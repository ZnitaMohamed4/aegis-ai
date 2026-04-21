"""
LangGraph State definition and shared constants for the AEGIS multi-agent pipeline.

Extracted from graph.py during Phase 2 audit refactoring (2026-04-21).
"""
import os
from typing import TypedDict, Optional


# ── Shared Thresholds (configurable via .env) ────────────────────────
SHADOW_LOW = float(os.getenv('AEGIS_SHADOW_LOW', '0.12'))
SHADOW_HIGH = float(os.getenv('AEGIS_SHADOW_HIGH', '0.30'))
AGENT3_CONFIDENCE_THRESHOLD = float(os.getenv('AEGIS_LLM_THRESHOLD', '0.75'))
ESCALATION_AUDIT_THRESHOLD = float(os.getenv('AEGIS_ESCALATION_THRESHOLD', '0.40'))

# Threat phrases that signal real-world intent even without high toxicity
THREAT_PHRASES = [
    "pay for this", "gonna get you", "you'll regret", "watch your back",
    "find you", "after school", "waiting for you", "make you sorry",
    "you're dead", "come for you", "better run",
]


# =====================================================================
# THE STATE
# =====================================================================
# LangGraph works by passing a single dictionary (the State) between nodes.
# Every node (Agent) can read from it and return updates to it.
class ModerationState(TypedDict):
    # INPUTS (Extracted from WhatsApp Webhook)
    raw_text: str
    sender_jid: str
    sender_phone_jid: Optional[str]  # Phone-based JID from remoteJidAlt (for block/archive API calls)
    instance_name: str
    message_key_id: Optional[str]
    is_from_me: bool
    push_name: Optional[str]

    # OUTPUTS (Populated by Agents as the graph runs)
    normalized_text: Optional[str]
    m1_score: Optional[float]
    is_harmful: Optional[bool]
    
    primary_class: Optional[str]
    secondary_class: Optional[str]
    m2_confidence: Optional[float]
    needs_audit: Optional[bool]

    # Raw ML decision BEFORE Agent 3 override (for retraining)
    ml_original_decision: Optional[str]
    ml_original_class: Optional[str]
    
    llm_triggered: Optional[bool]
    llm_explanation: Optional[str]
    shadow_reviewed: Optional[bool]
    ml_corrected: Optional[bool]  # 🔁 Did Agent 3 override the ML?
    escalation_risk: Optional[float]   # Behavioral escalation gate score
    escalation_reason: Optional[str]   # Why escalation was triggered

    risk_score: Optional[float]
    risk_level: Optional[str]

    decision: Optional[str] # ALLOW, WARN, BLOCK, ESCALATE, REVISE, HUMAN_REVIEW

    # AGENT 5: ENFORCER outputs
    moderation_id: Optional[str]        # ID of saved ModerationResult
    alert_severity: Optional[str]       # Severity of created SecurityAlert (if any)
    enforcement_actions: Optional[list]  # List of actions taken (e.g., ["delete", "warn", "react"])
