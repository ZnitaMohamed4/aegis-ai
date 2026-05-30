from django.contrib import admin
from django.utils.html import format_html
from moderation.models import UserBehaviorProfile, BehavioralSnapshot


class BehavioralSnapshotInline(admin.TabularInline):
    model = BehavioralSnapshot
    extra = 0
    readonly_fields = ['date_snapshot', 'message_count', 'blocked_count', 'risk_score_snapshot']


@admin.register(UserBehaviorProfile)
class UserBehaviorProfileAdmin(admin.ModelAdmin):
    list_display = ['user_jid', 'risk_level_badge', 'risk_score',
                    'total_messages_sent', 'total_blocked_messages_sent',
                    'average_toxicity_score', 'last_updated']
    list_filter = ['risk_level']
    search_fields = ['user_jid']
    readonly_fields = ['last_updated']
    inlines = [BehavioralSnapshotInline]

    @admin.display(description='Risk')
    def risk_level_badge(self, obj):
        colors = {
            'LOW': '#27ae60', 'MEDIUM': '#f39c12',
            'HIGH': '#e74c3c', 'CRITICAL': '#8e44ad',
        }
        bg = colors.get(obj.risk_level, '#95a5a6')
        return format_html(
            '<span style="background:{}; color:white; padding:2px 8px; '
            'border-radius:10px; font-size:11px; font-weight:bold;">{}</span>',
            bg, obj.risk_level
        )


@admin.register(BehavioralSnapshot)
class BehavioralSnapshotAdmin(admin.ModelAdmin):
    list_display = ['profile', 'date_snapshot', 'message_count',
                    'blocked_count', 'risk_score_snapshot']
    list_filter = ['date_snapshot']
    raw_id_fields = ['profile']
