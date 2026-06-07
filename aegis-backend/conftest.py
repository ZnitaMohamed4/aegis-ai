"""
Shared pytest fixtures and Django settings overrides for AEGIS test suite.

Key: Override DATABASES to use SQLite in-memory so tests never touch PostgreSQL.
"""
import os
import pytest

# Force stub mode BEFORE Django settings are loaded
os.environ.setdefault('AEGIS_STUB_MODE', 'True')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')


@pytest.fixture(scope='session')
def django_db_setup():
    """Override Django's database settings for the entire test session."""
    from django.conf import settings
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'ATOMIC_REQUESTS': False,
    }


@pytest.fixture
def sample_moderation_state():
    """A minimal ModerationState dict for testing routing logic."""
    return {
        "monitoring_mode": "child",
        "raw_text": "test message",
        "sender_jid": "212600000000@s.whatsapp.net",
        "sender_phone_jid": "212600000000@s.whatsapp.net",
        "instance_name": "test-instance",
        "message_key_id": "TEST_MSG_001",
        "is_from_me": False,
        "push_name": "TestSender",
        "start_time_ms": 0,
        "image_analyzed": False,
        "image_nsfw": False,
        "image_violent": False,
        "image_nsfw_score": 0.0,
        "image_violent_score": 0.0,
        "image_ocr_text": "",
        "image_metadata": {},
        "normalized_text": None,
        "m1_score": None,
        "is_harmful": None,
        "primary_class": None,
        "secondary_class": None,
        "m2_confidence": None,
        "needs_audit": None,
        "ml_original_decision": None,
        "ml_original_class": None,
        "llm_triggered": None,
        "llm_explanation": None,
        "shadow_reviewed": None,
        "ml_corrected": None,
        "upward_corrected": None,
        "downward_corrected": None,
        "escalation_risk": None,
        "escalation_reason": None,
        "risk_score": None,
        "risk_level": None,
        "detected_language": None,
        "decision": None,
        "agent_1_2_latency_ms": None,
        "agent_3_latency_ms": None,
        "agent_4_latency_ms": None,
        "agent_5_latency_ms": None,
        "moderation_id": None,
        "alert_severity": None,
        "enforcement_actions": None,
    }
