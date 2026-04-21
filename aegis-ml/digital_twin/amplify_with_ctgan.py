"""
═══════════════════════════════════════════════════════════════
  AEGIS Digital Twin — TIER 2: CTGAN Amplification
═══════════════════════════════════════════════════════════════

This script takes the 500 rule-based seed profiles and feeds
them into a CTGAN (Conditional Tabular GAN) to generate
~2,000 MORE profiles that are statistically realistic.

WHY CTGAN?
  Our 500 seeds are "too clean" — they follow exact rules.
  Real humans are messier. CTGAN learns the JOINT DISTRIBUTION
  of all 14 features together, and generates profiles with
  realistic correlations and edge cases that our rules missed.

  Example: A rule-based groomer always has night_ratio > 0.40.
  But CTGAN might generate a groomer with night_ratio = 0.35
  who compensates with very high correction_rate = 0.48.
  That's a realistic edge case our rules didn't think of.

Input:  data/seeds.csv (500 rows)
Output: data/synthetic_amplified.csv (~2,500 rows = seeds + generated)
═══════════════════════════════════════════════════════════════
"""

import os
import pandas as pd
import numpy as np

# ── Paths ────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SEEDS_PATH = os.path.join(DATA_DIR, "seeds.csv")
OUTPUT_PATH = os.path.join(DATA_DIR, "synthetic_amplified.csv")

# ── Target counts (total = seeds + generated) ───────────────
# Updated for Phase 3: Night-active sub-archetypes mean more
# seeds per class. We amplify to ~3,000 total profiles.
TARGET_COUNTS = {
    "LOW":      1200,   # ~40% — Normal users (daytime + night-active)
    "HIGH":     700,    # ~23% — Bullies (daytime + night-active)
    "CRITICAL": 500,    # ~17% — Groomers
    "MEDIUM":   500,    # ~17% — Trolls (daytime + night-active)
}


def amplify_with_ctgan():
    """
    Main amplification pipeline:
    1. Load seeds
    2. Train CTGAN on seeds
    3. Generate synthetic profiles per class
    4. Combine seeds + synthetic
    5. Save final dataset
    """
    print("═" * 60)
    print("  🧬 AEGIS Digital Twin — Tier 2: CTGAN Amplification")
    print("═" * 60)

    # ── 1. Load seeds ────────────────────────────────────────
    seeds_df = pd.read_csv(SEEDS_PATH)
    print(f"\n  📥 Loaded {len(seeds_df)} seed profiles from {SEEDS_PATH}")
    print(f"  📊 Seed distribution:")
    for label, count in seeds_df["risk_label"].value_counts().items():
        print(f"     {label:>8}: {count}")

    # ── 2. Setup CTGAN ───────────────────────────────────────
    try:
        from sdv.single_table import CTGANSynthesizer
        from sdv.metadata import SingleTableMetadata
    except ImportError:
        print("\n  ❌ SDV not installed. Installing...")
        os.system(f"{os.path.dirname(os.path.abspath(__file__))}/../../aegis-backend/venv/bin/pip install sdv")
        from sdv.single_table import CTGANSynthesizer
        from sdv.metadata import SingleTableMetadata

    # ── 3. Create metadata ───────────────────────────────────
    metadata = SingleTableMetadata()
    metadata.detect_from_dataframe(seeds_df)
    # Tell SDV that risk_label is a categorical column (not numeric)
    metadata.update_column('risk_label', sdtype='categorical')

    # Integer features need to be marked
    int_features = ["escalation_count", "unique_targets_count",
                    "burst_count_24h", "days_since_first_seen"]
    for feat in int_features:
        metadata.update_column(feat, sdtype='numerical')

    print(f"\n  🧠 Training CTGAN (this may take 2-5 minutes)...")

    # ── 4. Train CTGAN ───────────────────────────────────────
    synthesizer = CTGANSynthesizer(
        metadata,
        epochs=300,        # More epochs = better quality
        batch_size=100,
        verbose=True
    )
    synthesizer.fit(seeds_df)
    print("  ✅ CTGAN training complete!")

    # ── 5. Generate synthetic profiles per class ─────────────
    # We generate extra for each class to hit our target counts
    all_frames = [seeds_df]  # Start with original seeds

    for risk_label, target_total in TARGET_COUNTS.items():
        existing = len(seeds_df[seeds_df["risk_label"] == risk_label])
        needed = target_total - existing

        if needed <= 0:
            print(f"  ⏭️  {risk_label}: already have {existing}, need {target_total}. Skipping.")
            continue

        print(f"\n  🔄 Generating {needed} synthetic profiles for {risk_label}...")

        # Generate with condition on risk_label
        from sdv.sampling import Condition
        condition = Condition(
            num_rows=needed,
            column_values={"risk_label": risk_label}
        )

        try:
            synthetic = synthesizer.sample_from_conditions([condition])
        except Exception as e:
            # Fallback: generate unconditioned and filter
            print(f"  ⚠️  Conditional sampling failed ({e}). Using filter method...")
            oversample = synthesizer.sample(num_rows=needed * 4)
            synthetic = oversample[oversample["risk_label"] == risk_label].head(needed)

        # Clip values to valid ranges (no negative ratios, etc.)
        ratio_cols = ["block_ratio", "avg_toxicity_score", "night_activity_ratio",
                      "correction_rate", "max_toxicity_24h", "current_hour_score"]
        for col in ratio_cols:
            if col in synthetic.columns:
                synthetic[col] = synthetic[col].clip(0.0, 1.0)

        count_cols = ["escalation_count", "unique_targets_count",
                      "burst_count_24h", "days_since_first_seen"]
        for col in count_cols:
            if col in synthetic.columns:
                synthetic[col] = synthetic[col].clip(0).round().astype(int)

        # Positive-only columns
        pos_cols = ["message_frequency_1h", "avg_message_length"]
        for col in pos_cols:
            if col in synthetic.columns:
                synthetic[col] = synthetic[col].clip(0.0)

        all_frames.append(synthetic)
        name = {"LOW": "NORMAL", "HIGH": "BULLY", "CRITICAL": "GROOMER", "MEDIUM": "TROLL"}[risk_label]
        print(f"  ✅ Generated {len(synthetic)} {name} profiles")

    # ── 6. Combine and save ──────────────────────────────────
    final_df = pd.concat(all_frames, ignore_index=True)
    final_df = final_df.sample(frac=1, random_state=42).reset_index(drop=True)
    final_df.to_csv(OUTPUT_PATH, index=False)

    print(f"\n  ✅ Saved {len(final_df)} total profiles → {OUTPUT_PATH}")
    print(f"\n  📊 Final Distribution:")
    for label, count in final_df["risk_label"].value_counts().items():
        pct = count / len(final_df) * 100
        name = {"LOW": "NORMAL", "HIGH": "BULLY", "CRITICAL": "GROOMER", "MEDIUM": "TROLL"}.get(label, label)
        print(f"     {name:>7} ({label:>8}): {count:>4} profiles ({pct:.1f}%)")

    print("\n" + "═" * 60)
    print("  🚀 Next step: Run train_rf.py to train the Random Forest!")
    print("═" * 60)


if __name__ == "__main__":
    amplify_with_ctgan()
