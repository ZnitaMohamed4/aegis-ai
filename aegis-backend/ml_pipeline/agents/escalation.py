"""
Multi-dimensional Behavioral Escalation Gate.

Scores 4 independent signals to determine if a "safe-looking" message
should still be sent to the LLM Auditor (Agent 3) due to behavioral patterns.

Signals:
  Burst Rate     (0.35) — messages sent in the last 10 minutes
  Toxicity Trend (0.30) — are recent messages getting MORE toxic?
  Profiler Risk  (0.20) — sender's existing behavioral risk score
  Threat Keyword (0.15) — does any recent message contain known threat phrases?

Extracted from graph.py during Phase 2 audit refactoring (2026-04-21).
"""
import logging
from datetime import timedelta
from django.utils import timezone

from .state import THREAT_PHRASES

logger = logging.getLogger(__name__)


def compute_escalation_risk(sender_jid: str, instance_name: str, current_m1: float) -> tuple[float, str]:
    """
    Computes a composite escalation risk score for the given sender.

    Returns:
        (escalation_score, reason_string) — score is 0.0–1.0
    """
    from moderation.models import ModerationResult, UserBehaviorProfile
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
        keyword_hit = any(phrase in latest_msg for phrase in THREAT_PHRASES)
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
