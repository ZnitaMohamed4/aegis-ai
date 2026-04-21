"""
Shared formatting utilities for AEGIS API responses.

Previously duplicated across views.py:
  - severity_map: 5 occurrences (lines 334, 687, 910, 1416, 1464)
  - phone formatting: 4 occurrences (lines 576, 1168, 1278, 1598)

Extracted during Phase 2 audit refactoring (2026-04-21).
"""


# ── Severity Mapping ─────────────────────────────────────────────────
# Maps AI decision codes to human-readable severity labels for the UI.

SEVERITY_MAP = {
    'WARN': 'medium',
    'REVISE': 'high',
    'BLOCK': 'high',
    'ESCALATE': 'critical',
    'HUMAN_REVIEW': 'high',
    'ALLOW': 'none',
}


def get_severity(decision: str, alert_obj=None) -> str:
    """
    Returns the severity string for a moderation decision.
    If an alert object is provided and has a severity, use that instead.
    """
    if alert_obj and hasattr(alert_obj, 'severity') and alert_obj.severity:
        return alert_obj.severity
    return SEVERITY_MAP.get(decision, 'medium')


# ── Phone Number Formatting ──────────────────────────────────────────

def format_phone_number(raw_jid: str) -> str:
    """
    Formats a WhatsApp JID into a human-readable phone number.

    Examples:
        '212709731128@s.whatsapp.net' → '+212 709731128'
        '212709731128'                → '+212 709731128'
        'group-id@g.us'              → 'group-id'
    """
    raw = raw_jid.split('@')[0]
    if raw.isdigit() and len(raw) > 4:
        return f"+{raw[:3]} {raw[3:]}"
    elif raw.isdigit():
        return f"+{raw}"
    return raw


def format_group_display(jid: str) -> str:
    """
    Formats a JID for display, handling groups vs contacts.

    Examples:
        '212709731128@s.whatsapp.net' → '+212709731128'
        'group-id@g.us'              → 'Group (d-id)'
    """
    raw = jid.split('@')[0]
    if jid.endswith('@g.us'):
        return f"Group ({raw[-4:]})"
    elif jid.endswith('@s.whatsapp.net'):
        return f"+{raw}"
    return jid
