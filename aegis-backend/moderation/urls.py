from django.urls import path
from . import views

urlpatterns = [
    # 1. Webhook - Evolution API posts here
    path('webhook/messages/', views.webhook_messages, name='webhook-messages'),
    
    # 2. REST API - Angular fetches history from here
    path('alerts/', views.alert_list, name='alert-list'),
]
