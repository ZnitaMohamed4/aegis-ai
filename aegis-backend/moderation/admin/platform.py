from django.contrib import admin
from django.utils.html import format_html
from moderation.models import FailedMessage


@admin.register(FailedMessage)
class FailedMessageAdmin(admin.ModelAdmin):
    list_display = ['error_badge', 'sender_jid', 'instance_name',
                    'pipeline_stage', 'created_at', 'resolved']
    list_filter = ['resolved', 'pipeline_stage', 'error_type']
    search_fields = ['sender_jid', 'raw_text', 'error_message', 'message_key_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_editable = ['resolved']

    fieldsets = (
        ('Message', {
            'fields': ('raw_text', 'sender_jid', 'instance_name',
                       'message_key_id', 'push_name'),
        }),
        ('Error', {
            'fields': ('error_type', 'error_message', 'pipeline_stage'),
        }),
        ('Meta', {
            'fields': ('metadata', 'resolved', 'created_at'),
        }),
    )

    def error_badge(self, obj):
        colors = {
            'TimeoutError': '#f59e0b',
            'OperationalError': '#ef4444',
        }
        color = colors.get(obj.error_type, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px">{}</span>',
            color, obj.error_type,
        )
    error_badge.short_description = 'Error'
