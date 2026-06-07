"""
Tests for LangGraph routing logic (ml_pipeline/graph.py).

These are pure function tests -- no Django, no database needed.
Tests the conditional edge routing that determines which agent runs next.
"""
import pytest
from ml_pipeline.graph import route_after_pipeline


class TestRouteAfterPipeline:
    """Tests for route_after_pipeline() -- the conditional edge function."""

    def test_route_after_pipeline_needs_audit(self):
        """When needs_audit=True, route to the auditor (Agent 3)."""
        state = {"needs_audit": True}
        result = route_after_pipeline(state)
        assert result == "auditor"

    def test_route_after_pipeline_skip_to_profiler(self):
        """When needs_audit=False, skip directly to profiler (Agent 4)."""
        state = {"needs_audit": False}
        result = route_after_pipeline(state)
        assert result == "profiler"
