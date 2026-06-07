"""
Tests for the escalation gate (ml_pipeline/agents/escalation.py).

The escalation gate combines 4 signals: burst rate, toxicity trend,
profiler risk, and keyword detection. These tests verify each signal
contributes correctly to the composite score.
"""
import pytest
from unittest.mock import patch, MagicMock
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from datetime import timedelta


class TestEscalationGate:
    """Tests for compute_escalation_risk() -- the behavioral escalation gate."""

    @pytest.mark.django_db
    @patch('moderation.models.ModerationResult')
    def test_zero_signals_returns_zero(self, mock_mr):
        """No recent messages should return 0.0 escalation risk."""
        from ml_pipeline.agents.escalation import compute_escalation_risk

        mock_mr.objects.filter.return_value.order_by.return_value = []

        score, reason = compute_escalation_risk(
            sender_jid="212600000000@s.whatsapp.net",
            instance_name="test-instance",
            current_m1=0.05,
        )
        assert score == 0.0
        assert reason == ""

    @pytest.mark.django_db
    @patch('moderation.models.UserBehaviorProfile')
    @patch('moderation.models.ModerationResult')
    def test_burst_rate_contributes_to_score(self, mock_mr, mock_profile):
        """5+ messages in 10 minutes should trigger burst signal."""
        from ml_pipeline.agents.escalation import compute_escalation_risk

        # Create 6 mock recent messages
        now = timezone.now()
        mock_messages = []
        for i in range(6):
            msg = MagicMock()
            msg.toxicity_score = 0.10
            msg.raw_text = "hello"
            msg.created_at = now - timedelta(minutes=i)
            mock_messages.append(msg)

        mock_mr.objects.filter.return_value.order_by.return_value = mock_messages
        # Make DoesNotExist a real exception class so `except` works
        mock_profile.DoesNotExist = ObjectDoesNotExist
        mock_profile.objects.get.side_effect = ObjectDoesNotExist("Profile not found")

        score, reason = compute_escalation_risk(
            sender_jid="212600000000@s.whatsapp.net",
            instance_name="test-instance",
            current_m1=0.10,
        )

        # Burst score: min(1.0, 6/5.0) * 0.35 = 0.35
        assert score > 0.30
        assert "burst" in reason

    @pytest.mark.django_db
    @patch('moderation.models.UserBehaviorProfile')
    @patch('moderation.models.ModerationResult')
    def test_threat_keyword_contributes(self, mock_mr, mock_profile):
        """A message containing a threat phrase should add keyword score."""
        from ml_pipeline.agents.escalation import compute_escalation_risk

        now = timezone.now()
        msg = MagicMock()
        msg.toxicity_score = 0.10
        msg.raw_text = "i will kill you after school"
        msg.created_at = now

        mock_mr.objects.filter.return_value.order_by.return_value = [msg]
        mock_profile.DoesNotExist = ObjectDoesNotExist
        mock_profile.objects.get.side_effect = ObjectDoesNotExist("Profile not found")

        score, reason = compute_escalation_risk(
            sender_jid="212600000000@s.whatsapp.net",
            instance_name="test-instance",
            current_m1=0.10,
        )

        # Keyword score is 0.15 when hit
        assert "threat-keyword" in reason
        assert score >= 0.15
