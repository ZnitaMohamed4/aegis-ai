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

# ── i18n error messages shown to users when the pipeline fails ───────
_ERROR_MESSAGES = {
    "fr": "Désolé, une erreur est survenue. Veuillez réessayer.",
    "ar": "عذراً، حدث خطأ. يرجى إعادة المحاولة.",
    "en": "Sorry, an error occurred. Please try again.",
    "darija": "سمحلي، وقع خطأ. عافاك جرب مرة أخرى.",
}
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
#  AGENT SINGLETON — Avoid recreating ChatGroq/Gemini + ReAct agent per request
#  Saves ~200-500ms of object instantiation overhead on every call.
#  Supports dual providers: Groq (qwen3-32b) for FR/EN, Gemini for AR/Darija.
# ═══════════════════════════════════════════════════════════════════════

_cached_agents = {}   # key: (provider, api_key, model) → compiled agent


def _get_react_agent(language: str = "fr"):
    """Get or create a cached ReAct agent singleton.

    Provider selection:
      - darija / ar  → Gemini (far superior for Arabic-script text)
      - fr / en      → Groq qwen3-32b (reliable tool-calling)

    Falls back to Groq if Gemini is not configured.
    """
    from .rag_tools import search_knowledge_base, search_web_and_learn
    tools = [search_knowledge_base, search_web_and_learn]

    use_gemini = language in ("darija", "ar")

    if use_gemini:
        gemini_key = (
            os.getenv("GEMINI_API_KEY", "").strip().strip('"')
            or os.getenv("GOOGLE_AI_API_KEY", "").strip().strip('"')
        )
        gemini_model = os.getenv("GEMINI_RAG_MODEL", "gemini-2.5-flash")
        cache_key = ("gemini", gemini_key, gemini_model)

        if cache_key in _cached_agents:
            return _cached_agents[cache_key]

        if not gemini_key:
            # No Gemini key — fall back to Groq
            logger.warning("[RAG] GEMINI_API_KEY not set for %s — falling back to Groq", language)
            use_gemini = False
        else:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                llm = ChatGoogleGenerativeAI(
                    model=gemini_model,
                    google_api_key=gemini_key,
                    temperature=0.1,
                    max_tokens=1500,
                )
                agent = create_react_agent(
                    llm, tools, prompt=SystemMessage(content=AGENT_SYSTEM_PROMPT)
                )
                _cached_agents[cache_key] = agent
                logger.info(f"[RAG] Agent initialized (provider=gemini, model={gemini_model})")
                return agent
            except Exception as e:
                logger.warning(f"[RAG] Gemini agent creation failed: {e} — falling back to Groq")
                use_gemini = False

    # ── Groq (default for FR/EN, or Gemini fallback) ─────────────
    groq_key = os.getenv("GROQ_API_KEY", "").strip().strip('"')
    model_name = "qwen/qwen3-32b"
    cache_key = ("groq", groq_key, model_name)

    if cache_key in _cached_agents:
        return _cached_agents[cache_key]

    llm = ChatGroq(
        api_key=groq_key,
        model_name=model_name,
        temperature=0.1,
        max_tokens=1500,
    )
    agent = create_react_agent(
        llm, tools, prompt=SystemMessage(content=AGENT_SYSTEM_PROMPT)
    )
    _cached_agents[cache_key] = agent
    logger.info(f"[RAG] Agent initialized (provider=groq, model={model_name})")
    return agent


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
        language: Preferred language (fr/ar/en/darija)

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

    # ── 2b. SEMANTIC CACHE CHECK ─────────────────────────────────
    # Check if we've answered a very similar question recently.
    # Skips the entire agent pipeline on a hit (~3s → ~50ms).
    # IMPORTANT: Use the ORIGINAL question (not reformulated) for cache lookup.
    # This prevents follow-up questions like "tell me more" from being matched
    # against the previous topic-similar question in the cache.
    from .cache.rag_cache import get_cached_answer, cache_answer

    cached = get_cached_answer(question, language)
    if cached is not None:
        thinking_steps.append(
            {"label": f"⚡ Réponse en cache (similarité: {cached['cache_similarity']})", "status": "done"}
        )

        # Save to DB for conversation history (but skip the heavy pipeline)
        ChatMessage.objects.create(
            session=session, role='user', content=question,
        )
        ChatMessage.objects.create(
            session=session, role='assistant', content=cached["answer"],
            source_type=cached.get("source_type", "knowledge_base"),
        )

        return {
            "answer": cached["answer"],
            "sources": cached.get("sources", []),
            "session_id": str(session.id),
            "source_type": cached.get("source_type", "knowledge_base"),
            "thinking_steps": thinking_steps,
            "cached": True,
        }

    # ── 3. INPUT GUARDRAIL: Topic relevance (run on reformulated query) ──
    is_allowed, refusal_message = input_topic_guardrail(search_query, language, session=session)

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
    # Uses cached singleton to avoid ~200-500ms object creation per request.
    agent = _get_react_agent(language)

    thinking_steps.append(
        {"label": "Agent ReAct démarré — raisonnement en cours...", "status": "done"}
    )

    # Track what the agent does for observability and source extraction
    used_web_search = False
    collected_sources_text = ""   # Raw source text for hallucination check
    retrieved_sources = []         # Structured source list for response
    web_sources = []

    try:
        # Build agent input with session history for multi-turn context.
        # This lets the agent understand follow-up questions like "tell me more"
        # by seeing the prior conversation exchanges.
        agent_messages = []
        if session:
            try:
                recent = list(session.messages.order_by('-sent_at')[:8])
                recent.reverse()  # chronological order
                for m in recent:
                    role = 'user' if m.role == 'user' else 'assistant'
                    # Truncate long assistant responses to keep context manageable
                    content = m.content[:500] if m.content else ''
                    agent_messages.append((role, content))
            except Exception as e:
                logger.debug(f"[RAG] Failed to load session history: {e}")

        agent_messages.append(("user", search_query))
        inputs = {"messages": agent_messages}
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

        # Gemini returns structured content blocks as a list of dicts:
        #   [{'type': 'text', 'text': 'actual answer'}, ...]
        # Groq returns plain strings.  Handle both formats.
        if isinstance(answer, list):
            text_parts = []
            for block in answer:
                if isinstance(block, dict) and 'text' in block:
                    text_parts.append(block['text'])
                elif isinstance(block, str):
                    text_parts.append(block)
            answer = '\n'.join(text_parts)

        if answer:
            answer = str(answer)
            # Convert markdown bold to HTML bold so it renders beautifully in the UI
            answer = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', answer)

            # Convert markdown bullet lists (- item) to proper HTML <ul><li>
            # so they render correctly in both LTR and RTL directions.
            def _bullets_to_html(m):
                items = re.findall(r'^[\-\*\u2022]\s+(.+)', m.group(0), re.MULTILINE)
                return '<ul>' + ''.join(f'<li>{item}</li>' for item in items) + '</ul>'
            answer = re.sub(r'(?:^|\n)(?:[\-\*\u2022]\s+.+(?:\n|$))+', _bullets_to_html, answer)

        if not answer or not answer.strip():
            answer = _ERROR_MESSAGES.get(language, _ERROR_MESSAGES["fr"])

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
            # Apply output guardrails to fallback answer too
            fb_answer = fallback_payload.get("answer", "")
            _, fb_answer = output_hallucination_guardrail(fb_answer, "", language)
            if language:
                fb_answer = output_language_guardrail(fb_answer, language)
            fallback_payload["answer"] = fb_answer
            return fallback_payload

        answer = _ERROR_MESSAGES.get(language, _ERROR_MESSAGES["fr"])
        thinking_steps.append(
            {"label": "Erreur de l'agent — réponse par défaut", "status": "warning"}
        )

    # ── 5. OUTPUT GUARDRAILS ──────────────────────────────────────

    # 5a. Hallucination check
    is_grounded, answer = output_hallucination_guardrail(answer, collected_sources_text, language)
    if not is_grounded:
        thinking_steps.append(
            {"label": "⚠️ Garde-fou: réponse potentiellement non vérifiable", "status": "warning"}
        )
    else:
        thinking_steps.append(
            {"label": "Vérification de cohérence ✓", "status": "done"}
        )

    # 5b. Language enforcement (was dead code — now wired in)
    if language:
        answer = output_language_guardrail(answer, language)
        thinking_steps.append(
            {"label": f"Langue vérifiée ({language}) ✓", "status": "done"}
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

    assistant_msg = ChatMessage.objects.create(
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

    # ── 8. CACHE STORE ───────────────────────────────────────────
    # Store this fresh answer in the semantic cache so similar
    # questions are answered instantly next time.
    try:
        cache_answer(
            question=question,
            answer=answer,
            sources=source_list,
            source_type=source_type,
            language=language,
        )
    except Exception as cache_err:
        logger.warning(f"[RAG CACHE] Failed to store answer: {cache_err}")

    return {
        "answer": answer,
        "sources": source_list,
        "session_id": str(session.id),
        "message_id": str(assistant_msg.id),
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
