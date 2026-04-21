"""
AGENT 1 & 2: Gatekeeper + Classifier

Runs the ML pipeline (M1 toxicity + M2 classification), then evaluates
whether the message needs to be sent to Agent 3 (the Groq Auditor).

Extracted from graph.py during Phase 2 audit refactoring (2026-04-21).
"""
import logging

from .state import (
    ModerationState,
    SHADOW_LOW, SHADOW_HIGH,
    ESCALATION_AUDIT_THRESHOLD,
)
from .escalation import compute_escalation_risk

logger = logging.getLogger(__name__)


def ml_pipeline_node(state: ModerationState) -> dict:
    """
    AGENT 1 & 2: Gatekeeper + Classifier
    """
    raw_text = state["raw_text"]

    # Resolve the correct pipeline at runtime (respects AEGIS_STUB_MODE).
    from django.conf import settings
    from ml_pipeline.inference import run_pipeline, run_pipeline_stub
    _pipeline_fn = run_pipeline_stub if getattr(settings, 'AEGIS_STUB_MODE', False) else run_pipeline
    result = _pipeline_fn(raw_text)
    
    # --- Behavioral Escalation Gate ---
    escalation_risk, escalation_reason = compute_escalation_risk(
        state["sender_jid"], state["instance_name"], result.m1_score
    )

    # Evaluate Auditor Triggers
    needs_audit = False
    audit_reason = ""

    # ✅ TRUST-BUT-VERIFY: ALL non-ALLOW decisions go to Agent 3
    if result.decision != 'ALLOW':
        needs_audit = True
        audit_reason = "ml-flagged"

    # 🚨 ESCALATION GATE: Safe-looking message but behavioral pattern is alarming
    elif escalation_risk >= ESCALATION_AUDIT_THRESHOLD:
        needs_audit = True
        audit_reason = f"escalation-gate({escalation_risk:.2f}): {escalation_reason}"
        logger.warning(
            f"[ESCALATION GATE] 🚨 Triggered for {state['sender_jid']} "
            f"(score={escalation_risk:.2f}): {escalation_reason}"
        )

    # SHADOW REVIEW: Borderline safe messages
    elif result.decision == 'ALLOW' and SHADOW_LOW <= result.m1_score <= SHADOW_HIGH:
        word_count = len(raw_text.strip().split())
        # Short messages (≤3 words) with very low toxicity are almost certainly
        # greetings/filler ("supp", "yoo bro", "haha ok") — skip the expensive LLM call.
        if word_count <= 3 and result.m1_score < 0.15:
            needs_audit = False
        else:
            needs_audit = True
            audit_reason = "shadow-zone"

    # Store the raw ML decision BEFORE any potential Agent 3 override
    ml_original_decision = result.decision
    ml_original_class = result.primary_class

    return {
        "normalized_text": result.normalized_text,
        "m1_score": result.m1_score,
        "is_harmful": result.is_harmful,
        "primary_class": result.primary_class,
        "secondary_class": getattr(result, "secondary_class", None),
        "m2_confidence": result.m2_confidence,
        "decision": result.decision,
        "needs_audit": needs_audit,
        "ml_original_decision": ml_original_decision,
        "ml_original_class": ml_original_class,
        "ml_corrected": False,
        "escalation_risk": escalation_risk,
        "escalation_reason": escalation_reason,
    }
