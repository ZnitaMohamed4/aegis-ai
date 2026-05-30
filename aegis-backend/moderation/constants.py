"""
Centralized constants for the AEGIS moderation backend.
Extracted from formatters.py to eliminate hardcoded mappings across views and services.
"""

# Maps AI decision codes to human-readable severity labels for the UI
SEVERITY_MAP = {
    'WARN': 'medium',
    'REVISE': 'high',
    'BLOCK': 'high',
    'ESCALATE': 'critical',
    'HUMAN_REVIEW': 'high',
    'EDUCATE': 'low',      # Self-moderation — educational, not punitive
    'ALLOW': 'none',
}
