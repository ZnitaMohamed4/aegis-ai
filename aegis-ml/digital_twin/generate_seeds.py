"""
═══════════════════════════════════════════════════════════════
  AEGIS Digital Twin — TIER 1: Rule-Based Seed Generation
═══════════════════════════════════════════════════════════════

This script generates ~600 "seed" behavioral profiles using
domain knowledge about 4 user archetypes:

  1. NORMAL  — Friends, family, gamers. Low toxicity, known contacts.
  2. BULLY   — Persistent, rising hostility toward specific victims.
  3. GROOMER — Subtle, low-toxicity, night-active, targets children.
  4. TROLL   — Spammy, bursty, hits many targets, then disappears.

Each profile is a row of 14 behavioral features + a risk_label.
Gaussian noise is added so the Random Forest learns PATTERNS,
not exact numbers.

Output: data/seeds.csv (~600 rows × 15 columns)
═══════════════════════════════════════════════════════════════
"""

import os
import numpy as np
import pandas as pd

# ── Reproducibility ──────────────────────────────────────────
np.random.seed(42)

# ── Output path ──────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "seeds.csv")

# ── Feature names (must match feature_extractor.py EXACTLY) ──
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
    "risk_trajectory_delta",
]


# ═════════════════════════════════════════════════════════════
#  NOISE INJECTION
# ═════════════════════════════════════════════════════════════
def add_noise(value, std=0.05, min_val=None, max_val=None):
    """
    Adds Gaussian noise to a value.
    
    WHY: If every "Normal" user had block_ratio = exactly 0.02,
    the model would memorize "0.02 = Normal" instead of learning
    "low block_ratio = Normal". Noise forces generalization.
    
    Args:
        value: The base value
        std:   Standard deviation of noise (bigger = more randomness)
        min_val: Floor (e.g., 0.0 for ratios)
        max_val: Ceiling (e.g., 1.0 for ratios)
    """
    noisy = value + np.random.normal(0, std)
    if min_val is not None:
        noisy = max(noisy, min_val)
    if max_val is not None:
        noisy = min(noisy, max_val)
    return round(noisy, 4)


# ═════════════════════════════════════════════════════════════
#  ARCHETYPE DEFINITIONS
# ═════════════════════════════════════════════════════════════
# Each archetype is a dictionary of (min, max) ranges.
# For each seed profile, we sample uniformly within these ranges,
# then add Gaussian noise on top.

ARCHETYPES = {
    # ─── NORMAL USER (Daytime) ────────────────────────────
    # Friends, family, known contacts. Clean messages.
    # ML almost never flags them. Known contacts for months.
    "LOW": {
        "block_ratio":           (0.0,  0.05),
        "avg_toxicity_score":    (0.01, 0.12),
        "escalation_count":      (0,    1),
        "night_activity_ratio":  (0.0,  0.20),
        "unique_targets_count":  (1,    3),
        "message_frequency_1h":  (0,    8),
        "avg_message_length":    (15,   80),
        "correction_rate":       (0.0,  0.10),
        "days_since_first_seen": (30,   365),
        "burst_count_24h":       (0,    1),
        "max_toxicity_24h":      (0.01, 0.15),
        "toxicity_trend_slope":  (-0.02, 0.02),
        "current_hour_score":    (0.0,  0.3),
        "risk_trajectory_delta": (-0.05, 0.05),
    },

    # ─── BULLY (Daytime) ─────────────────────────────────
    # Persistent harassment toward specific victims.
    # Rising toxicity, multiple escalations, bursty behavior.
    "HIGH": {
        "block_ratio":           (0.15, 0.50),
        "avg_toxicity_score":    (0.30, 0.70),
        "escalation_count":      (2,    8),
        "night_activity_ratio":  (0.10, 0.40),
        "unique_targets_count":  (1,    4),
        "message_frequency_1h":  (5,    25),
        "avg_message_length":    (8,    40),
        "correction_rate":       (0.05, 0.25),
        "days_since_first_seen": (7,    180),
        "burst_count_24h":       (1,    5),
        "max_toxicity_24h":      (0.40, 0.85),
        "toxicity_trend_slope":  (0.0,  0.08),
        "current_hour_score":    (0.0,  0.5),
        "risk_trajectory_delta": (0.0,  0.15),
    },

    # ─── GROOMER ──────────────────────────────────────────
    # The hardest to detect. Low toxicity, but:
    #   - Messages at night (22h-06h)
    #   - STRANGER (days_known ≤ 15 — tightened from 30)
    #   - Long, conversational messages (building trust)
    #   - Agent 3 correction rate is HIGH (ML misses them)
    "CRITICAL": {
        "block_ratio":           (0.02, 0.15),
        "avg_toxicity_score":    (0.05, 0.25),
        "escalation_count":      (0,    2),
        "night_activity_ratio":  (0.40, 0.85),
        "unique_targets_count":  (1,    2),
        "message_frequency_1h":  (3,    15),
        "avg_message_length":    (40,   150),
        "correction_rate":       (0.15, 0.50),
        "days_since_first_seen": (1,    15),       # ← TIGHTENED: strangers only
        "burst_count_24h":       (0,    2),
        "max_toxicity_24h":      (0.05, 0.30),
        "toxicity_trend_slope":  (-0.01, 0.03),
        "current_hour_score":    (0.5,  1.0),
        "risk_trajectory_delta": (0.02, 0.12),
    },

    # ─── TROLL / SPAMMER (Daytime) ───────────────────────
    # Hit-and-run behavior. Short messages, many targets,
    # very bursty, then disappears. New accounts.
    "MEDIUM": {
        "block_ratio":           (0.10, 0.35),
        "avg_toxicity_score":    (0.15, 0.45),
        "escalation_count":      (0,    3),
        "night_activity_ratio":  (0.05, 0.25),
        "unique_targets_count":  (3,    15),
        "message_frequency_1h":  (10,   40),
        "avg_message_length":    (5,    25),
        "correction_rate":       (0.10, 0.30),
        "days_since_first_seen": (1,    14),
        "burst_count_24h":       (2,    8),
        "max_toxicity_24h":      (0.20, 0.55),
        "toxicity_trend_slope":  (-0.05, 0.05),
        "current_hour_score":    (0.0,  0.5),
        "risk_trajectory_delta": (-0.05, 0.08),
    },
}

# ═════════════════════════════════════════════════════════════
#  NIGHT-ACTIVE SUB-ARCHETYPES (Phase 3 Fix)
# ═════════════════════════════════════════════════════════════
# GENERAL night-active variants for every class.
# These represent any user who is legitimately active at night:
#   students, shift workers, people in different time zones,
#   late-night chatters, etc. — NOT context-specific.
#
# The KEY discriminator for a groomer is:
#   STRANGER (low days_known) + night + high correction + low toxicity
# NOT just "anyone at night".

NIGHT_ARCHETYPES = {
    # ─── NIGHT-ACTIVE NORMAL USER ────────────────────────
    # Students doing homework at midnight, shift workers,
    # people in different time zones, late-night socializers.
    # The CRITICAL difference vs Groomer: they are KNOWN contacts.
    "LOW_NIGHT": {
        "label": "LOW",
        "block_ratio":           (0.0,  0.06),
        "avg_toxicity_score":    (0.01, 0.15),
        "escalation_count":      (0,    1),
        "night_activity_ratio":  (0.45, 1.0),      # ← HIGH night, but SAFE
        "unique_targets_count":  (1,    3),
        "message_frequency_1h":  (0,    10),
        "avg_message_length":    (10,   90),
        "correction_rate":       (0.0,  0.10),      # ← LOW corrections
        "days_since_first_seen": (30,   365),       # ← KNOWN for a long time
        "burst_count_24h":       (0,    2),
        "max_toxicity_24h":      (0.01, 0.18),
        "toxicity_trend_slope":  (-0.02, 0.02),
        "current_hour_score":    (0.5,  1.0),
        "risk_trajectory_delta": (-0.05, 0.05),
    },

    # ─── NIGHT-ACTIVE NORMAL (Moderate contact age) ──────
    # Newer but still established contacts chatting at night.
    # Covers the 14-30 day range that the Groomer doesn't.
    "LOW_NIGHT_MED": {
        "label": "LOW",
        "block_ratio":           (0.0,  0.05),
        "avg_toxicity_score":    (0.02, 0.12),
        "escalation_count":      (0,    1),
        "night_activity_ratio":  (0.40, 0.85),
        "unique_targets_count":  (1,    4),
        "message_frequency_1h":  (1,    8),
        "avg_message_length":    (15,   70),
        "correction_rate":       (0.0,  0.08),
        "days_since_first_seen": (16,   90),        # ← Not strangers, not old friends
        "burst_count_24h":       (0,    1),
        "max_toxicity_24h":      (0.02, 0.15),
        "toxicity_trend_slope":  (-0.01, 0.02),
        "current_hour_score":    (0.5,  1.0),
        "risk_trajectory_delta": (-0.04, 0.04),
    },

    # ─── NIGHT-ACTIVE BULLY ──────────────────────────────
    # Bullies who harass at night. Same toxic behavior,
    # just shifted to nighttime hours.
    "HIGH_NIGHT": {
        "label": "HIGH",
        "block_ratio":           (0.15, 0.50),
        "avg_toxicity_score":    (0.30, 0.70),
        "escalation_count":      (2,    7),
        "night_activity_ratio":  (0.45, 0.90),      # ← HIGH night activity
        "unique_targets_count":  (1,    4),
        "message_frequency_1h":  (5,    25),
        "avg_message_length":    (8,    40),
        "correction_rate":       (0.05, 0.25),
        "days_since_first_seen": (7,    180),
        "burst_count_24h":       (1,    5),
        "max_toxicity_24h":      (0.40, 0.85),
        "toxicity_trend_slope":  (0.0,  0.08),
        "current_hour_score":    (0.5,  1.0),
        "risk_trajectory_delta": (0.0,  0.15),
    },

    # ─── NIGHT-ACTIVE TROLL ──────────────────────────────
    # Spammers who operate at night. Same hit-and-run pattern.
    "MEDIUM_NIGHT": {
        "label": "MEDIUM",
        "block_ratio":           (0.10, 0.35),
        "avg_toxicity_score":    (0.15, 0.45),
        "escalation_count":      (0,    3),
        "night_activity_ratio":  (0.35, 0.80),      # ← Night spam
        "unique_targets_count":  (3,    15),
        "message_frequency_1h":  (10,   40),
        "avg_message_length":    (5,    25),
        "correction_rate":       (0.10, 0.30),
        "days_since_first_seen": (1,    14),
        "burst_count_24h":       (2,    8),
        "max_toxicity_24h":      (0.20, 0.55),
        "toxicity_trend_slope":  (-0.05, 0.05),
        "current_hour_score":    (0.5,  1.0),
        "risk_trajectory_delta": (-0.05, 0.08),
    },
}

# How many seeds per class (BASE archetypes — daytime patterns)
BASE_CLASS_COUNTS = {
    "LOW":      180,   # Normal users (daytime)
    "HIGH":     100,   # Bullies (daytime)
    "CRITICAL":  88,   # Groomers (always night by definition)
    "MEDIUM":    52,   # Trolls (daytime)
}

# How many seeds per NIGHT sub-archetype
NIGHT_CLASS_COUNTS = {
    "LOW_NIGHT":     100,   # Night-active normal users (long-term contacts)
    "LOW_NIGHT_MED":  60,   # Night-active normal (medium-term contacts)
    "HIGH_NIGHT":     60,   # Bullies who harass at night
    "MEDIUM_NIGHT":   40,   # Trolls who spam at night
}
# Total = 420 base + 260 night + 88 groomer = 680 seeds


# ═════════════════════════════════════════════════════════════
#  GENERATION LOGIC
# ═════════════════════════════════════════════════════════════
def generate_one_profile(archetype_ranges: dict) -> dict:
    """
    Generate a single behavioral profile by:
      1. Sampling uniformly within each feature's (min, max) range
      2. Adding Gaussian noise for realistic variation
    
    Returns: dict with 14 feature values
    """
    profile = {}
    for feature_name in FEATURE_NAMES:
        lo, hi = archetype_ranges[feature_name]

        # Integer features (counts) vs Float features (ratios/scores)
        integer_features = {"escalation_count", "unique_targets_count",
                           "burst_count_24h", "days_since_first_seen"}

        if feature_name in integer_features:
            # Sample an integer, add small integer noise
            base = np.random.randint(lo, hi + 1)
            noise = np.random.choice([-1, 0, 0, 0, 1])  # Slight jitter
            value = max(0, base + noise)
            profile[feature_name] = value
        else:
            # Sample a float uniformly, then add Gaussian noise
            base = np.random.uniform(lo, hi)
            # Noise std = 10% of the range width (controlled chaos)
            noise_std = (hi - lo) * 0.10
            profile[feature_name] = add_noise(base, std=noise_std, min_val=0.0)

    return profile


def generate_all_seeds():
    """
    Generate the full seed dataset across all archetypes.
    Includes both BASE (daytime) and NIGHT-ACTIVE sub-archetypes
    for every behavioral class.
    Returns: pandas DataFrame
    """
    all_profiles = []

    # --- 1. Generate BASE (daytime) archetypes ---
    print("\n  ── BASE ARCHETYPES (daytime patterns) ──")
    for risk_label, count in BASE_CLASS_COUNTS.items():
        archetype_ranges = ARCHETYPES[risk_label]
        archetype_name = {
            "LOW": "NORMAL", "HIGH": "BULLY",
            "CRITICAL": "GROOMER", "MEDIUM": "TROLL"
        }[risk_label]

        print(f"  Generating {count:>3} seeds for {archetype_name:>15} (risk_label={risk_label})")

        for _ in range(count):
            profile = generate_one_profile(archetype_ranges)
            profile["risk_label"] = risk_label
            all_profiles.append(profile)

    # --- 2. Generate NIGHT-ACTIVE sub-archetypes ---
    print("\n  ── NIGHT-ACTIVE SUB-ARCHETYPES (Phase 3 fix) ──")
    for night_key, count in NIGHT_CLASS_COUNTS.items():
        night_archetype = NIGHT_ARCHETYPES[night_key]
        actual_label = night_archetype["label"]  # The real risk label (LOW/HIGH/MEDIUM)
        # Build ranges dict (everything except 'label')
        archetype_ranges = {k: v for k, v in night_archetype.items() if k != "label"}

        print(f"  Generating {count:>3} seeds for {night_key:>15} (risk_label={actual_label})")

        for _ in range(count):
            profile = generate_one_profile(archetype_ranges)
            profile["risk_label"] = actual_label
            all_profiles.append(profile)

    df = pd.DataFrame(all_profiles)
    # Shuffle so classes aren't in order
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    return df


# ═════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("═" * 60)
    print("  🏗️  AEGIS Digital Twin — Tier 1: Seed Generation")
    print("═" * 60)

    df = generate_all_seeds()

    # Save
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"\n  ✅ Saved {len(df)} seed profiles → {OUTPUT_PATH}")

    # Quick sanity check
    print(f"\n  📊 Class Distribution:")
    counts = df["risk_label"].value_counts()
    for label, count in counts.items():
        pct = count / len(df) * 100
        name = {"LOW": "NORMAL", "HIGH": "BULLY", "CRITICAL": "GROOMER", "MEDIUM": "TROLL"}[label]
        print(f"     {name:>7} ({label:>8}): {count:>4} profiles ({pct:.1f}%)")

    # Night activity distribution check (critical for Phase 3)
    print(f"\n  🌙 Night Activity Distribution (Phase 3 verification):")
    for label in ["LOW", "HIGH", "CRITICAL", "MEDIUM"]:
        subset = df[df["risk_label"] == label]["night_activity_ratio"]
        name = {"LOW": "NORMAL", "HIGH": "BULLY", "CRITICAL": "GROOMER", "MEDIUM": "TROLL"}[label]
        high_night = (subset > 0.40).sum()
        total = len(subset)
        print(f"     {name:>7}: night>0.40 in {high_night}/{total} profiles ({high_night/total*100:.0f}%)")

    # Show a sample from each class
    print(f"\n  🔍 Sample profiles (1 per class):")
    for label in ["LOW", "HIGH", "CRITICAL", "MEDIUM"]:
        sample = df[df["risk_label"] == label].iloc[0]
        name = {"LOW": "NORMAL", "HIGH": "BULLY", "CRITICAL": "GROOMER", "MEDIUM": "TROLL"}[label]
        print(f"\n     ── {name} ──")
        for feat in FEATURE_NAMES[:6]:  # Show first 6 features
            print(f"       {feat:>25}: {sample[feat]:.4f}")
        print(f"       {'...':>25}")

    print("\n" + "═" * 60)
    print("  🚀 Next step: Run amplify_with_ctgan.py to generate ~3,000 profiles")
    print("═" * 60)
