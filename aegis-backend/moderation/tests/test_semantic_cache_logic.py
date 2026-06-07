"""
Tests for semantic cache gating logic (ml_pipeline/agents/auditor.py).

The semantic cache has important business rules:
- Only cache ALLOW/BLOCK/ESCALATE (decisive verdicts)
- Never cache corrected decisions (edge cases)
- Never cache WARN/REVISE/HUMAN_REVIEW (ambiguous)

These tests mock the actual ChromaDB calls and verify the gating conditions.
"""
import pytest
from unittest.mock import patch


class TestSemanticCacheLogic:
    """Tests for the semantic cache gating rules in auditor.py."""

    @patch('moderation.semantic_cache.add_to_semantic_cache')
    def test_cacheable_decisions_are_saved(self, mock_add):
        """ALLOW, BLOCK, ESCALATE verdicts should be saved to cache."""
        from ml_pipeline.agents.auditor import _try_semantic_cache_save

        # ALLOW is cacheable
        _try_semantic_cache_save("hello", {"decision": "ALLOW"}, was_corrected=False)
        assert mock_add.call_count == 1

        # BLOCK is cacheable
        _try_semantic_cache_save("bad text", {"decision": "BLOCK"}, was_corrected=False)
        assert mock_add.call_count == 2

        # ESCALATE is cacheable
        _try_semantic_cache_save("threat", {"decision": "ESCALATE"}, was_corrected=False)
        assert mock_add.call_count == 3

    @patch('moderation.semantic_cache.add_to_semantic_cache')
    def test_corrected_verdicts_not_cached(self, mock_add):
        """Corrected decisions (upward/downward) should NEVER be cached."""
        from ml_pipeline.agents.auditor import _try_semantic_cache_save

        # Corrected ALLOW should NOT be cached
        _try_semantic_cache_save("edge case", {"decision": "ALLOW"}, was_corrected=True)
        assert mock_add.call_count == 0

        # Corrected BLOCK should NOT be cached
        _try_semantic_cache_save("edge case", {"decision": "BLOCK"}, was_corrected=True)
        assert mock_add.call_count == 0

    @patch('moderation.semantic_cache.add_to_semantic_cache')
    def test_ambiguous_decisions_not_cached(self, mock_add):
        """WARN, REVISE, HUMAN_REVIEW should NEVER be cached."""
        from ml_pipeline.agents.auditor import _try_semantic_cache_save

        for decision in ["WARN", "REVISE", "HUMAN_REVIEW"]:
            _try_semantic_cache_save("ambiguous", {"decision": decision}, was_corrected=False)
            assert mock_add.call_count == 0, f"{decision} should not be cached"
