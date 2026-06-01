"""
AEGIS RAG Retrieval — Vector Search, Query Processing & Knowledge Stats.

Handles all interaction with ChromaDB for retrieval:
  - Embedding model access (shared SentenceTransformer)
  - Collection management
  - Query preprocessing (abbreviation expansion)
  - Multi-turn query reformulation via fast LLM
  - Similarity search with threshold filtering
  - Context text formatting
  - Knowledge base statistics
"""
import os
import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq

from .rag_config import (
    KNOWLEDGE_COLLECTION,
    TOP_K,
    SIMILARITY_THRESHOLD,
    QUERY_EXPANSIONS,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  INFRASTRUCTURE — Embedder & ChromaDB Collection
# ═══════════════════════════════════════════════════════════════════════

def _get_embedder():
    """Reuse the SentenceTransformer already loaded by semantic_cache.py."""
    import moderation.services.cache.semantic_cache as sc
    if sc.embedder is None:
        sc.initialize_semantic_cache()
    return sc.embedder


def _get_knowledge_collection():
    """Get or create the knowledge base ChromaDB collection."""
    import chromadb

    chroma_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'chroma_storage'
    )
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_or_create_collection(
        name=KNOWLEDGE_COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )
    return collection


# ═══════════════════════════════════════════════════════════════════════
#  QUERY PREPROCESSING
#  Expand abbreviations and normalize French queries for better embedding
# ═══════════════════════════════════════════════════════════════════════

def _preprocess_query(query: str) -> str:
    """
    Expand common French abbreviations and clean query for better embedding match.
    Does NOT alter the meaning — only enriches with synonyms/full forms.
    """
    expanded = query.lower().strip()
    for abbr, full in QUERY_EXPANSIONS.items():
        if abbr in expanded:
            expanded = expanded.replace(abbr, full)
    return expanded


def _reformulate_query(session, question: str) -> str:
    """Rewrite a follow-up question into a standalone query using recent session history.

    Returns the rewritten query or the original question on failure. This mirrors the
    reformulation logic used in `ask_question` so that fallback retrieval benefits
    from multi-turn context even when the agent's tool-calling fails.
    """
    try:
        if not session:
            return question

        history_tuples = []
        # Fetch the most recent 10 messages, then reverse to chronological order
        recent_msgs = list(session.messages.order_by('-sent_at')[:10])
        recent_msgs.reverse()
        for m in recent_msgs:
            if m.role == 'user':
                history_tuples.append(("human", m.content))
            elif m.role == 'assistant':
                history_tuples.append(("ai", m.content))

        if not history_tuples:
            return question

        reformulate_prompt = ChatPromptTemplate.from_messages([
            ("system", "Given the following conversation history and the user's follow-up question, rewrite the follow-up question to be a standalone question that contains all the necessary context to be understood on its own. Do NOT answer the question, ONLY return the rewritten standalone question in the same language as the follow-up question. If the follow-up question is already standalone, just return it as is."),
            *history_tuples,
            ("human", "Follow-up question: {question}\nStandalone question:")
        ])

        fast_llm = ChatGroq(
            api_key=os.getenv("GROQ_API_KEY", "").strip().strip('"'),
            model_name="llama-3.1-8b-instant",
            temperature=0.0,
            max_tokens=150,
        )

        rewrite_chain = reformulate_prompt | fast_llm | StrOutputParser()
        rewritten = rewrite_chain.invoke({"question": question})
        if rewritten and isinstance(rewritten, str) and rewritten.strip():
            logger.debug(f"[RAG] Reformulated query: '{question}' -> '{rewritten}'")
            return rewritten
    except Exception as e:
        logger.debug(f"[RAG] Reformulation failed: {e}")

    return question


# ═══════════════════════════════════════════════════════════════════════
#  RETRIEVAL — ChromaDB Vector Search
# ═══════════════════════════════════════════════════════════════════════

def _retrieve_context(query: str, language: str = None) -> list[dict]:
    """
    Retrieve the most relevant chunks from ChromaDB for a given query.
    Applies similarity threshold filtering — only returns chunks above SIMILARITY_THRESHOLD.

    Returns list of dicts: [{text, source, source_type, score, chunk_preview}, ...]
    """
    embedder = _get_embedder()
    if embedder is None:
        return []

    collection = _get_knowledge_collection()

    # Embed the preprocessed query
    query_vector = embedder.encode(query).tolist()

    # Build filter if language specified
    where_filter = None
    if language and language != 'auto':
        where_filter = {"language": language}

    try:
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=TOP_K,
            include=["documents", "metadatas", "distances"],
            where=where_filter,
        )
        
        # Fallback: If no results found with language filter, try without filter
        if where_filter and (not results["documents"] or not results["documents"][0]):
            logger.debug(f"[RAG] No results found for language {language}. Falling back to all languages.")
            results = collection.query(
                query_embeddings=[query_vector],
                n_results=TOP_K,
                include=["documents", "metadatas", "distances"],
            )
            
    except Exception:
        # Fallback without language filter if it fails (e.g., no docs in that language)
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=TOP_K,
            include=["documents", "metadatas", "distances"],
        )

    if not results["documents"] or not results["documents"][0]:
        return []

    sources = []
    for i, doc_text in enumerate(results["documents"][0]):
        distance = results["distances"][0][i]
        similarity = 1.0 - distance
        metadata = results["metadatas"][0][i]

        # Web-learned snippets are usually shorter and noisier than document
        # chunks, so give them a slightly lower acceptance threshold.
        threshold = SIMILARITY_THRESHOLD
        if metadata.get("source_type") == "web":
            threshold = min(SIMILARITY_THRESHOLD, 0.32)

        # THRESHOLD GATE: Skip chunks below minimum relevance
        if similarity < threshold:
            logger.debug(f"[RAG] Skipping chunk (sim={similarity:.3f} < {threshold}): {doc_text[:60]}...")
            continue

        sources.append({
            "text": doc_text,
            "source": metadata.get("source", "Unknown"),
            "source_type": metadata.get("source_type", "document"),
            "category": metadata.get("category", "other"),
            "score": round(similarity, 3),
            "chunk_preview": doc_text[:150] + "..." if len(doc_text) > 150 else doc_text,
        })

    return sources


def _build_context_text(sources: list[dict]) -> str:
    """Build the context text block from retrieved sources."""
    if not sources:
        return "(Aucun document pertinent trouvé dans la base de connaissance.)"

    parts = []
    for i, src in enumerate(sources):
        parts.append(f"\n--- Extrait de document pertinent ---\n")
        parts.append(src['text'] + "\n")
    return "".join(parts)


# ═══════════════════════════════════════════════════════════════════════
#  KNOWLEDGE BASE STATS
# ═══════════════════════════════════════════════════════════════════════

def get_knowledge_stats() -> dict:
    """Return stats about the knowledge base."""
    from moderation.models import IndexedDocument

    docs = IndexedDocument.objects.filter(status='indexed')
    total_docs = docs.count()
    total_chunks = sum(d.chunk_count for d in docs)

    # Count web-learned chunks separately
    try:
        collection = _get_knowledge_collection()
        web_chunks = collection.get(where={"source_type": "web"}, include=[])
        web_chunk_count = len(web_chunks["ids"]) if web_chunks and web_chunks["ids"] else 0
    except Exception:
        web_chunk_count = 0

    return {
        "totalIndexedDocs": total_docs,
        "totalChunks": total_chunks + web_chunk_count,
        "webLearnedChunks": web_chunk_count,
        "lastUpdate": docs.order_by('-created_at').first().created_at.isoformat() if total_docs > 0 else None,
        # Placeholder metrics — in production, these would come from RAGAS evaluation
        "faithfulness": 0.88,
        "answerRelevancy": 0.82,
        "contextPrecision": 0.79,
    }
