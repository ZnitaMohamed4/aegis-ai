from django.urls import path
from . import views

urlpatterns = [
    # 1. Webhook - Evolution API posts here
    path('webhook/messages/', views.webhook_messages, name='webhook-messages'),
    
    # 2. REST API - Angular fetches history from here
    path('alerts/', views.alert_list, name='alert-list'),

    # 3. REST API - Dashboard live stats
    path('stats/dashboard/', views.dashboard_stats, name='dashboard-stats'),

    # 4. Agent 3 Audits 
    path('audits/llm/', views.llm_audit_list, name='llm-audit-list'),
    path('audits/llm/<int:moderation_id>/override/', views.override_llm_decision, name='override-llm-decision'),
]
