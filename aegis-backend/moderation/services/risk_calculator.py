"""
Single-source risk level calculation for AEGIS.

Previously duplicated at 4 locations in views.py:
  - views.py:552-565 (admin_user_list)
  - views.py:1000-1010 (admin_risk_profiles)
  - views.py:1234-1242 (parent_dashboard_stats)
  - views.py:1642-1659 (parent_risk_profile)

Extracted during Phase 2 audit refactoring (2026-04-21).
"""


def calculate_risk_level(blocked_count: int) -> tuple[str, float]:
    """
    Determines risk level and score based on blocked/harmful message count.

    Thresholds:
        >= 10 → CRITICAL (0.85)
        >=  5 → HIGH     (0.65)
        >=  1 → MEDIUM   (0.35)
           0 → LOW      (0.10)

    Returns:
        (risk_level, risk_score) tuple, e.g. ('HIGH', 0.65)
    """
    if blocked_count >= 10:
        return 'CRITICAL', 0.85
    elif blocked_count >= 5:
        return 'HIGH', 0.65
    elif blocked_count >= 1:
        return 'MEDIUM', 0.35
    return 'LOW', 0.10


def escalate_risk_by_actor(base_level: str, max_actor_risk: float) -> str:
    """
    Escalates risk level if the child is communicating with a high-risk actor.
    Used by parent_dashboard_stats and parent_risk_profile.

    Args:
        base_level: The risk level calculated from blocked message count.
        max_actor_risk: The highest risk_score among threat actors contacting this child.

    Returns:
        Potentially escalated risk level string.
    """
    if max_actor_risk >= 0.8 and base_level in ['LOW', 'MEDIUM']:
        return 'HIGH'
    elif max_actor_risk >= 0.3 and base_level == 'LOW':
        return 'MEDIUM'
    return base_level


def risk_score_from_level(risk_level: str, blocked_count: int = 0) -> float:
    """
    Computes a slightly dynamic risk score based on the risk level
    and actual blocked count. Used by parent_risk_profile.

    Returns:
        A float between 0.0 and 1.0.
    """
    if risk_level == 'CRITICAL':
        score = 0.88 + min(0.12, blocked_count * 0.01)
    elif risk_level == 'HIGH':
        score = 0.65 + min(0.2, blocked_count * 0.02)
    elif risk_level == 'MEDIUM':
        score = 0.35 + min(0.25, blocked_count * 0.02)
    else:
        score = 0.10
    return min(1.0, round(score, 2))
