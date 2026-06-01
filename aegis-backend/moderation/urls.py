from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    # 1. Webhooks - Evolution API posts here
    path('webhook/messages/', views.webhook_messages, name='webhook-messages'),
    path('webhook/chatbot/', views.webhook_chatbot, name='webhook-chatbot'),
    
    # 2. REST API - Angular fetches history from here
    path('alerts/', views.alert_list, name='alert-list'),
    path('alerts/<str:alert_id>/resolve/', views.resolve_alert, name='resolve-alert'),

    # 3. REST API - Dashboard live stats
    path('stats/dashboard/', views.dashboard_stats, name='dashboard-stats'),

    # 4. Review Queue (Agent 3 Audits + Admin flagged messages) 
    path('review/', views.review_queue_list, name='review-queue-list'),
    path('review/stats/', views.review_queue_stats, name='review-queue-stats'),
    path('review/<str:moderation_id>/override/', views.human_override, name='human-override'),
    path('review/<str:moderation_id>/flag/', views.flag_for_review, name='flag-for-review'),

    # 5. LLM Audit Trail
    path('audits/llm/', views.llm_audit_list, name='llm-audit-list'),
    path('audits/llm/<str:moderation_id>/override/', views.override_llm_decision, name='llm-override'),

    # 6. Activity Feed (ALL decisions including ALLOW — for dashboard persistence)
    path('activity/', views.activity_feed, name='activity-feed'),

    # RAG Chatbot
    path('chatbot/ask/', views.ask_chatbot, name='chatbot-ask'),
    path('chatbot/suggested-questions/', views.suggested_questions, name='chatbot-suggested-questions'),
    path('chatbot/sessions/', views.get_chat_sessions, name='chatbot-sessions'),
    path('chatbot/sessions/<str:session_id>/', views.get_chat_session_detail, name='chatbot-session-detail'),
    path('chatbot/sessions/<str:session_id>/delete/', views.delete_chat_session, name='chatbot-session-delete'),

    # Knowledge Base
    path('knowledge/upload/', views.upload_knowledge_document, name='knowledge-upload'),
    path('knowledge/documents/', views.get_knowledge_documents, name='knowledge-documents'),
    path('knowledge/documents/<str:doc_id>/', views.delete_knowledge_document, name='knowledge-document-delete'),
    path('knowledge/stats/', views.get_rag_stats, name='knowledge-stats'),

    # Admin Users endpoint
    path('admin/users/', views.admin_user_list, name='admin-user-list'),
    path('admin/users/<str:user_id>/', views.admin_user_detail, name='admin-user-detail'),
    
    # Admin Conversations 
    path('admin/conversations/', views.admin_conversations, name='admin-conversations'),
    
    # Admin Risk Profiles
    path('admin/risk-profiles/', views.admin_risk_profiles, name='admin-risk-profiles'),

    # Admin Settings (Platform Config)
    path('admin/settings/', views.admin_settings, name='admin-settings'),
    
    # Admin Children (for report generation dropdown)
    path('admin/children/', views.admin_children, name='admin-children'),
    
    # Admin Channels (Evolution API instance monitoring + emergency force-logout)
    path('admin/channels/', views.admin_channels, name='admin-channels'),
    path('admin/channels/<str:instance_id>/', views.admin_channels_disconnect, name='admin-channels-disconnect'),
    
    # Admin Analytics (Historical Dashboard Data)
    path('admin/analytics/', views.admin_analytics, name='admin-analytics'),

    # Admin AI Config Operational Endpoints
    path('admin/test-llm/', views.test_llm_connection, name='admin-test-llm'),
    path('admin/simulate/', views.simulate_message, name='admin-simulate'),
    path('admin/agent-latencies/', views.agent_latencies, name='admin-agent-latencies'),

    # 7. Auth Endpoints
    path('auth/register/', views.register_parent, name='auth-register'),
    path('auth/login/', TokenObtainPairView.as_view(), name='auth-login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='auth-refresh'),
    path('auth/me/', views.current_user, name='auth-me'),
    path('auth/qr-code/', views.generate_whatsapp_qr, name='auth-qr-code'),
    path('auth/check-connection/', views.check_whatsapp_status, name='auth-check-connection'),

    # 8. Parent-Scoped Endpoints (filtered to logged-in parent's child only)
    path('parent/stats/', views.parent_dashboard_stats, name='parent-stats'),
    path('parent/alerts/', views.parent_alert_list, name='parent-alerts'),
    path('parent/activity/', views.parent_activity_feed, name='parent-activity'),
    path('parent/blocked-messages/', views.parent_blocked_messages, name='parent-blocked-messages'),
    path('parent/conversations/', views.parent_conversations, name='parent-conversations'),
    path('parent/risk-profile/', views.parent_risk_profile, name='parent-risk-profile'),
    path('parent/digital-citizenship/', views.parent_digital_citizenship, name='parent-digital-citizenship'),
    path('parent/emotional-heatmap/', views.parent_emotional_heatmap, name='parent-emotional-heatmap'),
    path('parent/export-evidence/', views.parent_export_evidence, name='parent-export-evidence'),
    
    # 9. Reports Endpoints
    path('parent/reports/', views.parent_report_list, name='parent-report-list'),
    path('admin/reports/', views.admin_report_list, name='admin-report-list'),
    path('reports/generate/', views.generate_report, name='report-generate'),
    path('reports/<str:report_id>/download/', views.download_report, name='report-download'),
    path('reports/<str:report_id>/complete/', views.report_complete_webhook, name='report-complete-webhook'),
]
