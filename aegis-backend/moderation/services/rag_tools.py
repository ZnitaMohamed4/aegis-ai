"""
AEGIS RAG Tools — LangChain Tool Definitions for Agentic RAG.

These tools wrap existing RAG building blocks so the ReAct agent
can decide WHEN to call them instead of hardcoded if/else logic.

Tools:
  1. search_knowledge_base  — ChromaDB vector search
  2. search_web_and_learn   — SerpAPI fallback + auto-ingest
"""
import logging
from langchain_core.tools import tool
from pydantic import BaseModel, Field
try:
    # pydantic v2
    from pydantic import field_validator
except Exception:  # pragma: no cover - fallback for pydantic v1
    from pydantic import validator as field_validator
logger = logging.getLogger(__name__)


class SearchKnowledgeBaseInput(BaseModel):
    query: str = Field(
        description="The search query. IMPORTANT: Write in plain text and STRIP ALL ACCENTS (e.g., write 'autorisee' instead of 'autorisée') to avoid JSON parser errors."
    )

    @field_validator('query')
    def normalize_query(cls, v: str) -> str:
        """Normalize the query by stripping accents and normalising whitespace.

        This ensures the model's tool call JSON remains ASCII-safe even when
        the LLM generates accented characters.
        """
        if not isinstance(v, str):
            return v
        try:
            import unicodedata
            norm = unicodedata.normalize('NFKD', v)
            ascii_only = norm.encode('ascii', 'ignore').decode('ascii')
            return ' '.join(ascii_only.split())
        except Exception:
            return v

@tool(args_schema=SearchKnowledgeBaseInput)
def search_knowledge_base(query: str) -> str:
    """Search the AEGIS knowledge base (ChromaDB) for relevant legal documents,
    child protection guides, and cybersecurity information.

    Use this tool FIRST for any question. It searches through indexed documents
    including Moroccan laws (Loi 103-13, Loi 09-08, Loi 05-20), UNICEF/UNESCO
    guides, DGSN procedures, and previously learned web content.

    Args:
        query: The search query — use the user's question or a reformulated
               standalone version for multi-turn conversations.

    Returns:
        A formatted string with relevant document excerpts and their similarity
        scores, or a message indicating no relevant documents were found.
    """
    from .rag_retrieval import _retrieve_context, _build_context_text, _preprocess_query
    from .rag_config import SIMILARITY_THRESHOLD

    # Preprocess query for better embedding match (expand abbreviations, etc.)
    processed_query = _preprocess_query(query)

    # Retrieve from ChromaDB with threshold filtering
    retrieved = _retrieve_context(processed_query)

    if not retrieved:
        return (
            "NO RELEVANT DOCUMENTS FOUND in the knowledge base. "
            "The knowledge base does not contain information about this topic. "
            "Consider using the search_web_and_learn tool to find information online."
        )

    # Filter by quality
    high_quality = [s for s in retrieved if s["score"] >= SIMILARITY_THRESHOLD]

    if not high_quality:
        return (
            f"Found {len(retrieved)} documents but NONE passed the quality threshold "
            f"(best score: {retrieved[0]['score']:.3f}, threshold: {SIMILARITY_THRESHOLD}). "
            "The knowledge base has loosely related content but nothing specific enough. "
            "Consider using the search_web_and_learn tool for better results."
        )

    # Build structured response for the agent
    context_text = _build_context_text(high_quality)
    sources_summary = ", ".join(
        f"'{s['source']}' (score: {s['score']:.3f})" for s in high_quality[:5]
    )

    return (
        f"FOUND {len(high_quality)} relevant document(s) from the knowledge base.\n\n"
        f"Sources: {sources_summary}\n\n"
        f"--- RETRIEVED CONTENT ---\n{context_text}\n"
        f"--- END RETRIEVED CONTENT ---\n\n"
        f"Use ONLY the content above to formulate your answer. "
        f"Do not invent information beyond what is provided."
    )


class SearchWebAndLearnInput(BaseModel):
    query: str = Field(
        description="The search query to send to Google via SerpAPI."
    )

    @field_validator('query')
    def normalize_query(cls, v: str) -> str:
        """Also strip accents for web searches to keep downstream tool calls stable."""
        if not isinstance(v, str):
            return v
        try:
            import unicodedata
            norm = unicodedata.normalize('NFKD', v)
            ascii_only = norm.encode('ascii', 'ignore').decode('ascii')
            return ' '.join(ascii_only.split())
        except Exception:
            return v

@tool(args_schema=SearchWebAndLearnInput)
def search_web_and_learn(query: str) -> str:
    """Search the web when the knowledge base does not have sufficient information.
    Results are automatically saved to the knowledge base for future queries.

    ONLY use this tool when search_knowledge_base returns insufficient results.
    Do NOT use this as the first tool — always check the knowledge base first.

    The web search targets French-language results from Morocco (Google.ma).

    Args:
        query: The search query to send to Google via SerpAPI.

    Returns:
        A formatted string with web search results (title + snippet),
        or a message indicating no results were found.
    """
    from .rag_web import _web_search, _auto_learn_web_results, _build_web_context_text

    web_results = _web_search(query)

    if not web_results:
        return (
            "WEB SEARCH RETURNED NO RESULTS. "
            "Could not find relevant information online either. "
            "You should inform the user that this information is not available "
            "in either the knowledge base or on the web."
        )

    # Auto-learn web results into ChromaDB for future queries
    learned_count = _auto_learn_web_results(query, web_results)

    # Build structured response
    context_text = _build_web_context_text(web_results)
    sources_list = "\n".join(
        f"  - {r['title']} ({r['url']})" for r in web_results
    )

    return (
        f"WEB SEARCH returned {len(web_results)} result(s). "
        f"{learned_count} snippet(s) were auto-saved to the knowledge base for future use.\n\n"
        f"Web sources:\n{sources_list}\n\n"
        f"--- WEB CONTENT ---\n{context_text}\n"
        f"--- END WEB CONTENT ---\n\n"
        f"IMPORTANT: When answering from web results, mention that the information "
        f"comes from a web search, not from the local knowledge base."
    )
