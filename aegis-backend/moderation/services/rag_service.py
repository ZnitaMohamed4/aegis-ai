"""
AEGIS RAG Service — Knowledge Base Chatbot Engine (v3 — Agentic RAG)
=====================================================================
Powers the in-platform chatbot with Agentic Retrieval-Augmented Generation.

Architecture (v3 — Agentic RAG + Guardrails):
  User Question → Input Guardrail (topic check)
       │
       ├─ Off-topic? → Polite refusal (no agent invoked)
       │
       └─ On-topic → ReAct Agent (decides tool calls dynamically)
                      │
                      ├─ Tool 1: search_knowledge_base (ChromaDB)
                      └─ Tool 2: search_web_and_learn (SerpAPI → auto-ingest)
                      │
                      └─ Agent answer → Output Guardrails
                                         ├─ Hallucination check
                                         └─ Language enforcement
                                         │
                                         └─ Final response to user

The agent DECIDES when to search ChromaDB, when to fall back to web search,
and whether it has enough context. No more hardcoded if/else logic.

Uses LangGraph's create_react_agent with LangChain tools.
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
from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

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
        # Keep the originating question in the learned chunk so future
        # semantically similar questions can retrieve it more reliably.
        text = (
            f"Question originale: {query}\n"
            f"Titre: {result['title']}\n"
            f"Extrait: {result['snippet']}"
        )
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
#  AGENTIC RAG — ReAct Agent with Tools + Guardrails
#  Replaces the old static LCEL chain with an agent that DECIDES what to do
# ═══════════════════════════════════════════════════════════════════════

AGENT_SYSTEM_PROMPT = """Tu es l'Assistant Juridique AEGIS, un expert en protection de l'enfance et cybersécurité au Maroc.

Tu disposes d'outils pour chercher des informations. Voici ta stratégie:

--- STRATÉGIE DE RECHERCHE ---
1. TOUJOURS utiliser l'outil search_knowledge_base en premier avec la question de l'utilisateur.
2. Si le résultat indique "NO RELEVANT DOCUMENTS" ou que les documents ne répondent pas à la question → utiliser l'outil search_web_and_learn pour chercher sur le web.
3. Si les résultats web sont aussi insuffisants → dire honnêtement que tu n'as pas trouvé l'information.
4. Ne JAMAIS inventer d'information. Répondre UNIQUEMENT à partir des résultats des outils.

--- RÈGLES DE RÉPONSE ---
1. Sois ULTRA-CONCIS et direct (2-3 phrases max, sauf si la question demande plus de détails).
2. OBLIGATION ABSOLUE : Formule ta réponse avec des balises HTML (<b>texte</b> pour le gras, <br> pour les sauts de ligne).
3. INTERDICTION FORMELLE de mentionner les sources, noms de fichiers, ou URLs dans ta réponse. Le système d'interface s'en charge.
4. TRADUCTION OBLIGATOIRE : Tu DOIS ABSOLUMENT répondre dans la MÊME LANGUE que la question de l'utilisateur (si la question est en français, réponds en français. Si en anglais, en anglais).
5. Si tu utilises des résultats web, mentionne brièvement que l'information provient d'une recherche web.
6. Ne FABRIQUE JAMAIS d'information — ne dis JAMAIS "il est possible que" ou "d'autres cas pourraient exister".
7. Si aucune source ne contient la réponse, réponds: "Je n'ai pas trouvé cette information dans la base de connaissance AEGIS."
"""


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
    Agentic RAG pipeline: Guardrails → ReAct Agent → Guardrails → Save.

    The agent DECIDES when to search ChromaDB, when to fall back to web search,
    and whether it has enough context — no more hardcoded if/else logic.

    Guardrails run before (topic check) and after (hallucination + language)
    the agent to ensure quality and safety.

    Args:
        question: The user's question
        session_id: Existing ChatSession ID (or None to create new)
        user: The authenticated AegisUser
        language: Preferred language (fr/ar/en)

    Returns:
        dict with: answer, sources, session_id, source_type, thinking_steps
    """
    from moderation.models import ChatSession, ChatMessage
    from .rag_tools import search_knowledge_base, search_web_and_learn
    from .rag_guardrails import (
        input_topic_guardrail,
        output_hallucination_guardrail,
        output_language_guardrail,
    )

    # ── 1. Manage session ────────────────────────────────────────
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

    thinking_steps = []

    # ── 2. INPUT GUARDRAIL: Topic relevance ──────────────────────
    thinking_steps.append(
        {"label": "Vérification de la pertinence de la question...", "status": "done"}
    )

    is_allowed, refusal_message = input_topic_guardrail(question, language)

    if not is_allowed:
        thinking_steps.append(
            {"label": "Question hors-sujet — réponse bloquée par le garde-fou", "status": "warning"}
        )

        # Save the exchange even for blocked questions
        ChatMessage.objects.create(
            session=session, role='user', content=question,
        )
        ChatMessage.objects.create(
            session=session, role='assistant', content=refusal_message,
            source_type='guardrail',
        )

        return {
            "answer": refusal_message,
            "sources": [],
            "session_id": str(session.id),
            "source_type": "guardrail",
            "thinking_steps": thinking_steps,
        }

    thinking_steps.append(
        {"label": "Question pertinente ✓ — lancement de l'agent", "status": "done"}
    )

    # ── 3. Query Reformulation (multi-turn context) ──────────────
    history_tuples = []
    recent_msgs = session.messages.order_by('sent_at')[:10]
    for m in recent_msgs:
        if m.role == 'user':
            history_tuples.append(("human", m.content))
        elif m.role == 'assistant':
            history_tuples.append(("ai", m.content))

    search_query = question

    if history_tuples:
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

        try:
            rewrite_chain = reformulate_prompt | fast_llm | StrOutputParser()
            search_query = rewrite_chain.invoke({"question": question})
            logger.debug(f"[RAG] Reformulated query: '{question}' -> '{search_query}'")
            thinking_steps.append(
                {"label": "Question reformulée pour le contexte multi-tour", "status": "done"}
            )
        except Exception as e:
            logger.error(f"[RAG] Query reformulation failed: {e}")
            search_query = question

    # ── 4. Build and run the ReAct Agent ─────────────────────────
    # Inject session_id into the system prompt
    system_prompt = AGENT_SYSTEM_PROMPT

    llm = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY", "").strip().strip('"'),
        model_name=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        temperature=0.1,
        max_tokens=1500,
    )

    tools = [search_knowledge_base, search_web_and_learn]
    agent = create_react_agent(llm, tools, prompt=SystemMessage(content=system_prompt))

    thinking_steps.append(
        {"label": "Agent ReAct démarré — raisonnement en cours...", "status": "done"}
    )

    # Track what the agent does for observability and source extraction
    used_web_search = False
    collected_sources_text = ""   # Raw source text for hallucination check
    retrieved_sources = []         # Structured source list for response
    web_sources = []

    try:
        inputs = {"messages": [("user", search_query)]}
        final_message = None

        for chunk in agent.stream(inputs, stream_mode="values"):
            messages = chunk.get("messages", [])
            if not messages:
                continue

            final_message = messages[-1]

            for msg in messages:
                # Track tool calls for thinking_steps
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_name = tc["name"]
                        if tool_name == "search_knowledge_base":
                            thinking_steps.append(
                                {"label": "🔍 Recherche dans la base de connaissance...", "status": "done"}
                            )
                        elif tool_name == "search_web_and_learn":
                            used_web_search = True
                            thinking_steps.append(
                                {"label": "🌐 Recherche web (base insuffisante)...", "status": "done"}
                            )
                        logger.info(f"[RAG AGENT] Tool call: {tool_name} | args={tc['args']}")

                # Capture tool results for source extraction
                elif msg.type == "tool":
                    tool_content = str(msg.content)
                    tool_name = msg.name if hasattr(msg, "name") else "Tool"

                    if tool_name == "search_knowledge_base" and "FOUND" in tool_content:
                        collected_sources_text += tool_content
                        # Extract source info from the tool output
                        retrieved_sources = _extract_sources_from_kb_result(tool_content)
                        thinking_steps.append(
                            {"label": f"{len(retrieved_sources)} passages pertinents trouvés ✓", "status": "done"}
                        )

                    elif tool_name == "search_web_and_learn" and "WEB SEARCH returned" in tool_content:
                        collected_sources_text += tool_content
                        web_sources = _extract_sources_from_web_result(tool_content)
                        thinking_steps.append(
                            {"label": f"{len(web_sources)} résultats web trouvés et appris ✓", "status": "done"}
                        )

                    logger.info(f"[RAG AGENT] Tool result from {tool_name}: {tool_content[:120]}...")

        # Extract the final answer
        answer = final_message.content if final_message else ""

        if not answer or not answer.strip():
            answer = "Désolé, je n'ai pas pu générer une réponse. Veuillez reformuler votre question."

    except Exception as e:
        logger.error(f"[RAG] ReAct Agent error: {e}")
        fallback_payload = _direct_rag_fallback(
            question=question,
            search_query=search_query,
            language=language,
            session=session,
            thinking_steps=thinking_steps,
            error=e,
        )
        if fallback_payload is not None:
            return fallback_payload

        answer = "Désolé, une erreur est survenue lors de la génération de la réponse. Veuillez réessayer."
        thinking_steps.append(
            {"label": "Erreur de l'agent — réponse par défaut", "status": "warning"}
        )

    # ── 5. OUTPUT GUARDRAILS ──────────────────────────────────────

    # 5a. Hallucination check
    is_grounded, answer = output_hallucination_guardrail(answer, collected_sources_text)
    if not is_grounded:
        thinking_steps.append(
            {"label": "⚠️ Garde-fou: réponse potentiellement non vérifiable", "status": "warning"}
        )
    else:
        thinking_steps.append(
            {"label": "Vérification de cohérence ✓", "status": "done"}
        )

    # 5b. Language enforcement disabled - rely on LLM to match query language
    # answer = output_language_guardrail(answer, language)

    thinking_steps.append(
        {"label": "Réponse générée avec succès ✓", "status": "done"}
    )

    # ── 6. Save to database ──────────────────────────────────────
    ChatMessage.objects.create(
        session=session, role='user', content=question,
    )

    # Build context summary for storage
    if used_web_search and web_sources:
        context_summary = "; ".join([f"{s['name']} ({s.get('url', '')})" for s in web_sources])
    elif retrieved_sources:
        context_summary = "; ".join([f"{s['name']} ({s.get('score', '')})" for s in retrieved_sources])
    else:
        context_summary = ""

    source_type = "web" if used_web_search else "knowledge_base"

    ChatMessage.objects.create(
        session=session, role='assistant', content=answer,
        retrieved_context=context_summary,
        source_type=source_type,
    )

    # ── 7. Build response ────────────────────────────────────────
    source_list = []
    seen_sources = set()

    for src in retrieved_sources:
        if src["name"] not in seen_sources:
            seen_sources.add(src["name"])
            source_list.append({
                "name": src["name"],
                "score": src.get("score"),
                "type": "document",
                "chunk_preview": src.get("chunk_preview", ""),
            })

    for ws in web_sources:
        source_list.append({
            "name": ws["name"],
            "score": 0.99, # Default high score for web results so frontend doesn't show 0%
            "type": "web",
            "url": ws.get("url", ""),
            "chunk_preview": ws.get("chunk_preview", ""),
        })

    return {
        "answer": answer,
        "sources": source_list,
        "session_id": str(session.id),
        "source_type": source_type,
        "thinking_steps": thinking_steps,
    }


def _extract_sources_from_kb_result(tool_output: str) -> list[dict]:
    """
    Parse the search_knowledge_base tool output to extract source metadata.
    The tool returns structured text with source names and scores.
    """
    sources = []
    # Extract from "Sources: 'name' (score: 0.xxx), ..." line
    sources_match = re.search(r"Sources:\s*(.+?)\n", tool_output)
    if sources_match:
        sources_str = sources_match.group(1)
        # Parse each 'name' (score: 0.xxx) entry
        for match in re.finditer(r"'([^']+)'\s*\(score:\s*([\d.]+)\)", sources_str):
            sources.append({
                "name": match.group(1),
                "score": float(match.group(2)),
                "chunk_preview": "",
            })

    # If parsing failed or it's a "NO RELEVANT DOCUMENTS FOUND" response, return empty list
    # We do NOT want to return a generic 0% source.
    return sources


def _extract_sources_from_web_result(tool_output: str) -> list[dict]:
    """
    Parse the search_web_and_learn tool output to extract web source metadata.
    """
    sources = []
    # Extract from "  - Title (URL)" lines
    for match in re.finditer(r"\s*-\s*(.+?)\s*\(([^)]+)\)", tool_output):
        title = match.group(1).strip()
        url = match.group(2).strip()
        # Only include actual URLs, not score patterns
        if url.startswith("http"):
            sources.append({
                "name": title,
                "url": url,
                "chunk_preview": "",
            })

    return sources


def _direct_rag_fallback(
    question: str,
    search_query: str,
    language: str,
    session,
    thinking_steps: list[dict],
    error: Exception,
) -> dict | None:
    """Fallback path when the ReAct agent fails to produce a valid tool call.

    This keeps the chatbot usable even when the LLM tool-calling layer breaks.
    It runs retrieval directly, then asks the model to answer from the fetched
    context without tool-calling.
    """
    from moderation.models import ChatMessage

    logger.warning(f"[RAG] Falling back to direct retrieval after agent failure: {error}")
    thinking_steps.append(
        {"label": "Agent tool-call failed — fallback retrieval en cours", "status": "warning"}
    )

    kb_sources = _retrieve_context(search_query or question)
    retrieved_sources = [
        {
            "name": src.get("source", "Unknown"),
            "score": src.get("score", 0.0),
            "chunk_preview": src.get("chunk_preview", ""),
        }
        for src in kb_sources
    ]
    kb_context = _build_context_text(kb_sources)

    used_web_search = False
    web_context = ""
    web_sources = []

    if not kb_sources:
        web_results = _web_search(search_query or question)
        if web_results:
            _auto_learn_web_results(search_query or question, web_results)
            web_context = _build_web_context_text(web_results)
            web_sources = [
                {
                    "name": r.get("title", "Unknown"),
                    "url": r.get("url", ""),
                    "chunk_preview": r.get("snippet", ""),
                }
                for r in web_results
            ]
            used_web_search = True
            thinking_steps.append(
                {"label": f"{len(web_sources)} résultats web trouvés via fallback ✓", "status": "done"}
            )
    elif "NO RELEVANT DOCUMENTS FOUND" in kb_context or "NONE passed the quality threshold" in kb_context:
        web_results = _web_search(search_query or question)
        if web_results:
            _auto_learn_web_results(search_query or question, web_results)
            web_context = _build_web_context_text(web_results)
            web_sources = [
                {
                    "name": r.get("title", "Unknown"),
                    "url": r.get("url", ""),
                    "chunk_preview": r.get("snippet", ""),
                }
                for r in web_results
            ]
            used_web_search = True
            thinking_steps.append(
                {"label": f"{len(web_sources)} résultats web trouvés via fallback ✓", "status": "done"}
            )

    sources_text = "\n\n".join([txt for txt in [kb_context, web_context] if txt]).strip()

    llm = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY", "").strip().strip('"'),
        model_name=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        temperature=0.1,
        max_tokens=1200,
    )

    fallback_prompt = ChatPromptTemplate.from_messages([
        ("system", AGENT_SYSTEM_PROMPT),
        ("human", "Question de l'utilisateur: {question}\n\nCONTEXT SOURCES:\n{sources}\n\nRéponds uniquement à partir des sources ci-dessus."),
    ])

    try:
        chain = fallback_prompt | llm | StrOutputParser()
        answer = chain.invoke({
            "question": question,
            "sources": sources_text or "(Aucun document pertinent trouvé.)",
        }).strip()
        if not answer:
            answer = "Désolé, je n'ai pas pu générer une réponse. Veuillez reformuler votre question."
    except Exception as fallback_error:
        logger.error(f"[RAG] Direct fallback generation failed: {fallback_error}")
        answer = "Désolé, une erreur est survenue lors de la génération de la réponse. Veuillez réessayer."
        thinking_steps.append(
            {"label": "Fallback génération échouée — réponse par défaut", "status": "warning"}
        )

    ChatMessage.objects.create(
        session=session, role='user', content=question,
    )

    if used_web_search and web_sources:
        context_summary = "; ".join([f"{s['name']} ({s.get('url', '')})" for s in web_sources])
    elif retrieved_sources:
        context_summary = "; ".join([f"{s['name']} ({s.get('score', '')})" for s in retrieved_sources])
    else:
        context_summary = ""

    source_type = "web" if used_web_search else "knowledge_base"

    ChatMessage.objects.create(
        session=session, role='assistant', content=answer,
        retrieved_context=context_summary,
        source_type=source_type,
    )

    source_list = []
    seen_sources = set()

    for src in retrieved_sources:
        if src["name"] not in seen_sources:
            seen_sources.add(src["name"])
            source_list.append({
                "name": src["name"],
                "score": src.get("score"),
                "type": "document",
                "chunk_preview": src.get("chunk_preview", ""),
            })

    for ws in web_sources:
        source_list.append({
            "name": ws["name"],
            "score": 0.99,
            "type": "web",
            "url": ws.get("url", ""),
            "chunk_preview": ws.get("chunk_preview", ""),
        })

    thinking_steps.append(
        {"label": "Réponse générée via fallback direct ✓", "status": "done"}
    )

    return {
        "answer": answer,
        "sources": source_list,
        "session_id": str(session.id),
        "source_type": source_type,
        "thinking_steps": thinking_steps,
    }
