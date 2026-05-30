import datetime
from django.utils import timezone
from moderation.models import ModerationResult, BehavioralSnapshot

FEATURE_NAMES = [
    "block_ratio",
    "avg_toxicity_score",
    "escalation_count",
    "night_activity_ratio",
    "unique_targets_count",
    
    "message_frequency_1h",
    "avg_message_length",
    "correction_rate",
    "days_since_first_seen",
    "burst_count_24h",
    "max_toxicity_24h",
    
    "toxicity_trend_slope",
    "current_hour_score",
    "risk_trajectory_delta"
]

def extract_features(profile, current_m1_score=0.0):
    """
    Extracts the 14-element behavioral feature vector for the Random Forest.
    Returns: list of floats
    """
    now = timezone.now()
    
    # Tier 1 - Direct from profile
    f1 = float(profile.block_ratio)
    f2 = float(profile.average_toxicity_score)
    f3 = float(profile.escalation_count)
    f4 = float(profile.night_activity_ratio)
    f5 = float(profile.unique_targets_count)
    
    # Tier 2 - Stored in profile
    f6 = float(profile.message_frequency_1h)
    f7 = float(profile.avg_message_length)
    f8 = float(profile.correction_rate)
    
    days_since_first = (now - profile.first_seen_at).days if profile.first_seen_at else 0
    f9 = float(days_since_first)
    
    f10 = float(profile.burst_count_24h)
    f11 = float(max(profile.max_toxicity_24h, current_m1_score))
    
    # Tier 3 - Computed at prediction time
    # 1. toxicity_trend_slope (last 10 messages)
    recent_qs = ModerationResult.objects.filter(sender_jid=profile.user_jid).order_by('-created_at')[:10]
    scores = [r.toxicity_score for r in recent_qs]
    if len(scores) < 2:
        f12 = 0.0
    else:
        scores.reverse()  # chronological
        # Simple slope: compare second half to first half
        mid = len(scores) // 2
        first_half = sum(scores[:mid]) / max(1, mid)
        second_half = sum(scores[mid:]) / max(1, len(scores) - mid)
        f12 = float(second_half - first_half)
        
    # 2. current_hour_score
    curr_hour = now.hour
    if curr_hour >= 22 or curr_hour <= 6:
        f13 = 1.0
    elif 6 < curr_hour <= 8:
        f13 = 0.5
    else:
        f13 = 0.0
        
    # 3. risk_trajectory_delta (current vs 7 days ago)
    seven_days_ago = now.date() - datetime.timedelta(days=7)
    past_snapshot = BehavioralSnapshot.objects.filter(profile=profile, date_snapshot__lte=seven_days_ago).first()
    past_risk = past_snapshot.risk_score_snapshot if past_snapshot else profile.risk_score
    f14 = float(profile.risk_score - past_risk)

    return [f1, f2, f3, f4, f5, f6, f7, f8, f9, f10, f11, f12, f13, f14]
