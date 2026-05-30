"""
AEGIS RAG Service — Knowledge Base Chatbot Engine (v2)
========================================================
Powers the in-platform chatbot with Retrieval-Augmented Generation.

Architecture (v2 — Enhanced):
  User Question → Preprocess → ChromaDB Retriever (top-k=8, threshold gated)
       │
       ├─ Sufficient context? → Generate answer from docs (normal RAG)
       │
       └─ Insufficient?  → SerpAPI Web Search → Generate answer → Auto-learn to ChromaDB

Uses LangChain Expression Language (LCEL) for clean, composable chains.
Reuses the same SentenceTransformer embedder from semantic_cache.py.

Separate from the WhatsApp empathetic bot (chatbot_service.py):
  - This serves ADULTS (admins/parents) with legal/educational knowledge
  - The WhatsApp bot serves CHILDREN with empathetic conversation
"""
import os
import uuid
import logging
import re

import requests
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq

logger = logging.getLogger(__name__)

# ── ChromaDB Collection Name (separate from moderation cache!) ──────────
KNOWLEDGE_COLLECTION = "aegis_knowledge_base"

# ── Retrieval Configuration ─────────────────────────────────────────────
CHUNK_SIZE = 3000       # Larger chunks to keep legal articles intact
CHUNK_OVERLAP = 400     # More overlap to catch split articles
TOP_K = 8               # Retrieve 8 candidates, filter by threshold
SIMILARITY_THRESHOLD = 0.45   # Below this = irrelevant noise, skip
MIN_CONTEXT_CHUNKS = 1        # Minimum high-quality chunks before trusting local context


def _get_embedder():
    """Reuse the SentenceTransformer already loaded by semantic_cache.py."""
    from moderation.semantic_cache import embedder, initialize_semantic_cache
    if embedder is None:
        initialize_semantic_cache()
    from moderation.semantic_cache import embedder as loaded_embedder
    return loaded_embedder


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

# Static expansions for common legal query patterns
_QUERY_EXPANSIONS = {
    "c'est quoi": "qu'est-ce que",
    "c quoi": "qu'est-ce que",
    "cest quoi": "qu'est-ce que",
    "loi 09-08": "loi numéro 09-08 protection des données personnelles",
    "loi 103-13": "loi numéro 103-13 violences faites aux femmes",
    "loi 05-20": "loi numéro 05-20 cybersécurité",
    "loi 07-03": "loi numéro 07-03 infractions informatiques cybercrime",
}


def _preprocess_query(query: str) -> str:
    """
    Expand common French abbreviations and clean query for better embedding match.
    Does NOT alter the meaning — only enriches with synonyms/full forms.
    """
    expanded = query.lower().strip()
    for abbr, full in _QUERY_EXPANSIONS.items():
        if abbr in expanded:
            expanded = expanded.replace(abbr, full)
    return expanded


# ═══════════════════════════════════════════════════════════════════════
#  DOCUMENT INGESTION PIPELINE
#  Upload → Extract Text → Chunk → Embed → Store in ChromaDB
# ═══════════════════════════════════════════════════════════════════════

def _extract_text_from_file(file_obj, filename: str) -> str:
    """Extract raw text from an uploaded file (PDF or TXT)."""
    ext = os.path.splitext(filename)[1].lower()

    if ext == '.txt':
        content = file_obj.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')
        return content

    elif ext == '.pdf':
        try:
            import fitz  # PyMuPDF
            content = file_obj.read()
            doc = fitz.open(stream=content, filetype="pdf")
            text_parts = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                text_parts.append(page.get_text())
            doc.close()
            return "\n\n".join(text_parts)
        except ImportError:
            logger.error("[RAG] PyMuPDF (fitz) not installed. Install with: pip install PyMuPDF")
            raise ValueError("PDF support requires PyMuPDF. Install with: pip install PyMuPDF")

    elif ext in ('.md', '.markdown'):
        content = file_obj.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')
        return content

    else:
        raise ValueError(f"Unsupported file format: {ext}. Supported: .pdf, .txt, .md")


def _chunk_text(text: str, source_name: str, category: str, language: str) -> list[dict]:
    """
    Split text into overlapping chunks using Recursive Character Splitting.

    Strategy: Article-aware splitting for legal texts.
    - Tries to split at "Article" boundaries first to keep legal articles intact
    - Falls back to chapter/section/paragraph boundaries
    - 3000 chars per chunk with 400 char overlap
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=[
            "\nArticle ",     # Split at article boundaries first (legal texts)
            "\nChapitre ",    # Then chapter boundaries
            "\nSection ",     # Then section boundaries
            "\n\n",           # Double newline (paragraph)
            "\n",             # Single newline
            ". ",             # Sentence boundary
            " ",              # Word boundary
            "",               # Character boundary (last resort)
        ],
        length_function=len,
    )

    raw_chunks = splitter.split_text(text)

    chunks = []
    for i, chunk_text in enumerate(raw_chunks):
        # Skip chunks that are too small to be useful
        if len(chunk_text.strip()) < 50:
            continue
        chunks.append({
            "id": str(uuid.uuid4()),
            "text": chunk_text.strip(),
            "metadata": {
                "source": source_name,
                "source_type": "document",   # vs "web" for auto-learned
                "category": category,
                "language": language,
                "chunk_index": i,
                "total_chunks": len(raw_chunks),
            }
        })

    return chunks


def ingest_document(file_obj, filename: str, category: str, language: str, uploaded_by=None) -> dict:
    """
    Full ingestion pipeline: Upload → Extract → Chunk → Embed → Store.

    Returns:
        dict with keys: doc_id, name, chunk_count, status
    """
    from moderation.models import IndexedDocument

    # 1. Extract raw text
    logger.info(f"[RAG] Ingesting document: {filename}")
    raw_text = _extract_text_from_file(file_obj, filename)

    if not raw_text or len(raw_text.strip()) < 100:
        raise ValueError("Document is empty or too short to index.")

    # 2. Chunk the text
    chunks = _chunk_text(raw_text, filename, category, language)
    if not chunks:
        raise ValueError("No valid chunks could be extracted from this document.")

    # 3. Embed all chunks
    embedder = _get_embedder()
    if embedder is None:
        raise RuntimeError("Embedding model not available. Check server startup logs.")

    texts = [c["text"] for c in chunks]
    embeddings = embedder.encode(texts).tolist()

    # 4. Store in ChromaDB
    collection = _get_knowledge_collection()

    doc_id = str(uuid.uuid4())

    # Tag all chunks with the parent document ID for bulk deletion later
    for chunk in chunks:
        chunk["metadata"]["document_id"] = doc_id

    collection.add(
        ids=[c["id"] for c in chunks],
        embeddings=embeddings,
        documents=texts,
        metadatas=[c["metadata"] for c in chunks],
    )

    # 5. Save record in Django DB
    file_size = 0
    if hasattr(file_obj, 'size'):
        file_size = file_obj.size
    elif hasattr(file_obj, 'seek') and hasattr(file_obj, 'tell'):
        pos = file_obj.tell()
        file_obj.seek(0, 2)
        file_size = file_obj.tell()
        file_obj.seek(pos)

    doc_record = IndexedDocument.objects.create(
        id=doc_id,
        name=filename,
        category=category,
        language=language,
        chunk_count=len(chunks),
        file_size=file_size,
        status='indexed',
        uploaded_by=uploaded_by,
    )

    logger.info(f"[RAG] ✅ Indexed '{filename}': {len(chunks)} chunks stored in ChromaDB")

    return {
        "doc_id": str(doc_record.id),
        "name": filename,
        "chunk_count": len(chunks),
        "status": "indexed",
    }


def delete_document(doc_id: str):
    """Remove a document and all its chunks from ChromaDB + Django DB."""
    from moderation.models import IndexedDocument

    # 1. Remove chunks from ChromaDB by document_id metadata filter
    try:
        collection = _get_knowledge_collection()
        collection.delete(where={"document_id": doc_id})
        logger.info(f"[RAG] Deleted chunks for document {doc_id} from ChromaDB")
    except Exception as e:
        logger.error(f"[RAG] Error deleting from ChromaDB: {e}")

    # 2. Remove from Django DB
    try:
        IndexedDocument.objects.filter(id=doc_id).delete()
    except Exception as e:
        logger.error(f"[RAG] Error deleting from DB: {e}")


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


# ═══════════════════════════════════════════════════════════════════════
#  WEB SEARCH FALLBACK (SerpAPI)
#  When local knowledge base doesn't have enough context, search the web
# ═══════════════════════════════════════════════════════════════════════

def _web_search(query: str, num_results: int = 5) -> list[dict]:
    """
    Search the web using SerpAPI when local context is insufficient.

    Returns list of dicts: [{title, snippet, url, source}, ...]
    Falls back gracefully if API key is missing or request fails.
    """
    api_key = os.getenv("SERPAPI_KEY", "").strip()
    if not api_key:
        logger.warning("[RAG] SERPAPI_KEY not configured, skipping web search")
        return []

    try:
        resp = requests.get("https://serpapi.com/search", params={
            "q": query,
            "api_key": api_key,
            "engine": "google",
            "num": num_results,
            "hl": "fr",     # French results preferred
            "gl": "ma",     # Morocco geolocation
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("organic_results", [])[:num_results]:
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "url": item.get("link", ""),
                "source": item.get("displayed_link", ""),
            })

        logger.info(f"[RAG] Web search returned {len(results)} results for: '{query[:50]}...'")
        return results
    except Exception as e:
        logger.error(f"[RAG] Web search error: {e}")
        return []


def _auto_learn_web_results(query: str, web_results: list[dict]):
    """
    Store web search results back into ChromaDB for future retrieval.

    This makes the knowledge base grow incrementally — the same question
    asked twice will be answered from local cache on the second request.
    """
    embedder = _get_embedder()
    collection = _get_knowledge_collection()
    if not embedder or not web_results:
        return 0

    learned_count = 0
    for result in web_results:
        text = f"{result['title']}\n{result['snippet']}"
        if len(text.strip()) < 50:
            continue

        try:
            embedding = embedder.encode(text).tolist()
            chunk_id = str(uuid.uuid4())

            collection.add(
                ids=[chunk_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[{
                    "source": result.get("url", "web"),
                    "source_type": "web",
                    "source_title": result.get("title", ""),
                    "category": "web_search",
                    "language": "auto",
                    "original_query": query[:200],
                    "document_id": "web-auto-learned",
                }],
            )
            learned_count += 1
        except Exception as e:
            logger.error(f"[RAG] Error auto-learning web result: {e}")

    if learned_count > 0:
        logger.info(f"[RAG] Auto-learned {learned_count} web snippets into ChromaDB")
    return learned_count


# ═══════════════════════════════════════════════════════════════════════
#  RAG CHAIN — Question Answering with Source Citations
#  Uses LangChain Expression Language (LCEL)
# ═══════════════════════════════════════════════════════════════════════

RAG_SYSTEM_PROMPT = """Tu es l'Assistant Juridique AEGIS, expert en protection de l'enfance et cybersécurité au Maroc.

RÈGLES STRICTES:
1. Réponds UNIQUEMENT à partir des DOCUMENTS FOURNIS ci-dessous.
2. Sois ULTRA-CONCIS et direct (2-3 phrases). OBLIGATION ABSOLUE : Tu dois formuler ta réponse en utilisant des balises HTML (<b>texte</b> pour le gras, et <br> pour les sauts de ligne ou listes), QUELLE QUE SOIT LA LANGUE. Ne fais JAMAIS de copier-coller intégral.
3. INTERDICTION FORMELLE de mentionner les sources, les noms de fichiers, ou d'utiliser des crochets comme "[Source: ...]" dans ta réponse. Le système d'interface utilisateur s'en charge déjà. Ne termine JAMAIS ta réponse par une référence.
4. TRADUCTION OBLIGATOIRE : Tu DOIS ABSOLUMENT formuler ta réponse finale en {target_lang}. Si le document est en français et qu'on te parle en anglais, traduis la réponse en anglais.
5. Si AUCUN document pertinent n'est fourni ou si le contexte est insuffisant, réponds EXACTEMENT: "Je n'ai pas trouvé cette information dans la base de connaissance AEGIS."
6. Ne FABRIQUE JAMAIS d'information — ne dis JAMAIS "il est possible que" ou "d'autres cas pourraient exister".

DOCUMENTS PERTINENTS:
{context}
"""

RAG_WEB_SYSTEM_PROMPT = """Tu es l'Assistant AEGIS, expert en protection de l'enfance et cybersécurité au Maroc.
La base de connaissance locale ne contient pas assez d'information pour répondre.
Les résultats suivants proviennent d'une recherche web.

RÈGLES:
1. Réponds à partir des RÉSULTATS WEB fournis ci-dessous.
2. Sois ULTRA-CONCIS et direct. OBLIGATION ABSOLUE : Utilise les balises HTML <b>texte</b> pour le gras et <br> pour aérer le texte.
3. INTERDICTION FORMELLE d'inclure des URLs ou de mentionner la source dans le texte de ta réponse. Le système d'interface utilisateur s'en charge déjà. Ne termine JAMAIS ta réponse par une référence entre crochets.
4. TRADUCTION OBLIGATOIRE : Tu DOIS ABSOLUMENT formuler ta réponse finale en {target_lang}.
5. Précise que l'information provient d'une recherche web et non de la base de connaissance locale.
6. Sois factuel et précis — ne fabrique rien au-delà de ce qui est dans les résultats.

RÉSULTATS WEB:
{context}
"""

RAG_HUMAN_TEMPLATE = "{question}"


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

        # THRESHOLD GATE: Skip chunks below minimum relevance
        if similarity < SIMILARITY_THRESHOLD:
            logger.debug(f"[RAG] Skipping chunk (sim={similarity:.3f} < {SIMILARITY_THRESHOLD}): {doc_text[:60]}...")
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


def _build_web_context_text(web_results: list[dict]) -> str:
    """Build context text from web search results."""
    if not web_results:
        return "(Aucun résultat web trouvé.)"

    parts = []
    for r in web_results:
        parts.append(f"\n--- Extrait web pertinent ---\n")
        parts.append(r['snippet'] + "\n")
    return "".join(parts)


def ask_question(question: str, session_id: str = None, user=None, language: str = "fr") -> dict:
    """
    Full RAG pipeline: Preprocess → Retrieve → (Web fallback?) → Generate → Save.

    The pipeline checks local ChromaDB first. If fewer than MIN_CONTEXT_CHUNKS
    pass the similarity threshold, it falls back to SerpAPI web search and
    auto-learns the web results for future queries.

    Args:
        question: The user's question
        session_id: Existing ChatSession ID (or None to create new)
        user: The authenticated AegisUser
        language: Preferred language (fr/ar/en)

    Returns:
        dict with: answer, sources, session_id, source_type, thinking_steps
    """
    from moderation.models import ChatSession, ChatMessage

    # 1. Manage session and get conversational history
    session = None
    if session_id:
        try:
            session = ChatSession.objects.get(id=session_id)
        except (ChatSession.DoesNotExist, ValueError, Exception):
            session = None

    if not session:
        session = ChatSession.objects.create(
            user=user,
            language=language,
        )

    history_tuples = []
    # Fetch last 10 messages (5 turns) for context
    recent_msgs = session.messages.order_by('sent_at')[:10]
    for m in recent_msgs:
        if m.role == 'user':
            history_tuples.append(("human", m.content))
        elif m.role == 'assistant':
            history_tuples.append(("ai", m.content))

    search_query = question

    # 2. Query Reformulation (if there is history)
    if history_tuples:
        reformulate_prompt = ChatPromptTemplate.from_messages([
            ("system", "Given the following conversation history and the user's follow-up question, rewrite the follow-up question to be a standalone question that contains all the necessary context to be understood on its own. Do NOT answer the question, ONLY return the rewritten standalone question in the same language as the follow-up question. If the follow-up question is already standalone, just return it as is."),
            *history_tuples,
            ("human", "Follow-up question: {question}\nStandalone question:")
        ])
        
        fast_llm = ChatGroq(
            api_key=os.getenv("GROQ_API_KEY", "").strip().strip('"'),
            model_name="llama-3.1-8b-instant", # fast model for rewriting
            temperature=0.0,
            max_tokens=150,
        )
        
        try:
            rewrite_chain = reformulate_prompt | fast_llm | StrOutputParser()
            search_query = rewrite_chain.invoke({"question": question})
            logger.debug(f"[RAG] Reformulated query: '{question}' -> '{search_query}'")
        except Exception as e:
            logger.error(f"[RAG] Query reformulation failed: {e}")
            search_query = question # fallback to original

    # 3. Preprocess the search query for better embedding match
    processed_query = _preprocess_query(search_query)

    # 4. Retrieve relevant context from ChromaDB (threshold-gated) using the standalone query
    retrieved = _retrieve_context(processed_query, language)

    # 3. Decide: local context sufficient, or need web search?
    high_quality = [s for s in retrieved if s["score"] >= SIMILARITY_THRESHOLD]
    used_web_search = False
    web_sources = []

    thinking_steps = [
        {"label": f"Recherche dans {_get_knowledge_collection().count()} passages indexés...", "status": "done"},
        {"label": f"{len(high_quality)} passages pertinents trouvés (seuil: {SIMILARITY_THRESHOLD})", "status": "done"},
    ]

    lang_map = {'fr': 'français', 'ar': 'arabe', 'en': 'anglais'}
    target_lang = lang_map.get(language, 'la même langue que la question')

    if len(high_quality) < MIN_CONTEXT_CHUNKS:
        # Context insufficient — try web search fallback
        web_results = _web_search(search_query)
        if web_results:
            used_web_search = True
            web_sources = web_results
            context_text = _build_web_context_text(web_results)
            system_prompt = RAG_WEB_SYSTEM_PROMPT.replace('{target_lang}', target_lang)

            # Auto-learn web results for next time
            learned = _auto_learn_web_results(search_query, web_results)

            thinking_steps.append(
                {"label": f"Contexte local insuffisant — recherche web effectuée ({len(web_results)} résultats)", "status": "done"}
            )
            thinking_steps.append(
                {"label": f"{learned} résultats appris dans la base pour les requêtes futures", "status": "done"}
            )
        else:
            context_text = "(Aucun document pertinent trouvé dans la base de connaissance, et la recherche web n'a pas donné de résultats.)"
            system_prompt = RAG_SYSTEM_PROMPT.replace('{target_lang}', target_lang)
            thinking_steps.append(
                {"label": "Contexte insuffisant — aucune source web disponible", "status": "warning"}
            )
    else:
        # Normal RAG flow — use local documents
        context_text = _build_context_text(high_quality)
        system_prompt = RAG_SYSTEM_PROMPT.replace('{target_lang}', target_lang)
        thinking_steps.append(
            {"label": "Génération de la réponse avec Groq LLM...", "status": "done"}
        )

    # 5. Build the LCEL chain (without redundant history, since search_query is standalone)
    messages_for_prompt = [("system", system_prompt)]
    messages_for_prompt.append(("human", RAG_HUMAN_TEMPLATE))

    prompt = ChatPromptTemplate.from_messages(messages_for_prompt)

    llm = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY", "").strip().strip('"'),
        model_name=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        temperature=0.1,     # Factual, low creativity
        max_tokens=1500,
    )

    chain = prompt | llm | StrOutputParser()

    # 6. Invoke the chain
    try:
        answer = chain.invoke({
            "context": context_text,
            "question": search_query,
        })
    except Exception as e:
        logger.error(f"[RAG] LLM error: {e}")
        answer = "Désolé, une erreur est survenue lors de la génération de la réponse. Veuillez réessayer."

    # 7. Save user message and bot response
    ChatMessage.objects.create(
        session=session,
        role='user',
        content=question,
    )

    # Build retrieved context summary for storage
    if used_web_search:
        context_summary = "; ".join([f"{s['title']} ({s['url']})" for s in web_sources])
    else:
        context_summary = "; ".join([f"{s['source']} ({s['score']})" for s in retrieved]) if retrieved else ""

    source_type = "web" if used_web_search else "knowledge_base"

    ChatMessage.objects.create(
        session=session,
        role='assistant',
        content=answer,
        retrieved_context=context_summary,
        source_type=source_type,
    )

    # 8. Build response
    source_list = []
    seen_sources = set()

    # Local document sources
    for src in retrieved:
        if src["source"] not in seen_sources:
            seen_sources.add(src["source"])
            source_list.append({
                "name": src["source"],
                "score": src["score"],
                "type": "document",
                "chunk_preview": src["chunk_preview"],
            })

    # Web sources (if used)
    for ws in web_sources:
        source_list.append({
            "name": ws["title"],
            "score": None,
            "type": "web",
            "url": ws["url"],
            "chunk_preview": ws["snippet"][:150],
        })

    return {
        "answer": answer,
        "sources": source_list,
        "session_id": str(session.id),
        "source_type": source_type,
        "thinking_steps": thinking_steps,
    }
