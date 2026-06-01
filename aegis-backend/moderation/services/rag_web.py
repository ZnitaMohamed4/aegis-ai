"""
AEGIS RAG Web — SerpAPI Web Search & Auto-Learn.

When the local knowledge base doesn't have enough context, this module
searches the web via SerpAPI and auto-ingests the results back into
ChromaDB so the same question is answered locally next time.
"""
import os
import uuid
import logging

import requests

from .rag_retrieval import _get_embedder, _get_knowledge_collection

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  WEB SEARCH (SerpAPI)
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


# ═══════════════════════════════════════════════════════════════════════
#  AUTO-LEARN — Store web results back into ChromaDB
# ═══════════════════════════════════════════════════════════════════════

def _auto_learn_web_results(query: str, web_results: list[dict]) -> int:
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
        # Store the actual web snippet as the document text (title + snippet)
        # and move the originating query into metadata. This avoids burying
        # content under boilerplate which hurts semantic retrieval for
        # follow-up queries like "donnez moi plus de details?".
        text = f"{result.get('title','').strip()}\n\n{result.get('snippet','').strip()}"
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
                    # Use the chunk UUID as the document_id so deletions and
                    # statistics can target these learned snippets individually.
                    "document_id": chunk_id,
                }],
            )
            learned_count += 1
        except Exception as e:
            logger.error(f"[RAG] Error auto-learning web result: {e}")

    if learned_count > 0:
        logger.info(f"[RAG] Auto-learned {learned_count} web snippets into ChromaDB")
    return learned_count


# ═══════════════════════════════════════════════════════════════════════
#  CONTEXT FORMATTING
# ═══════════════════════════════════════════════════════════════════════

def _build_web_context_text(web_results: list[dict]) -> str:
    """Build context text from web search results."""
    if not web_results:
        return "(Aucun résultat web trouvé.)"

    parts = []
    for r in web_results:
        parts.append(f"\n--- Extrait web pertinent ---\n")
        parts.append(r['snippet'] + "\n")
    return "".join(parts)
