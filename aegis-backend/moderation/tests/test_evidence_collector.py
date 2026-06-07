"""
Tests for the Bayesian evidence collector (ml_pipeline/bayesian/evidence.py).

The evidence collector discretizes Digital Twin features into BN modalities.
These tests verify the threshold mappings that bridge real data to BN inference.
"""
import pytest
from ml_pipeline.bayesian.evidence import (
    discretize_stranger,
    discretize_night_active,
    discretize_toxicity,
    discretize_upward_correction,
    discretize_downward_correction,
    discretize_message_behavior,
    discretize_message_style,
    map_threat_category,
)


class TestEvidenceDiscretization:
    """Tests for discretization functions -- the bridge between Digital Twin and BN."""

    def test_stranger_threshold(self):
        """< 14 days = Stranger (O'Connell grooming timeline)."""
        assert discretize_stranger(5) == "YES"   # 5 days = unknown
        assert discretize_stranger(13) == "YES"  # 13 days = still stranger
        assert discretize_stranger(14) == "NO"   # 14 days = known contact
        assert discretize_stranger(60) == "NO"   # 60 days = well-known

    def test_night_active_with_cold_start(self):
        """Night activity should be dampened on low message counts."""
        # Cold start: < 5 messages, ratio dampened by 0.3
        # 0.80 * 0.3 = 0.24 → MEDIUM (not HIGH)
        assert discretize_night_active(0.80, total_messages=3) == "MEDIUM"

        # With enough messages, raw ratio applies
        assert discretize_night_active(0.80, total_messages=10) == "HIGH"
        assert discretize_night_active(0.10, total_messages=10) == "LOW"
        assert discretize_night_active(0.35, total_messages=10) == "MEDIUM"

    def test_toxicity_levels(self):
        """Toxicity EMA score should map to correct modality."""
        assert discretize_toxicity(0.05) == "CLEAN"
        assert discretize_toxicity(0.20) == "MILD"
        assert discretize_toxicity(0.40) == "MODERATE"
        assert discretize_toxicity(0.70) == "SEVERE"

    def test_correction_rates(self):
        """Upward/downward correction rates signal ML blind spots or false positives."""
        # Upward: ML misses threat, LLM catches it
        assert discretize_upward_correction(0.05) == "LOW"
        assert discretize_upward_correction(0.20) == "MEDIUM"
        assert discretize_upward_correction(0.50) == "HIGH"

        # Downward: ML overreacts, LLM clears
        assert discretize_downward_correction(0.05) == "LOW"
        assert discretize_downward_correction(0.20) == "MEDIUM"
        assert discretize_downward_correction(0.50) == "HIGH"

    def test_message_behavior_burst_detection(self):
        """Burst pattern detection (troll/spam vs groomer patience)."""
        assert discretize_message_behavior(20, 1) == "BURSTY"  # 20 msgs/hr
        assert discretize_message_behavior(2, 4) == "BURSTY"   # 4 bursts/day
        assert discretize_message_behavior(8, 1) == "ACTIVE"   # moderate
        assert discretize_message_behavior(2, 0) == "CALM"     # low activity

    def test_message_style_length(self):
        """Message length signals grooming (LONG) vs troll (SHORT)."""
        assert discretize_message_style(10) == "SHORT"   # Low-effort
        assert discretize_message_style(40) == "MEDIUM"  # Normal
        assert discretize_message_style(100) == "LONG"   # Rapport building

    def test_threat_category_mapping(self):
        """Agent 2 classification should map to BN modality."""
        assert map_threat_category("safe") == "SAFE"
        assert map_threat_category("verbal_harassment") == "VERBAL"
        assert map_threat_category("threat") == "THREAT"
        assert map_threat_category("sexual_harassment") == "SEXUAL"
        assert map_threat_category("discrimination") == "DISCRIMINATION"
        assert map_threat_category("unknown_class") == "SAFE"  # Fallback
