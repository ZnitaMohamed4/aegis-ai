import os
import logging
from datetime import timedelta
from django.utils import timezone
from typing import TypedDict, Optional
from .inference import run_pipeline, run_pipeline_stub
from .llm_agent import analyze_grey_zone
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from moderation.semantic_cache import search_semantic_cache, add_to_semantic_cache
from moderation.models import UserBehaviorProfile
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

SHADOW_LOW = float(os.getenv('AEGIS_SHADOW_LOW', '0.12'))
SHADOW_HIGH = float(os.getenv('AEGIS_SHADOW_HIGH', '0.30'))
AGENT3_CONFIDENCE_THRESHOLD = float(os.getenv('AEGIS_LLM_THRESHOLD', '0.75'))
ESCALATION_AUDIT_THRESHOLD = float(os.getenv('AEGIS_ESCALATION_THRESHOLD', '0.40'))

# Threat phrases that signal real-world intent even without high toxicity
_THREAT_PHRASES = [
    "pay for this", "gonna get you", "you'll regret", "watch your back",
    "find you", "after school", "waiting for you", "make you sorry",
    "you're dead", "come for you", "better run",
]


def compute_escalation_risk(sender_jid: str, instance_name: str, current_m1: float) -> tuple[float, str]:
    """
    Multi-dimensional Behavioral Escalation Gate.
    Scores 4 independent signals and returns (escalation_score, reason).

    Signals:
      Burst Rate   (0.35) — messages sent in the last 10 minutes
      Toxicity Trend (0.30) — are recent messages getting MORE toxic?
      Profiler Risk  (0.20) — sender's existing behavioral risk score
      Threat Keyword (0.15) — does any recent message contain known threat phrases?
    """
    from moderation.models import ModerationResult
    try:
        window = timezone.now() - timedelta(minutes=10)
        recent_qs = ModerationResult.objects.filter(
            sender_jid=sender_jid,
            instance_name=instance_name,
            created_at__gte=window,
            is_from_me=False
        ).order_by('created_at')

        recent = list(recent_qs)
        msg_count = len(recent)

        if msg_count == 0:
            return 0.0, ""

        # --- Signal 1: Burst Rate ---
        # 5+ messages in 10min = max score
        burst_score = min(1.0, msg_count / 5.0) * 0.35

        # --- Signal 2: Toxicity Trend ---
        # Is the average toxicity of recent messages rising?
        if msg_count >= 2:
            scores = [r.toxicity_score for r in recent]
            first_half_avg = sum(scores[:len(scores)//2]) / max(1, len(scores)//2)
            second_half_avg = sum(scores[len(scores)//2:]) / max(1, len(scores) - len(scores)//2)
            trend = max(0.0, second_half_avg - first_half_avg)  # positive = rising
            trend_score = min(1.0, trend * 3.0) * 0.30  # amplify small rises
        else:
            trend_score = current_m1 * 0.15  # single message fallback

        # --- Signal 3: Profiler Risk Score ---
        try:
            profile = UserBehaviorProfile.objects.get(user_jid=sender_jid)
            risk_score = profile.risk_score * 0.20
        except UserBehaviorProfile.DoesNotExist:
            risk_score = 0.0

        # --- Signal 4: Threat Keyword in Recent History ---
        all_text = " ".join(r.raw_text.lower() for r in recent)
        keyword_hit = any(phrase in all_text for phrase in _THREAT_PHRASES)
        keyword_score = 0.15 if keyword_hit else 0.0

        total = burst_score + trend_score + risk_score + keyword_score

        reason_parts = []
        if burst_score > 0.14:  reason_parts.append(f"burst={msg_count}msgs/10min")
        if trend_score > 0.08:  reason_parts.append("rising-toxicity")
        if risk_score > 0.10:   reason_parts.append(f"risk-profile={profile.risk_score:.2f}")
        if keyword_hit:         reason_parts.append("threat-keyword-detected")

        return round(total, 3), " | ".join(reason_parts)

    except Exception as e:
        logger.warning(f"[ESCALATION GATE] Error computing score: {e}")
        return 0.0, ""

# =====================================================================
# 1. THE STATE
# =====================================================================
# LangGraph works by passing a single dictionary (the State) between nodes.
# Every node (Agent) can read from it and return updates to it.
class ModerationState(TypedDict):
    # INPUTS (Extracted from WhatsApp Webhook)
    raw_text: str
    sender_jid: str
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

# =====================================================================
# 2. OUR ML AGENTS (M1 & M2)
# =====================================================================
def ml_pipeline_node(state: ModerationState) -> dict:
    """
    AGENT 1 & 2: Gatekeeper + Classifier
    """
    raw_text = state["raw_text"]

    # Resolve the correct pipeline at runtime (respects AEGIS_STUB_MODE).
    from django.conf import settings
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
    ml_original_decision = result.decision if needs_audit else None
    ml_original_class = result.primary_class if needs_audit else None

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

# =====================================================================
# 3. THE AUDITOR AGENT
# =====================================================================
def auditor_node(state: ModerationState) -> dict:
    """
    AGENT 3: The Groq Auditor — The Appeals Court.
    Trust-but-Verify: Re-evaluates ALL blocked/warned messages with context.
    Flags any correction for future ML retraining.
    """
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
    cached_response = search_semantic_cache(raw_text)
    
    if cached_response:
        llm_response = cached_response
    else:
        # 2. CALL THE LLM!
        llm_response = analyze_grey_zone(
            raw_text, check_class, check_conf, m1_score,
            state["sender_jid"], state["instance_name"]
        )
        # 3. SAVE KNOWLEDGE
        new_decision = llm_response.get("decision", "REVISE").upper()
        if m1_score > 0.12 or new_decision != "ALLOW":
            add_to_semantic_cache(raw_text, llm_response)
        
    new_decision = llm_response.get("decision", "REVISE").upper()
    new_class = llm_response.get("category", check_class)

    # 🔁 CORRECTION DETECTION: Did Agent 3 override the ML?
    ml_original_decision = state.get("ml_original_decision")
    ml_original_class = state.get("ml_original_class")
    ml_corrected = False

    if ml_original_decision and ml_original_decision != new_decision:
        ml_corrected = True
        logger.warning(
            f"[AGENT 3: CORRECTION] ⚠️  ML said '{ml_original_decision}' ({ml_original_class}) "
            f"but Auditor overrode to '{new_decision}' ({new_class}) "
            f"for message: '{raw_text[:60]}...'"
        )
    
    return {
        "llm_triggered": True,
        "llm_explanation": llm_response.get("explanation", ""),
        "decision": new_decision,
        "primary_class": new_class,
        "shadow_reviewed": is_shadow,
        "ml_corrected": ml_corrected,
    }

# =====================================================================
# 4. THE PROFILER AGENT
# =====================================================================
def profiler_node(state: ModerationState) -> dict:
    """
    AGENT 4: Profiler 
    Calculates behavioral risk score and updates the Digital Twin profile.
    """
    sender_jid = state["sender_jid"]
    m1_score = state.get("m1_score", 0.0)
    decision = state.get("decision", "ALLOW")
    # Fetch the exact user from DB
    profile, _ = UserBehaviorProfile.objects.get_or_create(user_jid=sender_jid)
    
    # 1. Update stats
    profile.total_messages_sent += 1
    alpha = 0.3 
    profile.average_toxicity_score = (profile.average_toxicity_score * (1 - alpha)) + (m1_score * alpha)
    
    if decision != "ALLOW":
        profile.total_blocked_messages_sent += 1
    # 2. Real-world mathematical Risk Score (0.0 to 1.0)
    volume_penalty = profile.total_blocked_messages_sent * 0.08
    blocked_ratio = profile.total_blocked_messages_sent / max(1, profile.total_messages_sent)
    ratio_penalty = blocked_ratio * 0.20
    toxicity_penalty = profile.average_toxicity_score * 0.30
    
    raw_risk = volume_penalty + ratio_penalty + toxicity_penalty
    profile.risk_score = min(1.0, max(0.0, raw_risk))
    
    # 3. Map to Dashboard Levels
    if profile.risk_score >= 0.8:
        profile.risk_level = 'CRITICAL'
    elif profile.risk_score >= 0.5:
        profile.risk_level = 'HIGH'
    elif profile.risk_score >= 0.25:
        profile.risk_level = 'MEDIUM'
    else:
        profile.risk_level = 'LOW'
        
    profile.save()
    
    # Update the LangGraph state
    return {
        "risk_score": profile.risk_score,
        "risk_level": profile.risk_level
    }

# =====================================================================
# 5. THE GRAPH WIRING (Orchestrator)
# =====================================================================
# 1. Initialize the graph with our State definition
workflow = StateGraph(ModerationState)
# 2. Add our Agent nodes
workflow.add_node("pipeline", ml_pipeline_node)
workflow.add_node("auditor", auditor_node)
workflow.add_node("profiler", profiler_node)
# 3. Define the routing logic (Conditional Edges)
def route_after_pipeline(state: ModerationState):
    if state.get("needs_audit", False):
        return "auditor"   # Send to Agent 3
    return "profiler"      # Skip straight to Agent 4
# 4. Wire everything together!
workflow.set_entry_point("pipeline")
workflow.add_conditional_edges(
    "pipeline",
    route_after_pipeline,
    {
        "auditor": "auditor",
        "profiler": "profiler"
    }
)
workflow.add_edge("auditor", "profiler")
workflow.add_edge("profiler", END) # The graph ends after profiling
# 5. Compile it into an executable app
aegis_graph = workflow.compile()