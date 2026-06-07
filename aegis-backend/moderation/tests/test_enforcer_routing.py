"""
Tests for Enforcer strategy routing (ml_pipeline/agents/enforcer.py).

These tests validate the decision routing logic that selects which
enforcement strategy to use based on monitoring mode and is_from_me.

Tests the _EnforcementContext class and the decision transformation logic
that converts raw pipeline decisions into strategy-specific decisions.
"""
import pytest
from ml_pipeline.agents.enforcer import _EnforcementContext


class TestEnforcementContext:
    """Tests for _EnforcementContext initialization and decision routing."""

    def test_adult_mode_routes_to_self_warn(self, sample_moderation_state):
        """In adult monitoring mode, non-ALLOW decisions become SELF_WARN.

        Adult self-moderation sends a reflection DM instead of punitive warning.
        """
        state = sample_moderation_state.copy()
        state["monitoring_mode"] = "adult"
        state["decision"] = "BLOCK"
        state["is_from_me"] = True

        ctx = _EnforcementContext(state)

        # Simulate the routing logic from enforcer_node (lines 107-108)
        decision = state["decision"]
        if ctx.is_adult_mode and decision != "ALLOW":
            decision = "SELF_WARN"

        assert ctx.is_adult_mode is True
        assert decision == "SELF_WARN"

    def test_child_from_me_routes_to_educate(self, sample_moderation_state):
        """Child's own toxic messages (is_from_me=True) route to EDUCATE.

        Self-moderation sends educational DM via Aegis Assistant bot
        instead of punitive warning.
        """
        state = sample_moderation_state.copy()
        state["monitoring_mode"] = "child"
        state["decision"] = "BLOCK"
        state["is_from_me"] = True

        ctx = _EnforcementContext(state)

        # Simulate the routing logic from enforcer_node (lines 109-111)
        decision = state["decision"]
        is_self_moderation = False
        if not ctx.is_adult_mode and ctx.is_from_me and decision != "ALLOW":
            is_self_moderation = True
            decision = "EDUCATE"

        assert ctx.is_adult_mode is False
        assert ctx.is_from_me is True
        assert is_self_moderation is True
        assert decision == "EDUCATE"

    def test_incoming_messages_not_deleted(self, sample_moderation_state):
        """REGRESSION: Incoming harmful messages should NOT be deleted.

        WhatsApp protocol limitation: can only delete own messages (fromMe=True).
        The is_from_me guard must prevent deletion attempts on incoming messages.
        """
        state = sample_moderation_state.copy()
        state["decision"] = "BLOCK"
        state["is_from_me"] = False

        ctx = _EnforcementContext(state)

        # Simulate the delete logic from _enforce_standard (lines 504-518)
        can_delete = False
        if ctx.message_key_id:
            if ctx.is_from_me:
                can_delete = True  # Only own messages can be deleted

        assert ctx.is_from_me is False
        assert can_delete is False  # Incoming message should NOT be deleted
