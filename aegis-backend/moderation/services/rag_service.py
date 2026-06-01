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

Module Structure (v3.1 — Refactored):
  rag_config.py      → Constants, prompts, suggested questions
  rag_retrieval.py   → Embedder, ChromaDB, query processing, similarity search
  rag_web.py         → SerpAPI search, auto-learn into ChromaDB
  rag_ingest.py      → Document upload, text extraction, chunking
  rag_fallback.py    → Direct retrieval when agent tool-calling fails
  rag_tools.py       → LangChain tool definitions for the ReAct agent
  rag_guardrails.py  → Input/output safety checks
  rag_service.py     → This file: ask_question() orchestrator only
"""
import os
import re
import logging

from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

# Import from refactored modules
from .rag_config import AGENT_SYSTEM_PROMPT
from .rag_retrieval import _reformulate_query
from .rag_fallback import _direct_rag_fallback

# Re-export commonly used functions for backward compatibility.
# Code that does `from moderation.services.rag_service import ingest_document`
# will continue to work.
from .rag_config import SIMILARITY_THRESHOLD, SUGGESTED_QUESTIONS  # noqa: F401
from .rag_retrieval import (  # noqa: F401
    _retrieve_context,
    _preprocess_query,
    _build_context_text,
    _get_embedder,
    _get_knowledge_collection,
    get_knowledge_stats,
)
from .rag_web import (  # noqa: F401
    _web_search,
    _auto_learn_web_results,
    _build_web_context_text,
)
from .rag_ingest import ingest_document, delete_document  # noqa: F401

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  ASK_QUESTION — The Orchestrator
# ═══════════════════════════════════════════════════════════════════════

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

    # ── 2. QUERY REFORMULATION (for multi-turn context) ──────────
    thinking_steps.append(
        {"label": "Vérification de la pertinence de la question...", "status": "done"}
    )

    # Reformulate the follow-up into a standalone question before running the topic guardrail.
    try:
        search_query = _reformulate_query(session, question)
        if search_query and search_query != question:
            thinking_steps.append({"label": "Question reformulée pour le contexte multi-tour", "status": "done"})
    except Exception:
        search_query = question

    # ── 3. INPUT GUARDRAIL: Topic relevance (run on reformulated query) ──
    is_allowed, refusal_message = input_topic_guardrail(search_query, language)

    if not is_allowed:
        thinking_steps.append(
            {"label": "Question hors-sujet — réponse bloquée par le garde-fou", "status": "warning"}
        )

        # Save the exchange even for blocked questions (save the original user text)
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

    thinking_steps.append({"label": "Question pertinente ✓ — lancement de l'agent", "status": "done"})

    # ── 4. Build and run the ReAct Agent ─────────────────────────
    # IMPORTANT: We use qwen3-32b for the agent, NOT llama-3.3-70b.
    # Llama 3.3 on Groq intermittently generates tool calls in native XML
    # format (<function=name{json}</function>) instead of OpenAI-compatible
    # JSON, causing "Failed to call a function" 400 errors.
    # qwen/qwen3-32b has 100% reliable structured tool-calling on Groq.
    llm = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY", "").strip().strip('"'),
        model_name="qwen/qwen3-32b",
        temperature=0.1,
        max_tokens=1500,
    )

    tools = [search_knowledge_base, search_web_and_learn]
    agent = create_react_agent(llm, tools, prompt=SystemMessage(content=AGENT_SYSTEM_PROMPT))

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
        seen_message_ids = set()

        for chunk in agent.stream(inputs, stream_mode="values"):
            messages = chunk.get("messages", [])
            if not messages:
                continue

            final_message = messages[-1]

            for msg in messages:
                msg_id = getattr(msg, "id", None)
                if msg_id and msg_id in seen_message_ids:
                    continue
                if msg_id:
                    seen_message_ids.add(msg_id)
                
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
                        collected_sources_text += tool_content + "\n\n"
                        # Extract source info from the tool output
                        retrieved_sources.extend(_extract_sources_from_kb_result(tool_content))
                        thinking_steps.append(
                            {"label": f"{len(retrieved_sources)} passages pertinents trouvés ✓", "status": "done"}
                        )

                    elif tool_name == "search_web_and_learn" and "WEB SEARCH returned" in tool_content:
                        collected_sources_text += tool_content + "\n\n"
                        web_sources.extend(_extract_sources_from_web_result(tool_content))
                        thinking_steps.append(
                            {"label": f"{len(web_sources)} résultats web trouvés et appris ✓", "status": "done"}
                        )

                    logger.info(f"[RAG AGENT] Tool result from {tool_name}: {tool_content[:120]}...")

        # Extract the final answer
        answer = final_message.content if final_message else ""
        if answer:
            answer = str(answer)
            # Convert markdown bold to HTML bold so it renders beautifully in the UI
            answer = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', answer)

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


# ═══════════════════════════════════════════════════════════════════════
#  SOURCE EXTRACTION HELPERS
# ═══════════════════════════════════════════════════════════════════════

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
                "type": "web",
                "score": 0.99,
                "chunk_preview": "",
            })

    return sources
