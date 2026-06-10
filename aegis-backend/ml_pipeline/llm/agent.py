import os
import json
import logging
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent
from .tools import fetch_recent_history, search_similar_cases, fetch_risk_profile

logger = logging.getLogger(__name__)


def analyze_grey_zone(raw_text, primary_class, confidence, m1_score, sender_jid, instance_name, image_context=None, is_darija=False, darija_script=None):
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
    model_name = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')

    if not api_key:
        logger.error("[AEGIS] GROQ API KEY MISSING")
        return {"decision": "HUMAN_REVIEW", "category": primary_class, "explanation": "API Key missing."}

    try:
        llm = ChatGroq(api_key=api_key, model_name=model_name, temperature=0.0)
    except Exception as e:
        logger.error(f"[AEGIS] Failed to initialize ChatGroq: {e}")
        return {"decision": "HUMAN_REVIEW", "category": primary_class, "explanation": "LLM init failed."}

    # ── System prompt ─────────────────────────────────────────
    # updated using claude
    system_prompt = f"""You are the AEGIS Child Safety Auditor — classify WhatsApp messages to protect minors from harassment, threats, and grooming.

    --- MESSAGE ---
    Text: "{raw_text}"
    ML Label: {primary_class} | Confidence: {(confidence or 0.0):.2f} | Toxicity: {(m1_score or 0.0):.2f}
    Sender: {sender_jid} | Instance: {instance_name}

    --- CORE PRINCIPLE ---
    Classify the MESSAGE in context. A message that seems harmless alone can be a grooming step in a sequence.

    --- TOOL USAGE ---
    - Call `fetch_risk_profile` FIRST if the message is ambiguous, the sender is unknown, or ANY grooming signal exists. This gives you the sender's Digital Twin: risk level, archetype (Groomer/Bully/Troll), and Bayesian evidence.
    - Call `fetch_recent_history` if the message is ambiguous OR if ANY prior grooming signal exists.
    - Call `search_similar_cases` only if uncertainty remains after history.
    - Skip tools for obvious cases (clear threats, clear greetings).
    - GROOMING EXCEPTION: If this message contains ANY grooming indicator (Rule 1), ALWAYS call fetch_risk_profile AND fetch_recent_history — grooming operates across multiple messages.
    - RISK-AWARE JUDGMENT: If fetch_risk_profile returns a CRITICAL or HIGH risk sender, treat ambiguous messages with maximum suspicion. A low-toxicity message from a CRITICAL Groomer Pattern sender is NOT safe.

    --- PRIORITY RULES (top → bottom, stop at first match) ---

    RULE 0 — SAFE GREETING:
    Neutral openers alone ("hi", "hey", "lol", "ok", "gg") → ALLOW + safe.
    Ignore past toxicity for standalone greetings.

    RULE 1 — GROOMING (CRITICAL — SEQUENCE-AWARE):
    If this message contains ANY of:
    - Relationship/age questions ("do you have a boyfriend?", "how old are you?")
    - Maturity or appearance compliments ("you seem mature for your age", "you're so pretty")
    - Secrecy language ("don't tell anyone", "just between us", "our little secret")
    - Boundary erosion ("I'm not like your parents", "you can trust me", "tell me anything")
    - Unusual intimacy from sender with days_known < 60

    → ALWAYS fetch history first.
    → If history shows 2+ prior grooming indicators from same sender: ESCALATE
    → If history shows 1 prior grooming indicator: HUMAN_REVIEW
    → If no prior history but message is clearly grooming: HUMAN_REVIEW
    → Toxicity score is IRRELEVANT for grooming. Low toxicity ≠ safe.

    RULE 2 — INTENT CHECK (violent words ≠ threat):
    Evaluate INTENT before deciding on any violent/aggressive language.
    - Figurative (gaming, sports, humor, hyperbole): "I'll destroy you in this 1v1" → ALLOW
    - Real-world intent (location, time, physical target): "I'll beat you up tomorrow" → BLOCK
    If context is established as gaming/casual, maintain that frame unless explicitly broken.

    RULE 3 — CLEAR HARM:
    Direct threats with real-world intent, sexual content, slurs, or discrimination → BLOCK
    Extreme immediate physical threats or severe grooming → ESCALATE

    RULE 3B — DECISION STRENGTH (CRITICAL):
    - UNKNOWN sender (no history, days_known < 30) + threat or sexual content → BLOCK, NOT HUMAN_REVIEW.
      A stranger saying "I'll be waiting for you after school" is NOT ambiguous. BLOCK it.
      A stranger commenting on a child's body is NOT ambiguous. BLOCK it.
    - HUMAN_REVIEW is ONLY for genuinely ambiguous cases where context could go either way
      (e.g., a known contact with mixed history, borderline phrasing with no clear intent).
    - When in doubt between BLOCK and HUMAN_REVIEW for threats/sexual content: choose BLOCK.
      False alarms are reviewed. Missed threats are not.

    RULE 4 — CONTEXT ESCALATION:
    - Escalating pattern + this message continues it → BLOCK or WARN
    - Escalating pattern + this message is neutral → classify on its own merit only

    RULE 5 — MODERATE RUDENESS:
    Non-threatening insults without real-world threat → WARN + verbal_harassment

    RULE 6 — UNCERTAIN:
    Still unclear after tools → HUMAN_REVIEW

    --- CATEGORIES ---
    threat | sexual_harassment | discrimination | verbal_harassment | nsfw_image | violent_image | safe

    --- OUTPUT (STRICT JSON ONLY, no preamble) ---
    {{"decision": "ESCALATE|BLOCK|WARN|ALLOW|HUMAN_REVIEW", "category": "<category>", "explanation": "<12 words max>"}}"""

    # ── IMAGE CONTEXT INJECTION ──────────────────────────────────────
    # When the message contains an image that was analyzed by ViT classifiers,
    # inject the results into the system prompt so the LLM can make informed decisions.
    if image_context:
        image_section = f"""

    --- IMAGE ANALYSIS (ViT Classifiers) ---
    This message contains an IMAGE analyzed by Vision Transformer models:
    - NSFW Detected: {image_context.get('nsfw', False)} (confidence: {image_context.get('nsfw_score', 0.0):.4f})
    - Violence Detected: {image_context.get('violent', False)} (confidence: {image_context.get('violent_score', 0.0):.4f})
    - OCR Text Extracted: "{image_context.get('ocr_text', '') or '(none)'}" 

    IMAGE RULES (override all other rules):
    - If NSFW=True → BLOCK with category "nsfw_image". No exceptions.
    - If Violence=True → BLOCK with category "violent_image". No exceptions.
    - If OCR text contains harmful content → classify the OCR text using the standard rules above.
    - Do NOT downgrade image-flagged content to HUMAN_REVIEW. ViT classifiers are definitive."""
        system_prompt += image_section

    # ── DARIJA CONTEXT INJECTION ────────────────────────────────────────
    # When the message was flagged by M1D (DarijaBERT-mix), inject Moroccan
    # cultural context so the LLM can properly assess Darija-specific patterns.
    if is_darija:
        darija_section = f"""

    --- DARIJA AWARENESS (Moroccan Arabic Dialect) ---
    This message is in Moroccan Darija (الدارجة المغربية), detected by M1D (DarijaBERT-mix).
    Script: {darija_script or 'unknown'} (arabic / arabizi / mixed).

    CRITICAL CONTEXT:
    - Darija mixes Arabic, French, and Amazigh vocabulary within sentences
    - Many severe insults appear mild in MSA/English translation
    - Grooming in Moroccan context often uses French terms of endearment
    - Code-switching (Arabic<->French within one sentence) is normal communication
    - Arabizi uses digits as letters: 2=hamza, 3=ain, 5=kha, 7=ha, 8/9=qaf

    DARIJA-SPECIFIC SEVERITY GUIDE:
    - "sir t9awed" / "sir tqwd" = severe verbal insult, equivalent to "fuck off" (BLOCK as verbal_harassment)
    - "9a7ba" / "qa7ba" / "l9a7ba" = severe gendered slur (BLOCK)
    - "nta 7mar" / "7mara" / "حمار" = strong dehumanizing insult (WARN/BLOCK by context)
    - "ghadi ndarbek" / "n9tlek" / "غادي نقتلك" = direct physical threat (BLOCK/ESCALATE)
    - "bghitek" / "bghitk" from stranger to minor = grooming signal (HUMAN_REVIEW)
    - "3tini snap" / "aji l whtsp" = off-platforming grooming signal (HUMAN_REVIEW)
    - "matgoulich l mamak" / "bini w binek" = forced secrecy grooming (BLOCK)
    - "salam" / "labas" / "cv?" / "kifach" = safe greetings (ALLOW)

    GENERAL PRINCIPLE: Do not rely only on exact keywords above. Use them as reference
    examples, but apply the same severity logic to ANY Darija expression you encounter.
    Darija is highly contextual — the same word can be friendly or threatening depending
    on tone, relationship, and surrounding words. When in doubt, assess INTENT over vocabulary."""
        system_prompt += darija_section

    tools = [fetch_risk_profile, fetch_recent_history, search_similar_cases]
    agent = create_react_agent(llm, tools, prompt=SystemMessage(content=system_prompt))

    try:
        inputs = {"messages": [("user", "Please analyse the message and give your JSON verdict.")]}

        logger.info(f"[AGENT 3: AUDITOR] ReAct Analysis Starting for: '{raw_text[:60]}'")

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
                        logger.info(f"[AGENT 3: TOOL CALL] {tc['name']} | args={tc['args']}")

                # ── Tool result ───────────────────────────────
                elif msg.type == "tool":
                    preview   = str(msg.content).replace('\n', ' | ')[:140]
                    tool_name = msg.name if hasattr(msg, "name") else "Tool"
                    logger.info(f"[AGENT 3: TOOL RESULT] {tool_name} → {preview[:120]}...")

                # ── LLM reasoning text (chain-of-thought) ─────
                elif (
                    hasattr(msg, "content") and msg.content
                    and msg.type == "ai"
                    and not getattr(msg, "tool_calls", None)
                ):
                    full_text = str(msg.content).strip()
                    if full_text:
                        thinking = full_text.split("```")[0].strip()
                        if thinking:
                            logger.info(f"[AGENT 3: REASONING] {thinking[:280]}")
                        else:
                            logger.info(f"[AGENT 3: REASONING] {full_text[:250]}")

        # ── Parse the JSON verdict ────────────────────────────
        import re
        output = final_message.content if final_message else ""

        if "```json" in output:
            json_str = output.split("```json")[1].split("```")[0].strip()
        elif "```" in output:
            json_str = output.split("```")[1].strip()
        else:
            json_str = output.strip()

        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', output, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except json.JSONDecodeError:
                    parsed = {"decision": "HUMAN_REVIEW", "category": primary_class, "explanation": "JSON Parse Fallback Error"}
            else:
                parsed = {"decision": "HUMAN_REVIEW", "category": primary_class, "explanation": "No JSON found in response"}

        valid  = {"ESCALATE", "BLOCK", "WARN", "ALLOW", "HUMAN_REVIEW"}
        if parsed.get("decision", "").upper() not in valid:
            parsed["decision"] = "HUMAN_REVIEW"

        decision = parsed.get("decision", "?")
        category = parsed.get("category", "?")
        expl     = parsed.get("explanation", "")

        logger.info(
            f"[AGENT 3: VERDICT] Decision={decision} | "
            f"Category={category} | Explanation={expl}"
        )
        return parsed

    except Exception as e:
        logger.error(f"[AEGIS] ReAct Agent Error: {e}")
        return {"decision": "HUMAN_REVIEW", "category": primary_class, "explanation": "ReAct agent failed."}
