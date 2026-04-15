from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    # 1. Webhook - Evolution API posts here
    path('webhook/messages/', views.webhook_messages, name='webhook-messages'),
    
    # 2. REST API - Angular fetches history from here
    path('alerts/', views.alert_list, name='alert-list'),

    # 3. REST API - Dashboard live stats
    path('stats/dashboard/', views.dashboard_stats, name='dashboard-stats'),

    # 4. Review Queue (Agent 3 Audits + Admin flagged messages) 
    path('review/', views.review_queue_list, name='review-queue-list'),
    path('review/<str:moderation_id>/override/', views.human_override, name='human-override'),
    path('review/<str:moderation_id>/flag/', views.flag_for_review, name='flag-for-review'),

    # 5. LLM Audit Trail
    path('audits/llm/', views.llm_audit_list, name='llm-audit-list'),
    path('audits/llm/<str:moderation_id>/override/', views.override_llm_decision, name='llm-override'),

    # 6. Activity Feed (ALL decisions including ALLOW — for dashboard persistence)
    path('activity/', views.activity_feed, name='activity-feed'),

    # Admin Users endpoint
    path('admin/users/', views.admin_user_list, name='admin-user-list'),
    path('admin/users/<str:user_id>/', views.admin_user_detail, name='admin-user-detail'),
    
    # Admin Conversations 
    path('admin/conversations/', views.admin_conversations, name='admin-conversations'),
    
    # Admin Risk Profiles
    path('admin/risk-profiles/', views.admin_risk_profiles, name='admin-risk-profiles'),

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
]
