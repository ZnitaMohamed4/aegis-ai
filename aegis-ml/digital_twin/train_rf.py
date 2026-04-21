"""
═══════════════════════════════════════════════════════════════
  AEGIS Digital Twin — STEP 5: Train the Random Forest
═══════════════════════════════════════════════════════════════

This script:
  1. Loads the 2,000 synthetic behavioral profiles
  2. Splits into 80% train / 20% test (stratified)
  3. Trains a Random Forest with class_weight='balanced'
  4. Prints a full classification report + confusion matrix
  5. Shows which features matter most (feature importance)
  6. Saves the trained model as risk_classifier.joblib

The model learns: given 14 behavioral numbers → predict
  LOW (Normal) / MEDIUM (Troll) / HIGH (Bully) / CRITICAL (Groomer)

Output:
  - models/risk_classifier.joblib  (the trained brain)
  - Terminal: accuracy, F1, confusion matrix, feature importance
═══════════════════════════════════════════════════════════════
"""

import os
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
import joblib

# ── Paths ────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DATASET_PATH = os.path.join(DATA_DIR, "synthetic_amplified.csv")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(MODEL_DIR, exist_ok=True)
MODEL_PATH = os.path.join(MODEL_DIR, "risk_classifier.joblib")

# Also save a copy directly into the backend for the pipeline
BACKEND_MODEL_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "aegis-backend", "ml_pipeline", "models"
)
os.makedirs(BACKEND_MODEL_DIR, exist_ok=True)
BACKEND_MODEL_PATH = os.path.join(BACKEND_MODEL_DIR, "risk_classifier.joblib")

# ── Feature names (must match feature_extractor.py) ──────────
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

TARGET_COL = "risk_label"


def train():
    print("═" * 60)
    print("  🌲 AEGIS Digital Twin — Step 5: Random Forest Training")
    print("═" * 60)

    # ── 1. Load Data ─────────────────────────────────────────
    df = pd.read_csv(DATASET_PATH)
    print(f"\n  📥 Loaded {len(df)} profiles from {DATASET_PATH}")
    print(f"  📊 Class distribution:")
    for label, count in df[TARGET_COL].value_counts().items():
        pct = count / len(df) * 100
        name = {"LOW": "NORMAL", "HIGH": "BULLY", "CRITICAL": "GROOMER", "MEDIUM": "TROLL"}.get(label, label)
        print(f"     {name:>7} ({label:>8}): {count:>4} ({pct:.1f}%)")

    # ── 2. Split Features / Target ───────────────────────────
    X = df[FEATURE_NAMES].values
    y = df[TARGET_COL].values

    print(f"\n  📐 Feature matrix shape: {X.shape}")
    print(f"  🎯 Target classes: {sorted(set(y))}")

    # ── 3. Train/Test Split (80/20, stratified) ──────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"\n  ✂️  Split: {len(X_train)} train / {len(X_test)} test")

    # ── 4. Train Random Forest ───────────────────────────────
    print(f"\n  🧠 Training Random Forest...")
    rf = RandomForestClassifier(
        n_estimators=200,          # 200 decision trees vote together
        max_depth=12,              # Each tree can be 12 levels deep
        min_samples_split=5,       # Need at least 5 samples to split a node
        min_samples_leaf=2,        # Each leaf must have at least 2 samples
        class_weight="balanced",   # Automatically compensate for class imbalance
        random_state=42,
        n_jobs=-1,                 # Use all CPU cores
        oob_score=True,            # Out-of-Bag score (free validation!)
    )
    rf.fit(X_train, y_train)

    # ── 5. Evaluate ──────────────────────────────────────────
    print(f"\n  ✅ Training complete!")
    print(f"\n  📊 Out-of-Bag Score: {rf.oob_score_:.4f}")
    print(f"     (This is like a free validation score — RF internally")
    print(f"      tests each tree on data it DIDN'T see during training)")

    # Test set accuracy
    y_pred = rf.predict(X_test)
    test_acc = (y_pred == y_test).mean()
    print(f"\n  🎯 Test Accuracy: {test_acc:.4f} ({test_acc*100:.1f}%)")

    # Full classification report
    label_order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    target_names = ["NORMAL (LOW)", "TROLL (MEDIUM)", "BULLY (HIGH)", "GROOMER (CRITICAL)"]
    print(f"\n  📋 Classification Report:")
    print("  " + "-" * 56)
    report = classification_report(
        y_test, y_pred,
        labels=label_order,
        target_names=target_names,
        digits=3
    )
    for line in report.split("\n"):
        print(f"  {line}")

    # Confusion Matrix
    cm = confusion_matrix(y_test, y_pred, labels=label_order)
    print(f"\n  🔢 Confusion Matrix:")
    print(f"  {'':>20} {'NORMAL':>8} {'TROLL':>8} {'BULLY':>8} {'GROOMER':>8}")
    for i, label in enumerate(["NORMAL", "TROLL", "BULLY", "GROOMER"]):
        row = "  ".join(f"{v:>6}" for v in cm[i])
        print(f"  {label:>20}   {row}")

    # ── 6. Feature Importance ────────────────────────────────
    importances = rf.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]

    print(f"\n  🏆 Feature Importance Ranking:")
    print(f"  {'Rank':>4} | {'Feature':>25} | {'Importance':>10} | {'Bar'}")
    print(f"  {'-'*4}-+-{'-'*25}-+-{'-'*10}-+-{'-'*20}")
    for rank, idx in enumerate(sorted_idx, 1):
        name = FEATURE_NAMES[idx]
        imp = importances[idx]
        bar = "█" * int(imp * 50)
        print(f"  {rank:>4} | {name:>25} | {imp:>10.4f} | {bar}")

    # ── 7. Cross-Validation ──────────────────────────────────
    print(f"\n  🔄 5-Fold Cross-Validation...")
    cv_scores = cross_val_score(rf, X, y, cv=5, scoring="f1_macro", n_jobs=-1)
    print(f"     Fold scores: {[f'{s:.4f}' for s in cv_scores]}")
    print(f"     Mean F1:     {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    # ── 8. Save Model ───────────────────────────────────────
    # Save with feature names for interpretability
    model_bundle = {
        "model": rf,
        "feature_names": FEATURE_NAMES,
        "classes": list(rf.classes_),
        "oob_score": rf.oob_score_,
        "test_accuracy": test_acc,
    }
    joblib.dump(model_bundle, MODEL_PATH)
    print(f"\n  💾 Model saved → {MODEL_PATH}")

    # Copy to backend
    joblib.dump(model_bundle, BACKEND_MODEL_PATH)
    print(f"  💾 Model copied → {BACKEND_MODEL_PATH}")

    print("\n" + "═" * 60)
    print("  🚀 Next step: Integrate into profiler_node (Step 6)")
    print("═" * 60)

    return rf


if __name__ == "__main__":
    train()
