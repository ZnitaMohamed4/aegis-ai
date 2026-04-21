"""
AGENT 4: The Profiler — Digital Twin behavioral risk assessment.

Calculates behavioral risk score using a Random Forest model (with graceful
fallback to a formula) and updates the sender's Digital Twin profile.

Extracted from graph.py during Phase 2 audit refactoring (2026-04-21).
"""
import os
import logging
import datetime

import joblib
import numpy as np
from django.utils import timezone

from .state import ModerationState
from ml_pipeline.feature_extractor import extract_features, FEATURE_NAMES

logger = logging.getLogger(__name__)

# ── Load Random Forest Model (once at startup) ──────────────
_RF_MODEL = None
_RF_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models", "risk_classifier.joblib"
)
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


def profiler_node(state: ModerationState) -> dict:
    """
    AGENT 4: Profiler 
    Calculates behavioral risk score and updates the Digital Twin profile.
    """
    from moderation.models import UserBehaviorProfile, ModerationResult

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
    
    # --- 3. Terminal Logging ---
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
