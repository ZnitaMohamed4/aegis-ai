from django.contrib import admin
from django.utils.html import format_html
from moderation.models import HarassmentCategory, ModerationResult


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
