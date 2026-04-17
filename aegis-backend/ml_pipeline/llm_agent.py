import os
import json
import logging
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent
from .agent_tools import fetch_recent_history, search_similar_cases

logger = logging.getLogger(__name__)

# ── ANSI colors (used in terminal output) ────────────────────
C_YELLOW  = "\033[93m"   # tool calls
C_CYAN    = "\033[96m"   # tool results
C_MAGENTA = "\033[95m"   # LLM reasoning  ← unique color you asked for
C_GREEN   = "\033[92m"   # pass / ALLOW
C_RED     = "\033[91m"   # BLOCK
C_ORANGE  = "\033[93m"   # WARN
C_RESET   = "\033[0m"
DIVIDER   = "═" * 62


def analyze_grey_zone(raw_text, primary_class, confidence, m1_score, sender_jid, instance_name):
    """
    Agent 3: ReAct Agent — Calls tools before reaching a decision.
    Equipped with: fetch_recent_history + search_similar_cases

    Terminal output is structured in one clean visual block:
      ═══ [AGENT 3: AUDITOR] ReAct Analysis Starting ═══
        🛠️  TOOL CALL → fetch_recent_history
        👀  RESULT    → ...
        💭  REASONING → <LLM chain-of-thought text> (magenta)
        ✅  VERDICT   → BLOCK [threat] — Direct threat to silence victim
      ═══════════════════════════════════════════════════

    Logger captures: TOOL CALL, TOOL RESULT, REASONING, FINAL VERDICT.
    NO duplicate RAW VERDICT log.
    """
    api_key    = os.getenv('GROQ_API_KEY')
    model_name = os.getenv('GROQ_MODEL', 'mixtral-8x7b-32768')

    if not api_key:
        logger.error("[AEGIS] GROQ API KEY MISSING")
        return {"decision": "HUMAN_REVIEW", "category": primary_class, "explanation": "API Key missing."}

    try:
        llm = ChatGroq(api_key=api_key, model_name=model_name, temperature=0.0)
    except Exception as e:
        logger.error(f"[AEGIS] Failed to initialize ChatGroq: {e}")
        return {"decision": "HUMAN_REVIEW", "category": primary_class, "explanation": "LLM init failed."}

    # ── System prompt ─────────────────────────────────────────
    system_prompt = f"""You are the AEGIS Child Safety Auditor — you classify messages on WhatsApp to protect children from bullying, threats, and harassment.

--- MESSAGE UNDER REVIEW ---
Text: "{raw_text}"
ML Label: {primary_class} | Confidence: {confidence:.2f} | Toxicity: {m1_score:.2f}
Sender: {sender_jid} | Instance: {instance_name}

--- CLASSIFICATION RULES (evaluate in order, stop at first match) ---

RULE 0 — GREETING OVERRIDE:
If this message is a neutral greeting, filler, or social opener on its own (e.g. "hey", "supp", "yo", "fine u", "haha", "lol", "ok") → ALLOW + safe. Past history does NOT make innocent greetings harmful. Judge the message, not the person.

RULE 1 — ALWAYS CHECK CONTEXT FIRST:
Before deciding, ALWAYS call `fetch_recent_history` with sender_jid="{sender_jid}" and instance_name="{instance_name}".
If the message is ambiguous, also call `search_similar_cases` with the message text.

RULE 2 — INTENT vs KEYWORDS (critical):
Words like "kill", "destroy", "you're dead", "wreck" are NOT automatically threats. Evaluate the INTENT behind the words:
  → FIGURATIVE use (gaming, sports, movies, slang, humor, hyperbole): "I'll destroy you in this 1v1", "that movie killed me", "you're dead in this match" → ALLOW + safe.
  → LITERAL use (targeting a real person with real-world action): "I will kill you after school", "I know where you live" → BLOCK + threat.
  KEY SIGNAL: Does the message reference REAL-WORLD harm (locations, times, physical actions, "in real life", "I'm not joking") or is it within an established casual/entertainment context? If the conversation history shows a casual topic (games, sports, movies, jokes), violent words stay figurative unless the sender explicitly breaks that frame.

RULE 3 — CLEAR HARM:
If text contains direct threats with real-world intent, sexual content, slurs, or discrimination with no ambiguity → BLOCK + appropriate category.

RULE 4 — ESCALATION IN CONTEXT:
  - If history shows an ESCALATING THREAT PATTERN and THIS message CONTINUES that pattern with real-world intent → BLOCK or WARN.
  - If history is hostile but this message is a topic shift or cooldown → DO NOT escalate. Classify this message on its own merit.

RULE 5 — MODERATE RUDENESS:
Insults without threat context → WARN + verbal_harassment.

RULE 6 — GENUINELY UNCLEAR:
If still uncertain after history + similar cases → HUMAN_REVIEW.

--- CATEGORIES ---
threat | sexual_harassment | discrimination | verbal_harassment | safe

--- HOW TO RESPOND ---
THINK first (2-3 sentences): explain your reasoning, reference the message and any history pattern.
Then output your verdict:
```json
{{"decision": "BLOCK|WARN|ALLOW|HUMAN_REVIEW", "category": "<category>", "explanation": "<15 words max>"}}
```"""

    tools = [fetch_recent_history, search_similar_cases]
    agent = create_react_agent(llm, tools, prompt=SystemMessage(content=system_prompt))

    try:
        inputs = {"messages": [("user", "Please analyse the message and give your JSON verdict.")]}

        # ── Print visual header ───────────────────────────────
        print(f"\n{DIVIDER}")
        print(f"  🧠 {C_MAGENTA}[AGENT 3: AUDITOR]{C_RESET} ReAct Analysis Starting")
        print(DIVIDER)
        logger.info(f"[AGENT 3: AUDITOR] ════ ReAct loop starting for: '{raw_text[:60]}' ════")

        final_message = None
        printed_ids   = set()

        for chunk in agent.stream(inputs, stream_mode="values"):
            messages = chunk.get("messages", [])
            if not messages:
                continue

            final_message = messages[-1]

            for msg in messages:
                if msg.id in printed_ids:
                    continue
                printed_ids.add(msg.id)

                # ── LLM tool-call decision ────────────────────
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        print(f"  🛠️  TOOL CALL → {C_YELLOW}{tc['name']}{C_RESET}")
                        print(f"  📥 ARGS      → {tc['args']}")
                        logger.info(f"[AGENT 3: TOOL CALL] {tc['name']} | args={tc['args']}")

                # ── Tool result ───────────────────────────────
                elif msg.type == "tool":
                    preview   = str(msg.content).replace('\n', ' | ')[:140]
                    tool_name = msg.name if hasattr(msg, "name") else "Tool"
                    print(f"  👀 {tool_name.upper()} → {C_CYAN}{preview}...{C_RESET}\n")
                    logger.info(f"[AGENT 3: TOOL RESULT] {tool_name} → {preview[:120]}...")

                # ── LLM reasoning text (chain-of-thought) ─────
                elif (
                    hasattr(msg, "content") and msg.content
                    and msg.type == "ai"
                    and not getattr(msg, "tool_calls", None)
                ):
                    full_text = str(msg.content).strip()
                    if full_text:
                        # Print only the thinking part (before ```json)
                        thinking = full_text.split("```")[0].strip()
                        if thinking:
                            print(f"  💭 {C_MAGENTA}REASONING{C_RESET} → {thinking[:280]}")
                        logger.info(f"[AGENT 3: REASONING] {full_text[:250]}")

        # ── Parse the JSON verdict ────────────────────────────
        output = final_message.content if final_message else ""

        if "```json" in output:
            json_str = output.split("```json")[1].split("```")[0].strip()
        elif "```" in output:
            json_str = output.split("```")[1].strip()
        else:
            json_str = output.strip()

        parsed = json.loads(json_str)
        valid  = {"BLOCK", "WARN", "ALLOW", "HUMAN_REVIEW"}
        if parsed.get("decision", "").upper() not in valid:
            parsed["decision"] = "HUMAN_REVIEW"

        decision = parsed.get("decision", "?")
        category = parsed.get("category", "?")
        expl     = parsed.get("explanation", "")

        # ── Color-coded verdict line ──────────────────────────
        vcolor = C_RED if decision == "BLOCK" else C_ORANGE if decision == "WARN" else C_GREEN
        print(f"  {C_GREEN}✅ VERDICT{C_RESET}   → {vcolor}{decision}{C_RESET} [{category}]  \"{expl}\"")
        print(DIVIDER + "\n")

        logger.info(
            f"[AGENT 3: FINAL VERDICT] Decision={decision} | "
            f"Category={category} | Explanation={expl}"
        )
        return parsed

    except Exception as e:
        logger.error(f"[AEGIS] ReAct Agent Error: {e}")
        return {"decision": "HUMAN_REVIEW", "category": primary_class, "explanation": "ReAct agent failed."}
