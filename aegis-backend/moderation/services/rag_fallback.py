"""
AEGIS RAG Fallback — Direct Retrieval When the ReAct Agent Fails.

When the LLM tool-calling layer breaks (e.g., malformed JSON, API errors),
this module runs retrieval directly and asks the model to answer from the
fetched context without tool-calling. Keeps the chatbot usable.
"""
import os
import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq

from .rag_config import AGENT_SYSTEM_PROMPT
from .rag_retrieval import (
    _retrieve_context,
    _reformulate_query,
    _build_context_text,
)
from .rag_web import _web_search, _auto_learn_web_results, _build_web_context_text

logger = logging.getLogger(__name__)


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

    # Persist the user's message immediately to avoid losing conversation
    # history if this fallback path errors mid-processing.
    try:
        ChatMessage.objects.create(
            session=session, role='user', content=question,
        )
    except Exception as e:
        logger.warning(f"[RAG] Failed to save user message in fallback: {e}")

    # Reformulate follow-up into a standalone query using session history
    reformulated_query = _reformulate_query(session, (search_query or question))
    kb_sources = _retrieve_context(reformulated_query)
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
        web_results = _web_search(reformulated_query)
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
        web_results = _web_search(reformulated_query)
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

    # NOTE: User message was already saved at the top of this function.
    # Do NOT save it again here — that was Bug #4 (duplicate user messages).

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
