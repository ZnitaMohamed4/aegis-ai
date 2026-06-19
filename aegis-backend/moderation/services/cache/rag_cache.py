"""
AEGIS RAG Cache — Semantic Cache for Chatbot Question→Answer Pairs.

Avoids redundant LLM calls by storing (question, answer, sources) in a
dedicated ChromaDB collection.  When a new question is semantically
similar to one we've already answered, we return the cached answer
instantly — saving Groq tokens and cutting latency from ~3s to ~50ms.

Architecture:
  - Reuses the SentenceTransformer embedder from semantic_cache.py
  - Separate ChromaDB collection: "aegis_rag_cache"
  - TTL-based expiry:
      • Knowledge-base answers → 1 hour (stable facts)
      • Web-sourced answers    → 5 minutes (may change)
      • Guardrail refusals     → NOT cached (user should rephrase)

Cache Flow (in rag_service.py):
  ask_question()
    ├─ cache_hit? → return cached answer immediately
    └─ cache_miss → run full RAG pipeline → store result in cache
"""
import json
import time
import uuid
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

CACHE_COLLECTION = "aegis_rag_cache"
SIMILARITY_THRESHOLD = 0.88   # Questions must be very similar to count as a cache hit
MAX_CACHE_SIZE = 5000         # Max entries before we start evicting oldest

# TTL in seconds
TTL_KNOWLEDGE_BASE = 60 * 60        # 1 hour — legal facts don't change fast
TTL_WEB = 30 * 60                   # 30 minutes — legal/educational web content is stable
TTL_DEFAULT = 30 * 60               # 30 minutes fallback


# ═══════════════════════════════════════════════════════════════════════
#  CHROMADB COLLECTION (lazy init, shares embedder with semantic_cache)
# ═══════════════════════════════════════════════════════════════════════

_cache_collection = None


def _get_embedder():
    """Reuse the shared SentenceTransformer from semantic_cache.py."""
    import moderation.services.cache.semantic_cache as sc
    if sc.embedder is None:
        sc.initialize_semantic_cache()
    return sc.embedder


def _get_cache_collection():
    """Get or create the RAG cache ChromaDB collection."""
    global _cache_collection
    if _cache_collection is not None:
        return _cache_collection

    import os
    import chromadb

    chroma_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'chroma_storage'
    )
    client = chromadb.PersistentClient(path=chroma_path)
    _cache_collection = client.get_or_create_collection(
        name=CACHE_COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )
    return _cache_collection


# ═══════════════════════════════════════════════════════════════════════
#  CACHE LOOKUP
# ═══════════════════════════════════════════════════════════════════════

def get_cached_answer(question: str, language: str = "fr") -> dict | None:
    """
    Search the RAG cache for a semantically similar question.

    Returns:
        Cached response dict if hit, None if miss.
        Returns None if the cached entry has expired (TTL exceeded).
    """
    embedder = _get_embedder()
    collection = _get_cache_collection()
    if not embedder or not collection:
        return None

    try:
        # Preprocess (translate Darija/Arabic keywords to French) so the
        # English-trained embedder produces meaningful vectors.
        from moderation.services.rag_retrieval import _preprocess_query
        processed = _preprocess_query(question)
        query_vector = embedder.encode(processed).tolist()

        results = collection.query(
            query_embeddings=[query_vector],
            n_results=1,
            include=["documents", "metadatas", "distances"],
        )

        if not results["documents"] or not results["documents"][0]:
            return None

        distance = results["distances"][0][0]
        similarity = 1.0 - distance

        if similarity < SIMILARITY_THRESHOLD:
            return None

        metadata = results["metadatas"][0][0]

        # ── TTL check ───────────────────────────────────────────
        cached_at = float(metadata.get("cached_at", 0))
        ttl = _get_ttl_for_source_type(metadata.get("source_type", "knowledge_base"))
        age_seconds = time.time() - cached_at

        if age_seconds > ttl:
            # Entry expired — delete it and return miss
            doc_id = results["ids"][0][0] if results.get("ids") else None
            if doc_id:
                collection.delete(ids=[doc_id])
            logger.debug(f"[RAG CACHE] Expired entry (age={age_seconds:.0f}s, ttl={ttl}s)")
            return None

        # ── Language check ──────────────────────────────────────
        cached_language = metadata.get("language", "fr")
        if cached_language != language:
            # Different language = different answer, don't use cache
            return None

        # ── Cache hit! ──────────────────────────────────────────
        answer = metadata.get("answer", "")
        sources_json = metadata.get("sources_json", "[]")
        source_type = metadata.get("source_type", "knowledge_base")

        try:
            sources = json.loads(sources_json)
        except (json.JSONDecodeError, TypeError):
            sources = []

        logger.info(
            f"[RAG CACHE] ✅ Hit (sim={similarity:.3f}, age={age_seconds:.0f}s) "
            f"for: '{question[:60]}...'"
        )

        return {
            "answer": answer,
            "sources": sources,
            "source_type": source_type,
            "cached": True,
            "cache_similarity": round(similarity, 3),
        }

    except Exception as e:
        logger.error(f"[RAG CACHE] Lookup error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════
#  CACHE STORE
# ═══════════════════════════════════════════════════════════════════════

def cache_answer(
    question: str,
    answer: str,
    sources: list[dict],
    source_type: str = "knowledge_base",
    language: str = "fr",
) -> None:
    """
    Store a question→answer pair in the RAG cache for future reuse.

    Does NOT cache guardrail refusals or empty answers.
    """
    # Don't cache useless entries
    if not answer or not question or source_type == "guardrail":
        return

    embedder = _get_embedder()
    collection = _get_cache_collection()
    if not embedder or not collection:
        return

    try:
        # Preprocess (translate Darija/Arabic keywords to French) so the
        # English-trained embedder produces meaningful vectors. Must match
        # the preprocessing used in get_cached_answer().
        from moderation.services.rag_retrieval import _preprocess_query
        processed = _preprocess_query(question)
        vector = embedder.encode(processed).tolist()
        doc_id = str(uuid.uuid4())

        # Serialize sources to JSON for metadata storage
        sources_json = json.dumps(sources, ensure_ascii=False)

        collection.add(
            ids=[doc_id],
            embeddings=[vector],
            documents=[question],
            metadatas=[{
                "answer": answer,
                "sources_json": sources_json,
                "source_type": source_type,
                "language": language,
                "cached_at": str(time.time()),
            }],
        )

        logger.info(
            f"[RAG CACHE] 💾 Stored (type={source_type}) "
            f"'{question[:50]}...' → '{answer[:40]}...'"
        )

        # ── Evict oldest if cache is getting too large ──────────
        _evict_if_needed()

    except Exception as e:
        logger.error(f"[RAG CACHE] Store error: {e}")


# ═══════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _get_ttl_for_source_type(source_type: str) -> int:
    """Return the TTL in seconds based on where the answer came from."""
    if source_type == "web":
        return TTL_WEB
    return TTL_KNOWLEDGE_BASE


def _evict_if_needed():
    """Remove oldest entries if the cache exceeds MAX_CACHE_SIZE."""
    collection = _get_cache_collection()
    if not collection:
        return

    try:
        count = collection.count()
        if count <= MAX_CACHE_SIZE:
            return

        # Delete the oldest 10% to batch evictions
        evict_count = max(1, MAX_CACHE_SIZE // 10)
        # ChromaDB doesn't support ORDER BY, so we get all IDs and
        # rely on insertion order (oldest first in the ids list)
        all_ids = collection.get()["ids"]
        if all_ids and len(all_ids) > evict_count:
            collection.delete(ids=all_ids[:evict_count])
            logger.info(f"[RAG CACHE] Evicted {evict_count} oldest entries (was {count})")
    except Exception as e:
        logger.error(f"[RAG CACHE] Eviction error: {e}")


def get_cache_stats() -> dict:
    """Return stats about the RAG cache for the admin dashboard."""
    collection = _get_cache_collection()
    if not collection:
        return {"count": 0, "collection": CACHE_COLLECTION}

    try:
        return {
            "count": collection.count(),
            "collection": CACHE_COLLECTION,
            "similarity_threshold": SIMILARITY_THRESHOLD,
            "ttl_kb_seconds": TTL_KNOWLEDGE_BASE,
            "ttl_web_seconds": TTL_WEB,
            "max_size": MAX_CACHE_SIZE,
        }
    except Exception as e:
        return {"count": 0, "error": str(e)}


def clear_cache() -> int:
    """Clear all entries from the RAG cache. Returns count of deleted entries."""
    collection = _get_cache_collection()
    if not collection:
        return 0

    try:
        count = collection.count()
        all_ids = collection.get()["ids"]
        if all_ids:
            collection.delete(ids=all_ids)
        logger.info(f"[RAG CACHE] Cleared {count} entries")
        return count
    except Exception as e:
        logger.error(f"[RAG CACHE] Clear error: {e}")
        return 0
