import uuid
from django.db import models
from django.utils import timezone

from .users import AegisUser, MonitoredChild
from .moderation import ModerationResult


# ╔══════════════════════════════════════════════════════════════╗
# ║  PACKAGE 7 — APPLICATION-LEVEL BLOCKLIST                    ║
# ║  BlockedContact                                              ║
# ╚══════════════════════════════════════════════════════════════╝

class BlockedContact(models.Model):
    """
    Application-level block. When the Enforcer decides BLOCK, the sender's JID
    is saved here. The webhook checks this table BEFORE processing any message —
    if the sender is blocked, the message is silently dropped (no pipeline, no response).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender_jid = models.CharField(max_length=255, unique=True,
        help_text="WhatsApp JID of the blocked contact")
    instance_name = models.CharField(max_length=255,
        help_text="Evolution API instance where the block was triggered")
    reason = models.CharField(max_length=50, default='BLOCK',
        help_text="Why the contact was blocked (BLOCK, ESCALATE, MANUAL)")
    blocked_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True,
        help_text="Set to False to unblock a contact")

    class Meta:
        verbose_name = "Blocked Contact"
        verbose_name_plural = "Blocked Contacts"
        ordering = ['-blocked_at']

    def __str__(self):
        return f"🚫 {self.sender_jid} (blocked {self.blocked_at.strftime('%Y-%m-%d %H:%M')})"


# ╔══════════════════════════════════════════════════════════════╗
# ║  PACKAGE 8 — REPORTS                                       ║
# ╚══════════════════════════════════════════════════════════════╝

class Report(models.Model):
    """
    Tracks AI-generated PDF reports (both scheduled and on-demand).
    Created by Django, populated by n8n.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        GENERATING = 'generating', 'Generating'
        READY = 'ready', 'Ready'
        FAILED = 'failed', 'Failed'

    class ReportType(models.TextChoices):
        SUMMARY = 'summary', 'Summary'
        FULL = 'full', 'Full Analysis'
        LEGAL = 'legal', 'Legal Evidence'
        INTELLIGENCE = 'intelligence', 'Intelligence Brief'

    class DeliveryChannel(models.TextChoices):
        EMAIL = 'email', 'Email'
        WHATSAPP = 'whatsapp', 'WhatsApp'
        BOTH = 'both', 'Email & WhatsApp'
        DASHBOARD = 'dashboard', 'Dashboard Only'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requested_by = models.ForeignKey(AegisUser, on_delete=models.CASCADE, related_name='reports')
    child = models.ForeignKey(MonitoredChild, on_delete=models.CASCADE, related_name='reports', null=True, blank=True)
    
    report_type = models.CharField(max_length=20, choices=ReportType.choices)
    period_start = models.DateField()
    period_end = models.DateField()
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    delivery_channel = models.CharField(max_length=20, choices=DeliveryChannel.choices, default=DeliveryChannel.DASHBOARD)
    
    pdf_file = models.FileField(upload_to='reports/', null=True, blank=True)
    ai_narrative = models.TextField(blank=True, default='')
    stats_json = models.JSONField(default=dict, blank=True)
    flagged_legal = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Report"
        verbose_name_plural = "Reports"
        ordering = ['-created_at']

    def __str__(self):
        return f"Report {self.report_type} ({self.status}) for {self.child.full_name if self.child else 'Admin'}"


# ╔══════════════════════════════════════════════════════════════╗
# ║  PACKAGE 9 — PLATFORM CONFIGURATION                        ║
# ║  PlatformSettings (Singleton)                              ║
# ╚══════════════════════════════════════════════════════════════╝

class PlatformSettings(models.Model):
    """
    Singleton model storing global configuration for the AEGIS platform.
    Controls AI Agent thresholds, retention policies, and global notification rules.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # 1. AI Moderation Thresholds
    ai_warn_threshold = models.FloatField(default=0.50)
    ai_review_threshold = models.FloatField(default=0.65)
    ai_block_threshold = models.FloatField(default=0.75)
    ai_critical_threshold = models.FloatField(default=0.90)
    
    # 2. Pipeline Toggles
    agent_1_enabled = models.BooleanField(default=True, help_text="Regex Gate")
    agent_2_enabled = models.BooleanField(default=True, help_text="ML Classification")
    agent_3_enabled = models.BooleanField(default=True, help_text="Semantic LLM")
    agent_4_enabled = models.BooleanField(default=True, help_text="Behavioral Engine")
    agent_5_enabled = models.BooleanField(default=True, help_text="Decision Orchestrator")
    
    # 3. LLM Infrastructure
    active_llm_provider = models.CharField(max_length=50, default='groq')
    active_llm_model = models.CharField(max_length=100, default='llama3-70b-8192')
    
    # 4. Data Retention (Days)
    log_retention_days = models.IntegerField(default=30)
    message_retention_days = models.IntegerField(default=90)
    alert_retention_days = models.IntegerField(default=365)
    
    # 5. Global Policy
    strictness_level = models.CharField(max_length=20, default='balanced')
    auto_escalate = models.BooleanField(default=True)
    block_unknown = models.BooleanField(default=False)

    # 6. Notification Defaults
    notify_email_enabled = models.BooleanField(default=True)
    notify_inapp_enabled = models.BooleanField(default=True)
    notify_on_block = models.BooleanField(default=True)
    notify_on_escalate = models.BooleanField(default=True)
    notify_on_warn = models.BooleanField(default=False)
    quiet_hours_start = models.CharField(max_length=5, default='23:00')
    quiet_hours_end = models.CharField(max_length=5, default='07:00')

    # 7. Extended Moderation Defaults
    default_language = models.CharField(max_length=10, default='auto')
    auto_resolve_allow = models.BooleanField(default=True)
    rate_limit_threshold = models.IntegerField(default=50)
    parent_portal_access = models.BooleanField(default=True)

    # 8. Risk profile history retention
    risk_profile_retention_days = models.IntegerField(default=60)

    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Platform Settings"
        verbose_name_plural = "Platform Settings"

    def __str__(self):
        return "Global Platform Configuration"

    @classmethod
    def get_settings(cls):
        """Returns the singleton instance, creating it if it doesn't exist."""
        obj, created = cls.objects.get_or_create(id=uuid.UUID('00000000-0000-0000-0000-000000000001'))
        return obj


# ╔══════════════════════════════════════════════════════════════╗
# ║  UML PACKAGE 7 — SELF-MODERATION                           ║
# ║  SelfModerationEvent                                        ║
# ╚══════════════════════════════════════════════════════════════╝

class FailedMessage(models.Model):
    """
    Crash net — when the 5-agent pipeline throws any exception, the raw message
    is persisted here so it is never silently lost. Admins can review and
    reprocess these later.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    raw_text = models.TextField(
        help_text="Original message text before pipeline processing")
    sender_jid = models.CharField(max_length=255,
        help_text="WhatsApp JID of the sender")
    instance_name = models.CharField(max_length=255,
        help_text="Evolution API instance that received the message")
    message_key_id = models.CharField(max_length=255, blank=True, default='',
        help_text="WhatsApp message key for deduplication")
    push_name = models.CharField(max_length=255, blank=True, default='',
        help_text="Display name of the sender")
    error_type = models.CharField(max_length=255,
        help_text="Exception class name (e.g. TimeoutError, OperationalError)")
    error_message = models.TextField(
        help_text="Full error traceback or message")
    pipeline_stage = models.CharField(max_length=100, blank=True, default='',
        help_text="Which agent/stage was executing when the error occurred")
    metadata = models.JSONField(default=dict, blank=True,
        help_text="Extra context: image_analyzed, is_from_me, etc.")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False,
        help_text="Set True once an admin has reviewed/reprocessed this message")

    class Meta:
        verbose_name = "Failed Message"
        verbose_name_plural = "Failed Messages"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at', 'resolved']),
        ]

    def __str__(self):
        return (f"Failed [{self.error_type}] from {self.sender_jid} "
                f"at {self.created_at.strftime('%Y-%m-%d %H:%M')}")


class SelfModerationEvent(models.Model):
    """
    Tracks when Aegis catches the CHILD'S own toxic message and sends
    an educational DM instead of a punitive warning.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    moderation_result = models.OneToOneField(ModerationResult, on_delete=models.CASCADE,
        related_name='self_moderation_event',
        help_text="The ModerationResult for the child's toxic message")
    
    category = models.CharField(max_length=50,
        help_text="Category of the child's message (e.g., verbal_harassment, threat)")
    original_decision = models.CharField(max_length=20,
        help_text="What the pipeline originally decided (BLOCK/WARN/ESCALATE) before converting to EDUCATE")
    message_deleted = models.BooleanField(default=False,
        help_text="Whether the message was deleted for everyone")
    
    educational_dm_sent = models.BooleanField(default=False,
        help_text="Whether the educational DM was sent via Aegis Assistant (Instance 2)")
    educational_dm_text = models.TextField(blank=True, default='',
        help_text="The actual text of the educational DM sent to the child")
    
    parent_notified = models.BooleanField(default=False,
        help_text="Whether the parent received a constructive notification")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Self-Moderation Event"
        verbose_name_plural = "Self-Moderation Events"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Self-Mod: {self.category} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
