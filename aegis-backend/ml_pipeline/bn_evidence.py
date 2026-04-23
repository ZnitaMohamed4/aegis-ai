"""
AEGIS Bayesian Profiler — Evidence Collector

Discretizes continuous Digital Twin features into Bayesian Network
modalities (categorical states). Each function maps a raw numerical
value from UserBehaviorProfile → a categorical state for BN inference.

Thresholds are grounded in domain research:
  - O'Connell (2003): Grooming stages model
  - Olweus (1993): Bullying criteria (intent, repetition, power imbalance)
  - NCMEC / DHS: Predator behavioral indicators
"""


# ═══════════════════════════════════════════════════════════════
#  DISCRETIZATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def discretize_stranger(days_since_first_seen: int) -> str:
    """
    Stranger detection: < 14 days = unknown contact.
    Based on O'Connell's finding that grooming friendship-forming
    typically begins within the first 1-2 weeks of contact.
    """
    return "YES" if days_since_first_seen < 14 else "NO"


def discretize_child_initiated(child_initiated: bool) -> str:
    """
    Initiator status.
    If the child initiated the conversation, it's peer-to-peer or safe.
    If the stranger initiated, it's a potential grooming signal.
    """
    return "YES" if child_initiated else "NO"


def discretize_shared_groups(count: int) -> str:
    """
    Shared groups count (schoolyard feature).
    0 = Pure stranger
    1 = Classmate / shared activity
    >1 = Heavy social overlap
    """
    if count == 0:
        return "ZERO"
    elif count == 1:
        return "ONE"
    return "MANY"


def discretize_night_active(night_ratio: float) -> str:
    """
    Night activity level: when parental supervision is lowest.
    DHS identifies late-night contact as a grooming risk factor.
    Night alone is NOT dangerous — only in combination with Stranger=YES.
    """
    if night_ratio < 0.20:
        return "LOW"
    elif night_ratio < 0.50:
        return "MEDIUM"
    return "HIGH"


def discretize_toxicity(avg_toxicity: float) -> str:
    """
    Toxicity level from EMA score.
    CLEAN is actually a grooming signal (NCMEC: "they build trust, not threats").
    MODERATE/SEVERE captures Olweus "intentional harm" for bullying.
    """
    if avg_toxicity < 0.10:
        return "CLEAN"
    elif avg_toxicity < 0.30:
        return "MILD"
    elif avg_toxicity < 0.55:
        return "MODERATE"
    return "SEVERE"


def discretize_upward_correction(upward_rate: float) -> str:
    """
    Rate at which Agent 3 ESCALATES beyond ML decisions.
    High rate = ML is blind to this user's threats = groomer signature.
    (ML says safe, LLM catches grooming subtext)
    """
    if upward_rate < 0.10:
        return "LOW"
    elif upward_rate < 0.30:
        return "MEDIUM"
    return "HIGH"


def discretize_downward_correction(downward_rate: float) -> str:
    """
    Rate at which Agent 3 DE-ESCALATES ML decisions.
    High rate = ML overreacts but LLM clears = gamer/trusted person.
    (ML says dangerous, LLM says safe — false positive suppression)
    """
    if downward_rate < 0.10:
        return "LOW"
    elif downward_rate < 0.30:
        return "MEDIUM"
    return "HIGH"


def discretize_target_breadth(targets: int) -> str:
    """
    Number of unique children contacted.
    Trolls → MANY (spray-and-pray), Groomers/Bullies → FEW (focused).
    """
    if targets <= 2:
        return "FEW"
    elif targets <= 5:
        return "SOME"
    return "MANY"


def discretize_block_ratio(ratio: float) -> str:
    """Block/warn ratio — captures Olweus 'repetition' for bullying."""
    if ratio < 0.10:
        return "LOW"
    elif ratio < 0.30:
        return "MEDIUM"
    return "HIGH"


def discretize_message_behavior(freq_1h: int, burst_24h: int) -> str:
    """
    Combined frequency + burstiness signal.
    BURSTY = troll/spam pattern (hit-and-run).
    CALM = groomer pattern (patient, slow).
    """
    if freq_1h > 15 or burst_24h >= 3:
        return "BURSTY"
    elif freq_1h > 5 or burst_24h >= 2:
        return "ACTIVE"
    return "CALM"


def discretize_message_style(avg_length: float) -> str:
    """
    Average message length.
    LONG = rapport building (O'Connell Stage 1-2: Friendship + Relationship).
    SHORT = low-effort provocations (troll pattern).
    """
    if avg_length < 20:
        return "SHORT"
    elif avg_length < 60:
        return "MEDIUM"
    return "LONG"


def map_threat_category(category: str) -> str:
    """Maps Agent 2 classification to BN modality."""
    mapping = {
        "safe": "SAFE",
        "verbal_harassment": "VERBAL",
        "threat": "THREAT",
        "sexual_harassment": "SEXUAL",
        "discrimination": "DISCRIMINATION",
    }
    return mapping.get(category, "SAFE")


# ═══════════════════════════════════════════════════════════════
#  MAIN EVIDENCE COLLECTOR
# ═══════════════════════════════════════════════════════════════

def collect_evidence(profile, threat_category: str = "safe") -> dict:
    """
    Reads a UserBehaviorProfile and produces the full BN evidence dict.

    This function bridges the Digital Twin (continuous numerical state)
    and the Bayesian Network (discrete categorical evidence).

    Args:
        profile: UserBehaviorProfile instance
        threat_category: Agent 2's classification for the current message

    Returns:
        dict of {variable_name: modality_string} for BN inference
    """
    from django.utils import timezone

    days = (
        (timezone.now() - profile.first_seen_at).days
        if profile.first_seen_at
        else 0
    )

    # Compute upward/downward correction rates
    total_msgs = max(1, profile.total_messages_sent)

    # Upward corrections: ML says safe, LLM escalates
    upward_corrections = getattr(profile, 'upward_corrections_total', 0)
    upward_rate = upward_corrections / total_msgs

    # Downward corrections: ML says harmful, LLM de-escalates
    downward_corrections = getattr(profile, 'downward_corrections_total', 0)
    downward_rate = downward_corrections / total_msgs

    return {
        "Stranger": discretize_stranger(days),
        "ChildInitiated": discretize_child_initiated(getattr(profile, 'child_initiated', False)),
        "SharedGroupsCount": discretize_shared_groups(getattr(profile, 'shared_groups_count', 0)),
        "NightActive": discretize_night_active(float(profile.night_activity_ratio)),
        "ToxicityLevel": discretize_toxicity(float(profile.average_toxicity_score)),
        "UpwardCorrection": discretize_upward_correction(upward_rate),
        "DownwardCorrection": discretize_downward_correction(downward_rate),
        "TargetBreadth": discretize_target_breadth(profile.unique_targets_count),
        "BlockRatio": discretize_block_ratio(float(profile.block_ratio)),
        "MessageBehavior": discretize_message_behavior(
            profile.message_frequency_1h, profile.burst_count_24h
        ),
        "MessageStyle": discretize_message_style(float(profile.avg_message_length)),
        "ThreatCategory": map_threat_category(threat_category),
    }
