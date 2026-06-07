"""
Tests for inference logic, language detection, and stub pipeline.

Covers:
- get_decision_uml() -- the core decision mapping function (4 tests)
- is_likely_darija() -- Darija detection heuristic (2 tests)
- run_pipeline_stub() -- keyword-based test pipeline (2 tests)

These are pure function tests -- no Django, no database needed.
"""
import pytest
from ml_pipeline.models_pkg.inference import get_decision_uml, run_pipeline_stub


class TestGetDecisionUML:
    """Tests for get_decision_uml() -- the score-to-decision mapping function."""

    def test_get_decision_uml_extreme_threat(self):
        """Extreme threats (m1 > 0.95 + threat class) should escalate immediately."""
        result = get_decision_uml(m1_score=0.98, primary_class="threat", confidence=0.95)
        assert result == "ESCALATE"

    def test_get_decision_uml_grey_zone_revise(self):
        """Grey zone confidence (0.65-0.75) should return REVISE for human review."""
        result = get_decision_uml(m1_score=0.70, primary_class="discrimination", confidence=0.70)
        assert result == "REVISE"

    def test_get_decision_uml_verbal_harassment_warn(self):
        """Verbal harassment below 0.85 M1 should return WARN."""
        result = get_decision_uml(m1_score=0.60, primary_class="verbal_harassment", confidence=0.80)
        assert result == "WARN"

    def test_get_decision_uml_verbal_harassment_block(self):
        """Verbal harassment above 0.85 M1 should escalate to BLOCK."""
        result = get_decision_uml(m1_score=0.90, primary_class="verbal_harassment", confidence=0.88)
        assert result == "BLOCK"


class TestIsLikelyDarija:
    """Tests for is_likely_darija() -- Darija detection heuristic."""

    def test_is_likely_darija_arabic_script(self):
        """Mixed Arabic + Latin script should be detected as Darija."""
        from ml_pipeline.models_pkg.language_detector import is_likely_darija
        # Mixed Arabic and Latin script: 2+ Arabic chars + 2+ Latin chars
        text = "كيفاك يا khoya"
        result = is_likely_darija(text, lang_code="ar")
        assert result is True

    def test_is_likely_darija_arabizi(self):
        """Arabizi digits (2,3,5,7,8,9 as letter substitutes) signal Darija."""
        from ml_pipeline.models_pkg.language_detector import is_likely_darija
        # "ki3ak a5i" -- digits 3 and 5 are Arabizi markers
        text = "ki3ak a5i"
        # fasttext misclassifies Arabizi as Indonesian
        result = is_likely_darija(text, lang_code="id")
        assert result is True


class TestRunPipelineStub:
    """Tests for run_pipeline_stub() -- keyword-based test pipeline."""

    def test_stub_threat_escalate(self):
        """Threat keywords should trigger ESCALATE decision."""
        result = run_pipeline_stub("I will kill you")
        assert result.decision == "ESCALATE"
        assert result.primary_class == "threat"
        assert result.is_harmful is True
        assert result.m1_score > 0.90

    def test_stub_safe_allow(self):
        """Safe text should pass through as ALLOW."""
        result = run_pipeline_stub("hello how are you")
        assert result.decision == "ALLOW"
        assert result.primary_class == "safe"
        assert result.is_harmful is False
