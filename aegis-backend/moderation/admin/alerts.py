from django.contrib import admin
from django.utils.html import format_html
from moderation.models import SecurityAlert, Notification


@admin.register(SecurityAlert)
class SecurityAlertAdmin(admin.ModelAdmin):
    list_display = ['severity_badge', 'alert_type', 'message_preview_short',
                    'recipient', 'is_read', 'is_resolved', 'parent_notified',
                    'calls_made', 'sms_sent', 'sent_at']
    list_filter = ['severity', 'alert_type', 'is_read', 'is_resolved', 'parent_notified']
    search_fields = ['message_preview', 'moderation_result__sender_jid']
    raw_id_fields = ['moderation_result', 'recipient']
    readonly_fields = ['sent_at']

    @admin.display(description='Severity')
    def severity_badge(self, obj):
        colors = {
            'low': '#3498db', 'medium': '#f39c12',
            'high': '#e74c3c', 'critical': '#8e44ad',
        }
        bg = colors.get(obj.severity, '#95a5a6')
        return format_html(
            '<span style="background:{}; color:white; padding:2px 8px; '
            'border-radius:10px; font-size:11px; text-transform:uppercase;">{}</span>',
            bg, obj.severity
        )

    @admin.display(description='Preview')
    def message_preview_short(self, obj):
        return obj.message_preview[:60] + '...' if len(obj.message_preview) > 60 else obj.message_preview


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'severity_badge', 'is_read', 'created_at']
    list_filter = ['is_read', 'created_at']
    search_fields = ['user__username', 'alert__message_preview']
    raw_id_fields = ['user', 'alert']
    readonly_fields = ['created_at']

    @admin.display(description='Severity')
    def severity_badge(self, obj):
        colors = {
            'low': '#3498db', 'medium': '#f39c12',
            'high': '#e74c3c', 'critical': '#8e44ad',
        }
        bg = colors.get(obj.alert.severity, '#95a5a6')
        return format_html(
            '<span style="background:{}; color:white; padding:2px 8px; '
            'border-radius:10px; font-size:11px; text-transform:uppercase;">{}</span>',
            bg, obj.alert.severity
        )
