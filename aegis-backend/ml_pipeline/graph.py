import hashlib
import os
import logging
import datetime
import joblib
import numpy as np
from datetime import timedelta
from django.utils import timezone
from typing import TypedDict, Optional
from .inference import run_pipeline, run_pipeline_stub
from .llm_agent import analyze_grey_zone
from .feature_extractor import extract_features, FEATURE_NAMES
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from moderation.semantic_cache import search_semantic_cache, add_to_semantic_cache
from moderation.models import (
    UserBehaviorProfile, ModerationResult, SecurityAlert,
    HarassmentCategory, Conversation, Message, MonitoredChild
)
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

# ── Load Random Forest Model (once at startup) ──────────────
_RF_MODEL = None
_RF_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "risk_classifier.joblib")
try:
    if os.path.exists(_RF_MODEL_PATH):
        _bundle = joblib.load(_RF_MODEL_PATH)
        _RF_MODEL = _bundle["model"]
        logger.info(f"[AGENT 4] ✅ Random Forest loaded (OOB={_bundle['oob_score']:.3f}, classes={_bundle['classes']})")
    else:
        logger.warning(f"[AGENT 4] ⚠️ RF model not found at {_RF_MODEL_PATH} — using fallback formula")
except Exception as e:
    logger.error(f"[AGENT 4] ❌ Failed to load RF model: {e} — using fallback formula")

# ── ANSI colors for Agent 4 logging ──────────────────────────
C4_BLUE   = "\033[94m"
C4_GREEN  = "\033[92m"
C4_YELLOW = "\033[93m"
C4_RED    = "\033[91m"
C4_MAGENTA= "\033[95m"
C4_CYAN   = "\033[96m"
C4_RESET  = "\033[0m"
C4_DIVIDER = "═" * 62

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

        # --- Signal 4: Threat Keyword (CURRENT message only) ---
        # We only check the MOST RECENT message for threat phrases.
        # Previously this checked the entire 10-min history as one blob,
        # which caused innocent follow-up messages (e.g., "gg bro") to
        # inherit keyword matches from earlier aggressive messages.
        latest_msg = recent[-1].raw_text.lower() if recent else ""
        keyword_hit = any(phrase in latest_msg for phrase in _THREAT_PHRASES)
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
    sender_phone_jid: Optional[str]  # [FIX] Phone-based JID from remoteJidAlt (for block/archive API calls)
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
    # NOTE: Semantic cache is temporarily disabled for slow-burn pattern testing.
    # See docs/DISABLED_FEATURES.md for the original cache lookup/save logic.
    escalation_risk = state.get("escalation_risk", 0.0)
    is_escalation = escalation_risk >= ESCALATION_AUDIT_THRESHOLD
    cached_response = None

    if cached_response:
        llm_response = cached_response
    else:
        # 2. CALL THE LLM!
        llm_response = analyze_grey_zone(
            raw_text, check_class, check_conf, m1_score,
            state["sender_jid"], state["instance_name"]
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
    ml_corrected = False

    if ml_original_decision and ml_original_decision != new_decision:
        # Map decisions to severity to distinguish between catching a predator vs saving a gamer
        severity = {"ALLOW": 0, "WARN": 1, "HUMAN_REVIEW": 2, "BLOCK": 3, "ESCALATE": 4}
        orig_sev = severity.get(ml_original_decision, 0)
        new_sev = severity.get(new_decision, 0)
        
        # Only punish the user's Twin profile (ml_corrected=True) if Agent 3 UPSCALED the severity (caught a sneaky predator).
        # Less severe overrides (saving a gamer from a false positive) will NOT increase correction_rate.
        if new_sev > orig_sev:
            ml_corrected = True

        logger.warning(
            f"[AGENT 3: CORRECTION] ⚠️ ML said '{ml_original_decision}' ({ml_original_class}) -> "
            f"Auditor overrode to '{new_decision}' ({new_class}). "
            f"Profile Punished? {'YES' if ml_corrected else 'NO (Gamer/Context override)'}"
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
    instance_name = state.get("instance_name", "")
    ml_corrected = state.get("ml_corrected", False)
    
    # ── Agent 3 Correction: Trust the Auditor, not raw ML ────
    # If Agent 3 overrode the ML decision, M1 was WRONG.
    # The raw M1 score stays in ModerationResult (for retraining),
    # but the Digital Twin's behavioral memory uses the CORRECTED
    # reality — what Agent 3 actually decided.
    #
    # TRUTH TABLE:
    #   M1=HIGH + Agent3→ALLOW   = M1 overreacted     → 0.05 (safe)
    #   M1=HIGH + Agent3→WARN    = Agent3 downgraded  → 0.40 (mild)
    #   M1=LOW  + Agent3→BLOCK   = M1 MISSED a threat → 0.85 (dangerous)
    #   M1=LOW  + Agent3→ESCALATE= M1 SEVERELY missed → 0.95 (critical)
    #   No correction            = M1 was right       → m1_score (as-is)
    
    if state.get("llm_triggered"):
        CORRECTED_SCORES = {
            "ALLOW":    0.05,   # Agent 3 says safe → clean signal
            "WARN":     0.40,   # Agent 3 says mild concern
            "HUMAN_REVIEW": 0.50, # Agent 3 says borderline
            "BLOCK":    0.85,   # Agent 3 caught a threat
            "ESCALATE": 0.95,   # Agent 3 caught a SEVERE threat
        }
        effective_toxicity = CORRECTED_SCORES.get(decision, m1_score)
    else:
        effective_toxicity = m1_score
    
    # Fetch the exact user from DB
    profile, _ = UserBehaviorProfile.objects.get_or_create(user_jid=sender_jid)
    
    # --- 1. Update Digital Twin Base Stats ---
    # Total messages
    prev_total = profile.total_messages_sent
    profile.total_messages_sent += 1
    
    # Toxicity (EMA) — uses CORRECTED score, not raw M1
    alpha = 0.3 
    profile.average_toxicity_score = (profile.average_toxicity_score * (1 - alpha)) + (effective_toxicity * alpha)
    
    # Block & Escalation counters
    if decision != "ALLOW":
        profile.total_blocked_messages_sent += 1
    if decision == "ESCALATE":
        profile.escalation_count += 1
        
    # Block ratio
    profile.block_ratio = profile.total_blocked_messages_sent / max(1, profile.total_messages_sent)
    
    # Night activity ratio (22h to 06h)
    current_hour = timezone.now().hour
    is_night = 1.0 if (current_hour >= 22 or current_hour <= 6) else 0.0
    prev_night_msgs = profile.night_activity_ratio * prev_total
    profile.night_activity_ratio = (prev_night_msgs + is_night) / profile.total_messages_sent
    
    # Unique targets count
    from moderation.models import ModerationResult
    known_targets = set(ModerationResult.objects.filter(sender_jid=sender_jid).values_list('instance_name', flat=True))
    if instance_name:
        known_targets.add(instance_name)
    profile.unique_targets_count = len(known_targets)
    
    # --- Tier 2 Features ---
    # Agent 3 overrides
    if state.get("llm_triggered"):
        profile.llm_triggers_total += 1
    if state.get("ml_corrected"):
        profile.ml_corrections_total += 1
    profile.correction_rate = profile.ml_corrections_total / max(1, profile.llm_triggers_total)
    
    # Message length EMA
    raw_text = state.get("raw_text", "")
    msg_len = len(raw_text)
    profile.avg_message_length = (profile.avg_message_length * 0.9) + (msg_len * 0.1)
    
    # Time-based metrics (1h, 24h windows)
    import datetime
    now = timezone.now()
    window_24h = now - datetime.timedelta(hours=24)
    recent_24h = ModerationResult.objects.filter(sender_jid=sender_jid, created_at__gte=window_24h).values_list('toxicity_score', 'created_at')
    
    past_max_tox = max([tox for tox, dt in recent_24h], default=0.0)
    profile.max_toxicity_24h = max(past_max_tox, effective_toxicity)
    
    window_1h = now - datetime.timedelta(hours=1)
    profile.message_frequency_1h = sum(1 for tox, dt in recent_24h if dt >= window_1h) + 1
    
    window_10m = now - datetime.timedelta(minutes=10)
    msgs_10m = sum(1 for tox, dt in recent_24h if dt >= window_10m) + 1
    if msgs_10m == 5:  # Trigger exactly once per burst episode
        profile.burst_count_24h += 1
    
    # --- 2. Risk Score: RF Model or Fallback Formula ---
    prediction_method = "fallback"
    rf_confidence = 0.0
    rf_probas = {}
    
    if _RF_MODEL is not None:
        try:
            features = extract_features(profile, current_m1_score=m1_score)
            features_array = np.array(features).reshape(1, -1)
            
            # Predict risk class
            predicted_class = _RF_MODEL.predict(features_array)[0]
            probas = _RF_MODEL.predict_proba(features_array)[0]
            class_labels = _RF_MODEL.classes_
            
            # Build probability map
            rf_probas = {label: float(prob) for label, prob in zip(class_labels, probas)}
            rf_confidence = max(probas)
            
            # Map class to risk_score (use the probability of the predicted class)
            risk_score_map = {"LOW": 0.1, "MEDIUM": 0.4, "HIGH": 0.7, "CRITICAL": 0.9}
            base_score = risk_score_map.get(predicted_class, 0.5)
            # Blend: base_score weighted by confidence
            profile.risk_score = round(base_score * rf_confidence + (1 - rf_confidence) * 0.3, 4)
            profile.risk_level = predicted_class
            prediction_method = "random_forest"
            
        except Exception as e:
            logger.error(f"[AGENT 4] RF prediction failed: {e}. Using fallback.")
            prediction_method = "fallback"
    
    if prediction_method == "fallback":
        # Old hardcoded formula (graceful degradation)
        volume_penalty = profile.total_blocked_messages_sent * 0.08
        ratio_penalty = profile.block_ratio * 0.20
        toxicity_penalty = profile.average_toxicity_score * 0.30
        raw_risk = volume_penalty + ratio_penalty + toxicity_penalty
        profile.risk_score = min(1.0, max(0.0, raw_risk))
        
        if profile.risk_score >= 0.8:
            profile.risk_level = 'CRITICAL'
        elif profile.risk_score >= 0.5:
            profile.risk_level = 'HIGH'
        elif profile.risk_score >= 0.25:
            profile.risk_level = 'MEDIUM'
        else:
            profile.risk_level = 'LOW'
        
    profile.save()
    
    # --- 3. Terminal Logging (Step 7) ---
    risk_color = C4_RED if profile.risk_level in ('CRITICAL','HIGH') else C4_YELLOW if profile.risk_level == 'MEDIUM' else C4_GREEN
    archetype = {"LOW": "Normal User", "MEDIUM": "Troll Pattern", "HIGH": "Bully Pattern", "CRITICAL": "Groomer Pattern"}.get(profile.risk_level, "Unknown")
    
    print(f"\n{C4_DIVIDER}")
    print(f"  📊 {C4_BLUE}[AGENT 4: PROFILER]{C4_RESET} Digital Twin Update")
    print(C4_DIVIDER)
    print(f"  👤 Sender:     {sender_jid}")
    print(f"  📈 Method:     {C4_CYAN}{prediction_method.upper()}{C4_RESET}")
    print(f"  🧠 Prediction: {risk_color}{profile.risk_level}{C4_RESET} ({archetype}) — score {profile.risk_score:.3f}")
    if rf_probas:
        proba_str = " | ".join(f"{k}={v:.2f}" for k, v in sorted(rf_probas.items()))
        print(f"  🎲 Probas:     {proba_str}")
    print(f"  📉 Features:   night={profile.night_activity_ratio:.2f}, targets={profile.unique_targets_count}, correction={profile.correction_rate:.2f}, days={int((timezone.now() - profile.first_seen_at).days) if profile.first_seen_at else 0}")
    print(C4_DIVIDER + "\n")
    
    logger.info(
        f"[AGENT 4: PROFILER] method={prediction_method} | "
        f"risk={profile.risk_level} ({profile.risk_score:.3f}) | "
        f"archetype={archetype}"
    )
    
    # Update the LangGraph state
    return {
        "risk_score": profile.risk_score,
        "risk_level": profile.risk_level
    }

# =====================================================================
# 5. THE ENFORCER AGENT
# =====================================================================
# ANSI colors for Agent 5 logging
C5_PURPLE = "\033[95m"
C5_GREEN  = "\033[92m"
C5_RED    = "\033[91m"

def enforcer_node(state: ModerationState) -> dict:
    """
    AGENT 5: The Enforcer
    Executes the final enforcement action based on the pipeline's decision.

    Responsibilities:
      1. Persist the ModerationResult + SecurityAlert to PostgreSQL
      2. Create Conversation + Message records for the admin dashboard
      3. Broadcast real-time events via Django Channels (WebSocket)
      4. Execute WhatsApp enforcement actions:
         - DELETE harmful messages (BLOCK/ESCALATE)
         - REACT with 🚨 emoji on flagged messages
         - SEND warning auto-reply to the sender
         - NOTIFY parent on critical escalations

    This node was previously inline in views.py. Moving it into the
    LangGraph pipeline enables interrupt_before=["enforcer"] for
    human-in-the-loop moderation in future phases.
    """
    # Lazy imports to avoid circular dependencies at module load time
    from moderation.evolution_api import (
        delete_message_from_whatsapp, send_aegis_warning,
        send_aegis_reaction, send_aegis_presence, send_parent_alert,
        block_contact, archive_chat
    )
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    # Extract state
    decision = state.get("decision", "ALLOW")
    raw_text = state.get("raw_text", "")
    sender_jid = state.get("sender_jid", "")
    instance_name = state.get("instance_name", "")
    message_key_id = state.get("message_key_id")
    push_name = state.get("push_name")
    is_from_me = state.get("is_from_me", False)
    m1_score = state.get("m1_score", 0.0)
    primary_class = state.get("primary_class", "safe")
    m2_confidence = state.get("m2_confidence")
    llm_triggered = state.get("llm_triggered", False)
    llm_explanation = state.get("llm_explanation", "")
    ml_corrected = state.get("ml_corrected", False)
    ml_original_decision = state.get("ml_original_decision")
    ml_original_class = state.get("ml_original_class")

    enforcement_actions = []
    alert_severity = None

    # ── 1. Save ModerationResult to PostgreSQL ───────────────────
    is_human_review = decision == 'HUMAN_REVIEW'

    # Link to HarassmentCategory reference table
    harassment_category = None
    try:
        harassment_category = HarassmentCategory.objects.get(code=primary_class)
    except HarassmentCategory.DoesNotExist:
        pass  # Unknown category — leave FK null

    moderation = ModerationResult.objects.create(
        instance_name=instance_name,
        sender_jid=sender_jid,
        sender_name=push_name,
        is_from_me=is_from_me,
        raw_text=raw_text,
        normalized_text=state.get("normalized_text", ""),
        message_key_id=message_key_id,
        primary_class=primary_class,
        category=harassment_category,
        toxicity_score=m1_score,
        confidence_score=m2_confidence,
        final_score=m1_score,
        decision=decision,
        llm_triggered=llm_triggered,
        llm_explanation=llm_explanation,
        flagged_for_review=is_human_review,
        behavioral_risk_score=state.get("risk_score", 0.0),
        # 🔁 Retraining fields: preserve what the ML said before Agent 3 corrected it
        ml_corrected=ml_corrected,
        ml_original_decision=ml_original_decision,
        ml_original_class=ml_original_class,
    )
    enforcement_actions.append("persist")

    # ── 2. Create Conversation + Message records ─────────────────
    child = None
    try:
        child = MonitoredChild.objects.filter(
            parent__evolution_instance_name=instance_name,
        ).first()
    except Exception:
        pass

    conversation = None
    try:
        conversation, _ = Conversation.objects.get_or_create(
            contact_jid=sender_jid,
            child=child,
            defaults={
                'contact_name': push_name or '',
                'platform': 'whatsapp',
            }
        )
        if push_name and push_name != conversation.contact_name:
            conversation.contact_name = push_name
            conversation.save(update_fields=['contact_name', 'updated_at'])
    except Exception as e:
        logger.warning(f"[AGENT 5: ENFORCER] Could not create Conversation: {e}")

    try:
        Message.objects.create(
            conversation=conversation,
            content=raw_text,
            content_hash=hashlib.sha256(raw_text.encode('utf-8')).hexdigest(),
            language=state.get('detected_language', 'unknown') or 'unknown',
            is_blocked=decision in ('BLOCK', 'ESCALATE'),
            is_displayed=decision not in ('BLOCK', 'ESCALATE'),
            platform='whatsapp',
            platform_message_id=message_key_id or '',
            sender_jid=sender_jid,
            moderation_result=moderation,
        )
    except Exception as e:
        logger.warning(f"[AGENT 5: ENFORCER] Could not create Message: {e}")

    # ── 3. Broadcast via WebSocket ───────────────────────────────
    def _broadcast(mod, alerte=None):
        """Push real-time event to Angular Dashboard via Django Channels."""
        channel_layer = get_channel_layer()
        payload = {
            "id": str(alerte.id) if alerte else str(mod.id),
            "type": "alert" if alerte else "log",
            "sender": mod.sender_jid,
            "text": mod.raw_text,
            "decision": mod.decision.lower(),
            "primary_class": mod.primary_class or 'safe',
            "language": getattr(mod, 'language', 'unknown'),
            "m1_score": round(mod.toxicity_score, 4),
            "m2_confidence": round(mod.confidence_score, 4) if mod.confidence_score else None,
            "llm_triggered": mod.llm_triggered,
            "llm_explanation": mod.llm_explanation,
            "severity": alerte.severity if alerte else "none",
            "timestamp": (alerte.sent_at if alerte else mod.created_at).isoformat(),
        }
        try:
            async_to_sync(channel_layer.group_send)(
                "alerts",
                {"type": "alert.message", "data": payload}
            )
        except Exception as e:
            logger.warning(f"[AGENT 5: ENFORCER] WS broadcast failed: {e}")

    # ── 4. Enforce Decision ──────────────────────────────────────
    if decision != 'ALLOW':
        severity_map = {
            'WARN': 'medium',
            'REVISE': 'high',
            'BLOCK': 'high',
            'ESCALATE': 'critical',
            'HUMAN_REVIEW': 'high',
        }
        alert_severity = severity_map.get(decision, 'medium')

        alerte = SecurityAlert.objects.create(
            moderation_result=moderation,
            severity=alert_severity,
            message_preview=raw_text[:200]
        )
        enforcement_actions.append("alert")

        _broadcast(moderation, alerte)
        enforcement_actions.append("broadcast")

        # ACTIVE SHIELD: Delete harmful messages from WhatsApp
        if decision in ['BLOCK', 'ESCALATE'] and is_from_me:
            if message_key_id:
                delete_message_from_whatsapp(instance_name, message_key_id, sender_jid, True)
                enforcement_actions.append("delete")

        # AUTO-REPLY: Tag + warn (not for HUMAN_REVIEW — wait for admin)
        if decision in ['BLOCK', 'ESCALATE', 'WARN', 'REVISE']:
            if message_key_id:
                react_emoji_map = {'ESCALATE': '🚨', 'BLOCK': '🛑', 'WARN': '⚠️', 'REVISE': '👀'}
                chosen_emoji = react_emoji_map.get(decision, '⚠️')
                send_aegis_reaction(instance_name, sender_jid, message_key_id, is_from_me, chosen_emoji)
                enforcement_actions.append("react")

            # [FIX] Resolve phone JID BEFORE sending the warning, so the warning's
            # remoteJid in Prisma matches the JID we'll use in the archive payload.
            phone_jid = state.get("sender_phone_jid") or sender_jid
            
            send_aegis_presence(instance_name, phone_jid, "composing", 1500)
            warning_result = send_aegis_warning(instance_name, phone_jid, primary_class, is_from_me, decision, message_key_id)
            enforcement_actions.append("warn")
            
            # Extract exact warning message key ID, timestamp, and full node for archive anchor
            warning_msg_key_id = None
            exact_warning_ts = None
            full_warning_message = None
            
            if isinstance(warning_result, tuple) and len(warning_result) == 3:
                warning_msg_key_id, exact_warning_ts, full_warning_message = warning_result
                logger.info(f"[AGENT 5: ENFORCER] 📌 Captured exact warning anchor (full node): id={warning_msg_key_id}, ts={exact_warning_ts}")
                
                # ── EXTRACT LID FROM WARNING RESPONSE ───────────────────────
                # The sendText response contextInfo contains the real @lid identity
                # This is the ONLY place Evolution API exposes it reliably
                warning_context = full_warning_message.get("contextInfo", {}) or {}
                lid_from_warning = (
                    warning_context.get("participant", "") or
                    warning_context.get("remoteJid", "")
                )
                if lid_from_warning and "@lid" in lid_from_warning:
                    # Override sender_jid in state with the real LID
                    state["sender_jid"] = lid_from_warning
                    logger.info(f"[AGENT 5: ENFORCER] ✅ LID extracted from warning contextInfo: {lid_from_warning}")
                # ────────────────────────────────────────────────────────────
                
            elif isinstance(warning_result, tuple) and len(warning_result) == 2:
                warning_msg_key_id, exact_warning_ts = warning_result
                logger.info(f"[AGENT 5: ENFORCER] 📌 Captured exact warning anchor (stripped node): id={warning_msg_key_id}, ts={exact_warning_ts}")
            elif isinstance(warning_result, str) and len(warning_result) > 5:
                # Fallback for old return type
                warning_msg_key_id = warning_result

            # PARENT ALERT: Notify parent on critical escalations
            if decision == 'ESCALATE' and child and child.parent and child.parent.user.phone_number:
                send_parent_alert(instance_name, child.parent.user.phone_number, child.full_name, primary_class, raw_text)
                enforcement_actions.append("parent_alert")
                
            # 🛡️ INCOMING ATTACKER NEUTRALIZATION (Flashbang + Archive + Block)
            if decision in ['BLOCK', 'ESCALATE'] and not is_from_me:
                # Pause 5 seconds to let Evolution API's Prisma database fully commit
                # and to account for any reconnect loops Baileys might be in.
                import time; time.sleep(5.0)
                
                # ✅ Archive the chat using the WARNING message as the lastMessage anchor.
                # `phone_jid` (@s.whatsapp.net) is required for lastMessage anchor (what Prisma stored).
                # `sender_jid` (@lid) is required for the main `chat` target (what Baileys uses internally).
                lid_jid = state.get("sender_jid")
                
                logger.info(
                    f"[AGENT 5: ENFORCER] 🗃️ Triggering archive: "
                    f"lid={lid_jid} | phone={phone_jid} | "
                    f"has_full_msg={full_warning_message is not None}"
                )
                
                # 📦 Archive + Block are disabled due to Baileys protocol instability.
                # See docs/DISABLED_FEATURES.md for the original code.
                logger.info(
                    f"[AGENT 5: ENFORCER] ⚠️ Archive/Block disabled for {phone_jid} "
                    f"(decision={decision}). See DISABLED_FEATURES.md."
                )
    else:
        # Safe message — still broadcast for the Activity Feed
        _broadcast(moderation)
        enforcement_actions.append("broadcast")

    # ── 5. Terminal Logging ──────────────────────────────────────
    action_icon = "🟢" if decision == "ALLOW" else "🔴"
    logger.info(
        f"[AGENT 5: ENFORCER] {action_icon} decision={decision} | "
        f"actions={enforcement_actions} | moderation_id={moderation.id}"
    )

    return {
        "moderation_id": str(moderation.id),
        "alert_severity": alert_severity,
        "enforcement_actions": enforcement_actions,
    }

# =====================================================================
# 6. THE GRAPH WIRING (Orchestrator)
# =====================================================================
# 1. Initialize the graph with our State definition
workflow = StateGraph(ModerationState)
# 2. Add our Agent nodes
workflow.add_node("pipeline", ml_pipeline_node)
workflow.add_node("auditor", auditor_node)
workflow.add_node("profiler", profiler_node)
workflow.add_node("enforcer", enforcer_node)
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
workflow.add_edge("profiler", "enforcer")    # Agent 4 → Agent 5
workflow.add_edge("enforcer", END)            # Agent 5 ends the graph
# 5. Compile it into an executable app
aegis_graph = workflow.compile()