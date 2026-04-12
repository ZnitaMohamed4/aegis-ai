from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

from .models import (
    AegisUser, ParentProfile, MonitoredChild,
    Conversation, Message,
    ModerationResult, HarassmentCategory,
    UserBehaviorProfile, BehavioralSnapshot,
    SecurityAlert,
    ChatSession, ChatMessage,
)


# ╔══════════════════════════════════════════════════════════════╗
# ║  UML PACKAGE 1 — USER MANAGEMENT                           ║
# ╚══════════════════════════════════════════════════════════════╝

class ParentProfileInline(admin.StackedInline):
    model = ParentProfile
    can_delete = False
    verbose_name_plural = "Parent Profile"
    fk_name = "user"
    extra = 0


@admin.register(AegisUser)
class AegisUserAdmin(UserAdmin):
    """Custom admin for AegisUser — extends Django's built-in UserAdmin."""
    list_display = ['username', 'email', 'first_name', 'last_name', 'role_badge',
                    'is_active', 'is_staff', 'created_at']
    list_filter = ['role', 'is_active', 'is_staff', 'is_superuser', 'language_preference']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'phone_number']
    ordering = ['-created_at']
    inlines = [ParentProfileInline]

    # Add our custom fields to the existing UserAdmin fieldsets
    fieldsets = UserAdmin.fieldsets + (
        ('AEGIS Settings', {
            'fields': ('role', 'language_preference', 'phone_number',
                       'auto_protection_enabled', 'notification_email'),
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('AEGIS Settings', {
            'fields': ('role', 'language_preference', 'phone_number'),
        }),
    )

    @admin.display(description='Role')
    def role_badge(self, obj):
        colors = {'admin': '#e74c3c', 'parent': '#3498db'}
        bg = colors.get(obj.role, '#95a5a6')
        return format_html(
            '<span style="background:{}; color:white; padding:3px 10px; '
            'border-radius:12px; font-size:11px; font-weight:bold;">{}</span>',
            bg, obj.get_role_display()
        )


@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'alert_threshold', 'evolution_instance_name',
                    'evolution_connected', 'receive_sms_alerts', 'created_at']
    list_filter = ['evolution_connected', 'receive_sms_alerts', 'receive_email_alerts']
    search_fields = ['user__username', 'user__email', 'evolution_instance_name']
    raw_id_fields = ['user']


@admin.register(MonitoredChild)
class MonitoredChildAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'parent', 'whatsapp_jid', 'school_name',
                    'school_level', 'is_monitored', 'linked_at']
    list_filter = ['is_monitored', 'school_level']
    search_fields = ['full_name', 'whatsapp_jid', 'whatsapp_display_number',
                     'parent__user__username']
    raw_id_fields = ['parent']
    readonly_fields = ['linked_at']


# ╔══════════════════════════════════════════════════════════════╗
# ║  UML PACKAGE 2 — MESSAGING                                 ║
# ╚══════════════════════════════════════════════════════════════╝

class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ['sender_jid', 'content', 'is_blocked', 'sent_at']
    readonly_fields = ['sent_at']
    show_change_link = True


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'contact_jid', 'child', 'platform',
                    'is_active', 'message_count', 'created_at']
    list_filter = ['platform', 'is_active']
    search_fields = ['contact_jid', 'contact_name', 'child__full_name']
    raw_id_fields = ['child']
    inlines = [MessageInline]

    @admin.display(description='Messages')
    def message_count(self, obj):
        return obj.messages.count()


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['short_content', 'sender_jid', 'is_blocked',
                    'language', 'platform', 'sent_at']
    list_filter = ['is_blocked', 'language', 'platform']
    search_fields = ['content', 'sender_jid', 'platform_message_id']
    raw_id_fields = ['conversation', 'moderation_result']
    readonly_fields = ['sent_at']

    @admin.display(description='Content')
    def short_content(self, obj):
        return obj.content[:80] + '...' if len(obj.content) > 80 else obj.content


# ╔══════════════════════════════════════════════════════════════╗
# ║  UML PACKAGE 3 — MODERATION                                ║
# ╚══════════════════════════════════════════════════════════════╝

@admin.register(HarassmentCategory)
class HarassmentCategoryAdmin(admin.ModelAdmin):
    list_display = ['code', 'label_en', 'label_fr', 'label_ar', 'severity_weight']
    search_fields = ['code', 'label_en', 'label_fr']
    ordering = ['-severity_weight']


@admin.register(ModerationResult)
class ModerationResultAdmin(admin.ModelAdmin):
    list_display = ['decision_badge', 'sender_jid', 'primary_class', 'score_display',
                    'llm_triggered', 'human_reviewed', 'created_at']
    list_filter = ['decision', 'llm_triggered', 'human_reviewed',
                   'flagged_for_review', 'primary_class']
    search_fields = ['sender_jid', 'raw_text', 'instance_name']
    raw_id_fields = ['category', 'reviewed_by']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Message', {
            'fields': ('instance_name', 'sender_jid', 'raw_text', 'normalized_text',
                       'language', 'message_key_id'),
        }),
        ('AI Analysis', {
            'fields': ('primary_class', 'category', 'toxicity_score',
                       'confidence_score', 'behavioral_risk_score', 'final_score',
                       'processing_time_ms'),
        }),
        ('Decision', {
            'fields': ('decision', 'llm_triggered', 'llm_explanation'),
        }),
        ('Human Review', {
            'fields': ('flagged_for_review', 'human_reviewed', 'human_decision',
                       'human_label', 'human_note', 'human_reviewed_at', 'reviewed_by'),
        }),
        ('Golden Dataset', {
            'fields': ('original_ai_decision', 'original_ai_label'),
            'classes': ['collapse'],
        }),
    )

    @admin.display(description='Decision')
    def decision_badge(self, obj):
        colors = {
            'ALLOW': '#27ae60', 'WARN': '#f39c12', 'BLOCK': '#e74c3c',
            'ESCALATE': '#8e44ad', 'REVISE': '#e67e22', 'HUMAN_REVIEW': '#2980b9',
        }
        bg = colors.get(obj.decision, '#95a5a6')
        return format_html(
            '<span style="background:{}; color:white; padding:2px 8px; '
            'border-radius:10px; font-size:11px;">{}</span>',
            bg, obj.decision
        )

    @admin.display(description='Scores')
    def score_display(self, obj):
        m2 = f" | M2: {obj.confidence_score:.2f}" if obj.confidence_score else ""
        return f"M1: {obj.toxicity_score:.2f}{m2}"


# ╔══════════════════════════════════════════════════════════════╗
# ║  UML PACKAGE 4 — BEHAVIORAL ANALYSIS                       ║
# ╚══════════════════════════════════════════════════════════════╝

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


# ╔══════════════════════════════════════════════════════════════╗
# ║  UML PACKAGE 5 — ALERTS & NOTIFICATIONS                    ║
# ╚══════════════════════════════════════════════════════════════╝

@admin.register(SecurityAlert)
class SecurityAlertAdmin(admin.ModelAdmin):
    list_display = ['severity_badge', 'alert_type', 'message_preview_short',
                    'recipient', 'is_read', 'is_resolved', 'parent_notified', 'sent_at']
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


# ╔══════════════════════════════════════════════════════════════╗
# ║  UML PACKAGE 6 — AWARENESS & CHATBOT                       ║
# ╚══════════════════════════════════════════════════════════════╝

class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ['sent_at']


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'user', 'language', 'is_active',
                    'message_count', 'started_at', 'ended_at']
    list_filter = ['language', 'is_active']
    search_fields = ['user__username']
    raw_id_fields = ['user']
    inlines = [ChatMessageInline]

    @admin.display(description='Messages')
    def message_count(self, obj):
        return obj.messages.count()


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['short_content', 'role', 'session', 'sent_at']
    list_filter = ['role']
    search_fields = ['content']
    raw_id_fields = ['session']
    readonly_fields = ['sent_at']

    @admin.display(description='Content')
    def short_content(self, obj):
        return obj.content[:80] + '...' if len(obj.content) > 80 else obj.content


# ── Admin Site Customization ──
admin.site.site_header = "🛡️ AEGIS AI — Administration"
admin.site.site_title = "AEGIS Admin"
admin.site.index_title = "Moderation & Monitoring Platform"
