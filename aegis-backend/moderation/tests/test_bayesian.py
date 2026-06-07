"""
Tests for the Bayesian Network profiler (ml_pipeline/bayesian/engine.py).

These are pure computation tests -- no Django, no database needed.
The BayesianProfiler is instantiated directly (not via singleton) to avoid
cross-test state pollution.
"""
import pytest
from ml_pipeline.bayesian.engine import BayesianProfiler


@pytest.fixture
def bn_profiler():
    """Create a fresh BayesianProfiler instance for each test."""
    return BayesianProfiler()


class TestBayesianNetwork:
    """Tests for the Bayesian Network structure and inference."""

    def test_bn_structure_has_16_nodes(self, bn_profiler):
        """The network should have 16 nodes:
        12 observable + 3 intermediate pathway + 1 output."""
        nodes = bn_profiler.model.nodes()
        assert len(nodes) == 16

        # Verify key nodes exist
        expected_nodes = {
            # 12 observables
            "Stranger", "ChildInitiated", "SharedGroupsCount", "NightActive",
            "ToxicityLevel", "BlockRatio", "TargetBreadth", "MessageBehavior",
            "MessageStyle", "ThreatCategory",
            "UpwardCorrection", "DownwardCorrection",
            # 3 pathways
            "GroomingRisk", "BullyRisk", "TrollRisk",
            # 1 output
            "OverallRisk",
        }
        assert expected_nodes == set(nodes)

    def test_bn_safe_evidence_returns_low_risk(self, bn_profiler):
        """Safe evidence (all lowest-risk states) should produce LOW risk."""
        safe_evidence = {
            "Stranger": "NO",
            "ChildInitiated": "YES",
            "SharedGroupsCount": "MANY",
            "NightActive": "LOW",
            "ToxicityLevel": "CLEAN",
            "UpwardCorrection": "LOW",
            "DownwardCorrection": "HIGH",  # Agent 3 cleared the person
            "TargetBreadth": "FEW",
            "BlockRatio": "LOW",
            "MessageBehavior": "CALM",
            "MessageStyle": "LONG",
            "ThreatCategory": "SAFE",
        }

        result = bn_profiler.infer(safe_evidence)

        assert result["risk_level"] == "LOW"
        assert result["risk_score"] < 0.20
        assert result["archetype"] == "Normal User"

    def test_bn_dangerous_evidence_returns_high_risk(self, bn_profiler):
        """Dangerous evidence should produce HIGH or CRITICAL risk."""
        dangerous_evidence = {
            "Stranger": "YES",
            "ChildInitiated": "NO",  # Stranger initiated contact
            "SharedGroupsCount": "ZERO",
            "NightActive": "HIGH",
            "ToxicityLevel": "SEVERE",
            "UpwardCorrection": "HIGH",  # Agent 3 escalated
            "DownwardCorrection": "LOW",
            "TargetBreadth": "FEW",  # Focused targeting
            "BlockRatio": "HIGH",
            "MessageBehavior": "BURSTY",
            "MessageStyle": "SHORT",
            "ThreatCategory": "THREAT",
        }

        result = bn_profiler.infer(dangerous_evidence)

        assert result["risk_level"] in ("HIGH", "CRITICAL")
        assert result["risk_score"] > 0.50
        assert result["archetype"] != "Normal User"
