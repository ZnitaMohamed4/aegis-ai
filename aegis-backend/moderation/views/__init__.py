"""
moderation/views — Split from the original 1,611-line views.py God File.

Re-exports all view functions so urls.py can continue using:
    from . import views
    path('webhook/messages/', views.webhook_messages, ...)

Phase 2 audit refactoring (2026-04-21).
"""

# Webhook
from moderation.views.webhook import webhook_messages

# Chatbot (Aegis Assistant — Instance 2)
from moderation.views.chatbot_views import webhook_chatbot

# Admin endpoints
from moderation.views.admin_views import (
    alert_list,
    resolve_alert,
    review_queue_list,
    review_queue_stats,
    human_override,
    admin_user_detail,
    admin_user_list,
    admin_conversations,
    flag_for_review,
    dashboard_stats,
    llm_audit_list,
    override_llm_decision,
    activity_feed,
    admin_risk_profiles,
    admin_settings,
    admin_children,
    admin_analytics,
    admin_channels,
    admin_channels_disconnect,
    test_llm_connection,
    simulate_message,
    agent_latencies,
    bn_inference,
)

# Auth + WhatsApp setup
from moderation.views.auth_views import (
    register_parent,
    current_user,
    generate_whatsapp_qr,
    check_whatsapp_status,
)

# Parent-scoped endpoints
from moderation.views.parent_views import (
    parent_dashboard_stats,
    parent_alert_list,
    parent_activity_feed,
    parent_blocked_messages,
    parent_conversations,
    parent_risk_profile,
    parent_digital_citizenship,
    parent_emotional_heatmap,
    parent_export_evidence,
)

# Reports
from moderation.views.report_views import (
    parent_report_list,
    admin_report_list,
    generate_report,
    report_complete_webhook,
    download_report,
)

# RAG Knowledge Base + Chatbot
from moderation.views.rag_views import (
    ask_chatbot,
    suggested_questions,
    get_chat_sessions,
    get_chat_session_detail,
    delete_chat_session,
    upload_knowledge_document,
    get_knowledge_documents,
    delete_knowledge_document,
    get_rag_stats,
)

# Health Check
from moderation.views.health_views import health_check

__all__ = [
    'webhook_messages',
    'webhook_chatbot',
    'alert_list',
    'resolve_alert',
    'review_queue_list',
    'review_queue_stats',
    'human_override',
    'admin_user_detail',
    'admin_user_list',
    'admin_conversations',
    'flag_for_review',
    'dashboard_stats',
    'llm_audit_list',
    'override_llm_decision',
    'activity_feed',
    'admin_risk_profiles',
    'admin_settings',
    'admin_children',
    'admin_analytics',
    'admin_channels',
    'admin_channels_disconnect',
    'test_llm_connection',
    'simulate_message',
    'agent_latencies',
    'bn_inference',
    'register_parent',
    'current_user',
    'generate_whatsapp_qr',
    'check_whatsapp_status',
    'parent_dashboard_stats',
    'parent_alert_list',
    'parent_activity_feed',
    'parent_blocked_messages',
    'parent_conversations',
    'parent_risk_profile',
    'parent_digital_citizenship',
    'parent_emotional_heatmap',
    'parent_export_evidence',
    'parent_report_list',
    'admin_report_list',
    'generate_report',
    'report_complete_webhook',
    'download_report',
    'ask_chatbot',
    'suggested_questions',
    'get_chat_sessions',
    'get_chat_session_detail',
    'delete_chat_session',
    'upload_knowledge_document',
    'get_knowledge_documents',
    'delete_knowledge_document',
    'get_rag_stats',
    'health_check',
]
