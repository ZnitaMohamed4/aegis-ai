"""
AGENT 3: The Groq Auditor — The Appeals Court.

Trust-but-Verify: Re-evaluates ALL blocked/warned messages with context.
Flags any correction for future ML retraining.

Extracted from graph.py during Phase 2 audit refactoring (2026-04-21).
"""
import logging

from .state import ModerationState, ESCALATION_AUDIT_THRESHOLD

logger = logging.getLogger(__name__)


def auditor_node(state: ModerationState) -> dict:
    """
    AGENT 3: The Groq Auditor — The Appeals Court.
    Trust-but-Verify: Re-evaluates ALL blocked/warned messages with context.
    Flags any correction for future ML retraining.
    """
    from ml_pipeline.llm_agent import analyze_grey_zone

    raw_text = state["raw_text"]
    m1_score = state.get("m1_score", 0.0)
    current_decision = state.get("decision", "ALLOW")

    is_shadow = (current_decision == "ALLOW")
    check_class = "safe" if is_shadow else state.get("primary_class", "safe")
    check_conf = 0.99 if is_shadow else state.get("m2_confidence", 0.0)

    # ⚡ SOFT OVERRIDE — Escalation Gate bypass for obvious greetings.
    # The escalation gate can fire on burst rate alone, forcing a costly LLM call
    # even for messages like "yoo" or "fine u". If the message is:
    #   • short (≤3 words) AND
    #   • very low toxicity (M1 < 0.15) AND
    #   • shadow context (ML already said ALLOW)
    # → skip the LLM entirely and fast-path to ALLOW. No tool calls, no Groq API.
    if is_shadow:
        word_count = len(raw_text.strip().split())
        if word_count <= 3 and m1_score < 0.15:
            logger.info(
                f"[AGENT 3: SOFT OVERRIDE] ⚡ '{raw_text}' — greeting in escalation context "
                f"(words={word_count}, M1={m1_score:.3f}). Fast-pathing ALLOW, skipping LLM."
            )
            return {
                "llm_triggered": False,
                "llm_explanation": "Soft override: short low-toxicity message in burst — classified as greeting.",
                "decision": "ALLOW",
                "primary_class": "safe",
                "shadow_reviewed": True,
                "ml_corrected": False,
            }

    # 1. SEMANTIC CACHE LOOKUP
    # NOTE: Semantic cache is temporarily disabled for slow-burn pattern testing.
    # See docs/DISABLED_FEATURES.md for the original cache lookup/save logic.
    escalation_risk = state.get("escalation_risk", 0.0)
    cached_response = None

    if cached_response:
        llm_response = cached_response
    else:
        # 2. CALL THE LLM!
        # Build image context for the LLM if this message has an analyzed image
        image_context = None
        if state.get("image_analyzed"):
            image_context = {
                "nsfw": state.get("image_nsfw", False),
                "nsfw_score": state.get("image_nsfw_score", 0.0),
                "violent": state.get("image_violent", False),
                "violent_score": state.get("image_violent_score", 0.0),
                "ocr_text": state.get("image_ocr_text", ""),
            }

        llm_response = analyze_grey_zone(
            raw_text, check_class, check_conf, m1_score,
            state["sender_jid"], state["instance_name"],
            image_context=image_context
        )
        # 3. SAVE KNOWLEDGE
        # NOTE: Semantic cache save is temporarily disabled.
        # See docs/DISABLED_FEATURES.md for the original logic.
        new_decision = llm_response.get("decision", "REVISE").upper()
        
    new_decision = llm_response.get("decision", "REVISE").upper()
    new_class = llm_response.get("category", check_class)

    # 🔁 SEVERITY-AWARE CORRECTION DETECTION
    ml_original_decision = state.get("ml_original_decision")
    ml_original_class = state.get("ml_original_class")
    upward_corrected = False
    downward_corrected = False

    if ml_original_decision and ml_original_decision != new_decision:
        # Map decisions to severity to distinguish between catching a predator vs saving a gamer
        severity = {"ALLOW": 0, "WARN": 1, "HUMAN_REVIEW": 2, "BLOCK": 3, "ESCALATE": 4}
        orig_sev = severity.get(ml_original_decision, 0)
        new_sev = severity.get(new_decision, 0)
        
        if new_sev > orig_sev:
            upward_corrected = True
        elif new_sev < orig_sev:
            downward_corrected = True

        logger.warning(
            f"[AGENT 3: CORRECTION] ⚠️ ML said '{ml_original_decision}' ({ml_original_class}) -> "
            f"Auditor overrode to '{new_decision}' ({new_class}). "
            f"Upward? {upward_corrected} | Downward? {downward_corrected}"
        )
    
    return {
        "llm_triggered": True,
        "llm_explanation": llm_response.get("explanation", ""),
        "decision": new_decision,
        "primary_class": new_class,
        "shadow_reviewed": is_shadow,
        "upward_corrected": upward_corrected,
        "downward_corrected": downward_corrected,
        "ml_corrected": upward_corrected or downward_corrected,
    }
