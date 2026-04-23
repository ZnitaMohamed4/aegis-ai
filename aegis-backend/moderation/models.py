import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


# ╔══════════════════════════════════════════════════════════════╗
# ║  UML PACKAGE 1 — USER MANAGEMENT                           ║
# ║  Utilisateur, ProfilParent, UtilisateurMineur               ║
# ╚══════════════════════════════════════════════════════════════╝

class AegisUser(AbstractUser):
    """
    UML: Utilisateur (abstract base) + UtilisateurAdulte
    Custom user model for AEGIS. Replaces Django's default User.
    Roles: 'admin' (platform operator) or 'parent' (child guardian)
    Children are NOT users — they are MonitoredChild data entities.
    """
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Administrator'
        PARENT = 'parent', 'Parent / Guardian'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PARENT)
    language_preference = models.CharField(max_length=5, default='fr',
        help_text="UI language: fr, ar, en")
    phone_number = models.CharField(max_length=20, blank=True, default='',
        help_text="Primary phone for notifications")

    # UtilisateurAdulte fields (applicable to all users)
    auto_protection_enabled = models.BooleanField(default=False,
        help_text="Adult self-protection mode (monitors own messages)")
    notification_email = models.CharField(max_length=255, blank=True, default='',
        help_text="Separate email for alert notifications")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AEGIS User"
        verbose_name_plural = "AEGIS Users"

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"

    def is_admin(self):
        return self.role == self.Role.ADMIN

    def is_parent(self):
        return self.role == self.Role.PARENT

    def get_dashboard_url(self):
        return '/admin' if self.is_admin() else '/parent'


class ParentProfile(models.Model):
    """
    UML: ProfilParent
    Extended settings for parent users — alert preferences, Evolution API linkage.
    One parent can monitor multiple children.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(AegisUser, on_delete=models.CASCADE, related_name='parent_profile')

    # Alert preferences
    alert_threshold = models.FloatField(default=0.65,
        help_text="Minimum score to trigger a parent alert (0.0 - 1.0)")
    receive_sms_alerts = models.BooleanField(default=True)
    receive_email_alerts = models.BooleanField(default=True)
    receive_push_alerts = models.BooleanField(default=True)
    receive_call_on_critical = models.BooleanField(default=True,
        help_text="Automatic phone call for CRITICAL severity alerts")

    # Evolution API connection (WhatsApp bridge)
    evolution_instance_name = models.CharField(max_length=255, null=True, blank=True,
        help_text="Evolution API instance name for this parent's WhatsApp bridge")
    evolution_connected = models.BooleanField(default=False,
        help_text="Whether the Evolution API instance is currently connected")
    evolution_connected_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Parent Profile"

    def __str__(self):
        return f"Parent: {self.user.get_full_name() or self.user.username}"

    def get_monitored_children(self):
        return self.children.filter(is_monitored=True)

    def get_pending_alerts(self):
        child_jids = self.children.values_list('whatsapp_jid', flat=True)
        return SecurityAlert.objects.filter(
            moderation_result__sender_jid__in=child_jids,
            is_read=False
        )


class MonitoredChild(models.Model):
    """
    UML: UtilisateurMineur
    A child monitored through a parent's WhatsApp bridge.
    NOT a Django user — children never authenticate.
    """
    class Grade(models.TextChoices):
        PRIMAIRE = 'primaire', 'Primaire'
        COLLEGE = 'college', 'Collège'
        LYCEE = 'lycee', 'Lycée'
        UNIVERSITE = 'universite', 'Université'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent = models.ForeignKey(ParentProfile, on_delete=models.CASCADE, related_name='children')

    # Basic info
    full_name = models.CharField(max_length=255, help_text="Child's display name")
    date_of_birth = models.DateField(null=True, blank=True)
    school_name = models.CharField(max_length=255, blank=True, default='')
    school_level = models.CharField(max_length=20, choices=Grade.choices, blank=True, default='')

    # WhatsApp linkage
    whatsapp_jid = models.CharField(max_length=255, unique=True,
        help_text="WhatsApp JID (e.g., 212612345678@s.whatsapp.net)")
    whatsapp_display_number = models.CharField(max_length=30, blank=True, default='',
        help_text="Formatted display number (e.g., +212 6XX XXX X01)")

    # Monitoring state
    is_monitored = models.BooleanField(default=True)
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Monitored Child"
        verbose_name_plural = "Monitored Children"

    def __str__(self):
        return f"{self.full_name} ({self.whatsapp_display_number or self.whatsapp_jid})"

    def get_risk_level(self):
        """Get risk level based on the number of blocked messages sent to this child's instance."""
        from .models import ModerationResult
        from django.utils import timezone
        import datetime
        
        # We can look up all blocked messages associated with this child's parent instance
        # over the last 30 days.
        try:
            thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
            instance_name = self.parent.evolution_instance_name
            if not instance_name:
                return 'LOW'
                
            blocked_count = ModerationResult.objects.filter(
                instance_name=instance_name,
                decision__in=['BLOCK', 'ESCALATE', 'WARN', 'REVISE'],
                created_at__gte=thirty_days_ago
            ).count()
            
            if blocked_count >= 10:
                return 'CRITICAL'
            elif blocked_count >= 5:
                return 'HIGH'
            elif blocked_count >= 1:
                return 'MEDIUM'
            return 'LOW'
        except Exception:
            return 'LOW'


# ╔══════════════════════════════════════════════════════════════╗
# ║  UML PACKAGE 2 — MESSAGING                                 ║
# ║  Conversation, Message                                      ║
# ╚══════════════════════════════════════════════════════════════╝

class Conversation(models.Model):
    """
    UML: Conversation
    Groups messages between a specific contact and a monitored child.
    Auto-created when a new sender_jid is seen for a child.
    """
    class Platform(models.TextChoices):
        WHATSAPP = 'whatsapp', 'WhatsApp'
        TELEGRAM = 'telegram', 'Telegram'
        SIMULATED = 'simulated', 'Simulated'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    child = models.ForeignKey(MonitoredChild, on_delete=models.CASCADE,
        related_name='conversations', null=True, blank=True,
        help_text="The monitored child this conversation belongs to")

    contact_jid = models.CharField(max_length=255,
        help_text="WhatsApp JID of the external contact (the sender)")
    contact_name = models.CharField(max_length=255, blank=True, default='',
        help_text="Push name or saved contact name")

    platform = models.CharField(max_length=20, choices=Platform.choices, default=Platform.WHATSAPP)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Conversation"
        unique_together = [('child', 'contact_jid')]  # One conversation per contact+child pair
        ordering = ['-updated_at']

    def __str__(self):
        child_name = self.child.full_name if self.child else 'Unknown'
        return f"{self.contact_name or self.contact_jid} → {child_name}"

    def get_last_message(self):
        return self.messages.order_by('-sent_at').first()

    def get_blocked_count(self):
        return self.messages.filter(is_blocked=True).count()


class Message(models.Model):
    """
    UML: Message
    Individual message record with content hash and moderation link.
    Created from the webhook, links to ModerationResult for AI analysis.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE,
        related_name='messages', null=True, blank=True)

    # Content (plaintext for prototype; in production only hash is kept per Loi 09-08)
    content = models.TextField(help_text="Message content (plaintext for prototype)")
    content_hash = models.CharField(max_length=64, blank=True, default='',
        help_text="SHA-256 hash of the message content")
    language = models.CharField(max_length=20, default='unknown',
        help_text="Detected language (fr, ar, en, darija, unknown)")

    # State
    is_displayed = models.BooleanField(default=True,
        help_text="Whether the message is visible to the child")
    is_blocked = models.BooleanField(default=False,
        help_text="Whether the AI blocked this message")

    # Platform metadata
    platform = models.CharField(max_length=20, default='whatsapp')
    platform_message_id = models.CharField(max_length=255, blank=True, default='',
        help_text="Original platform message ID (Evolution API key.id)")
    sender_jid = models.CharField(max_length=255, help_text="WhatsApp JID of the sender")

    # Link to AI moderation
    moderation_result = models.OneToOneField('ModerationResult', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='message')

    sent_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Message"
        ordering = ['-sent_at']

    def __str__(self):
        preview = self.content[:50] + '...' if len(self.content) > 50 else self.content
        return f"{'🚫' if self.is_blocked else '✅'} {preview}"

    def get_moderation_result(self):
        return self.moderation_result

    def mask_content(self):
        """Privacy-safe content preview (first/last 3 chars visible)."""
        if len(self.content) <= 10:
            return '***'
        return self.content[:3] + '***' + self.content[-3:]


# ╔══════════════════════════════════════════════════════════════╗
# ║  UML PACKAGE 3 — MODERATION                                ║
# ║  ModerationResult, CategorieHarcelement                    ║
# ╚══════════════════════════════════════════════════════════════╝

class HarassmentCategory(models.Model):
    """
    UML: CategorieHarcelement
    Reference table — 6 fixed categories + 'safe'.
    Never modified at runtime. Seeded via data migration.
    """
    code = models.CharField(max_length=30, unique=True,
        help_text="Internal code: verbal_harassment, threat, sexual_harassment, discrimination, repeated_messages, identity_theft, safe")
    label_fr = models.CharField(max_length=100, help_text="French label")
    label_ar = models.CharField(max_length=100, help_text="Arabic label")
    label_en = models.CharField(max_length=100, help_text="English label")
    severity_weight = models.FloatField(default=1.0,
        help_text="Severity multiplier for score weighting (e.g., threat=1.5, safe=0.0)")
    description = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = "Harassment Category"
        verbose_name_plural = "Harassment Categories"
        ordering = ['-severity_weight']

    def __str__(self):
        return f"{self.label_en} ({self.code})"

    def get_label(self, language='en'):
        labels = {'fr': self.label_fr, 'ar': self.label_ar, 'en': self.label_en}
        return labels.get(language, self.label_en)


class ModerationResult(models.Model):
    """
    UML Package 3: Moderation (RequeteModeration + ResultatModeration merged)
    Stores the final result of the AI pipeline after analyzing a message.
    """
    class Decision(models.TextChoices):
        ALLOW = 'ALLOW', 'Allow'
        WARN = 'WARN', 'Warn'
        BLOCK = 'BLOCK', 'Block'
        ESCALATE = 'ESCALATE', 'Escalate'
        REVISE = 'REVISE', 'Revise'          # Grey zone (0.65 - 0.75)
        HUMAN_REVIEW = 'HUMAN_REVIEW', 'Human Review'  # Too ambiguous — send to human

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Message Metadata
    instance_name = models.CharField(max_length=255, help_text="Evolution API instance name")
    sender_jid = models.CharField(max_length=255, help_text="WhatsApp ID of the sender")
    raw_text = models.TextField(help_text="Original message text")
    normalized_text = models.TextField(help_text="Message text after V3 normalization")
    language = models.CharField(max_length=20, default='en', help_text="Detected language (e.g. en, fr, ar, darija)")
    message_key_id = models.CharField(max_length=255, null=True, blank=True, help_text="Evolution API message key for deletion")
    primary_class = models.CharField(max_length=50, null=True, blank=True, help_text="M2 detected category (e.g. threat, sexual_harassment)")
    
    # Sender details
    sender_name = models.CharField(max_length=255, null=True, blank=True, help_text="Push name or display name of the sender")
    is_from_me = models.BooleanField(default=False, help_text="True if the monitored child sent this message")

    # Link to harassment category reference table
    category = models.ForeignKey(HarassmentCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='moderation_results',
        help_text="Reference to the harassment category lookup table")

    # AI Scores (Agent 2 & 4)
    toxicity_score = models.FloatField(help_text="M1 toxicity score (0-1)")
    confidence_score = models.FloatField(null=True, blank=True, help_text="M2 specialist confidence score (NULL for ALLOW)")
    behavioral_risk_score = models.FloatField(default=0.0, help_text="Agent 4 score")
    final_score = models.FloatField(help_text="Combined final score")

    # Processing time
    processing_time_ms = models.IntegerField(default=0,
        help_text="Total pipeline processing time in milliseconds")

    # Decision Result
    decision = models.CharField(
        max_length=20, 
        choices=Decision.choices, 
        default=Decision.ALLOW
    )
    
    # AI Explanation (Agent 3 - LLM)
    llm_triggered = models.BooleanField(default=False)
    llm_explanation = models.TextField(null=True, blank=True)

    # Human Review / Override fields
    flagged_for_review = models.BooleanField(default=False,
        help_text="Admin flagged this message (even ALLOW) for manual review")
    human_reviewed = models.BooleanField(default=False,
        help_text="A human admin has reviewed and overridden the AI decision")
    human_decision = models.CharField(max_length=20, null=True, blank=True,
        help_text="Admin's override decision (BLOCK/WARN/ALLOW/etc.)")
    human_label = models.CharField(max_length=50, null=True, blank=True,
        help_text="Admin's corrected category (e.g. sexual_harassment)")
    human_note = models.TextField(null=True, blank=True,
        help_text="Optional admin note on the override")
    human_reviewed_at = models.DateTimeField(null=True, blank=True,
        help_text="Timestamp of when the human reviewed this message")
    reviewed_by = models.ForeignKey(AegisUser, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_moderations',
        help_text="The admin who performed the human review")

    # Golden Dataset: Preserve original AI predictions before human override
    original_ai_decision = models.CharField(max_length=20, null=True, blank=True,
        help_text="AI's original decision before human override")
    original_ai_label = models.CharField(max_length=50, null=True, blank=True,
        help_text="AI's original class label before human override")

    # 🔁 Agent 3 Correction Tracking (for ML Retraining Pipeline)
    ml_corrected = models.BooleanField(default=False,
        help_text="True when Agent 3 (Auditor) overrode the ML model's decision. Use to build retraining dataset.")
    ml_original_decision = models.CharField(max_length=20, null=True, blank=True,
        help_text="The raw ML decision BEFORE Agent 3 corrected it (e.g. BLOCK/ESCALATE overridden to ALLOW)")
    ml_original_class = models.CharField(max_length=50, null=True, blank=True,
        help_text="The raw ML category BEFORE Agent 3 corrected it (e.g. 'threat' overridden to 'safe')")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Moderation Result"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.decision} - {self.sender_jid} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

    def is_harassment(self):
        return self.decision in (self.Decision.BLOCK, self.Decision.ESCALATE, self.Decision.WARN)


# ╔══════════════════════════════════════════════════════════════╗
# ║  UML PACKAGE 4 — BEHAVIORAL ANALYSIS                       ║
# ║  UserBehaviorProfile, BehavioralSnapshot                    ║
# ╚══════════════════════════════════════════════════════════════╝

class UserBehaviorProfile(models.Model):
    """
    UML Package 4: ProfilComportementalUtilisateur
    Tracks risk level for each unique sender over time.
    Enhanced with UML fields for harasser profiling.
    """
    class RiskLevel(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        CRITICAL = 'CRITICAL', 'Critical'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_jid = models.CharField(max_length=255, unique=True)

    # UML-aligned counters
    total_messages_sent = models.IntegerField(default=0)
    total_blocked_messages_sent = models.IntegerField(default=0,
        help_text="Messages sent by this user that were blocked")
    total_blocked_messages_received = models.IntegerField(default=0,
        help_text="Blocked messages received by this user (victim metric)")
    block_ratio = models.FloatField(default=0.0,
        help_text="Ratio of blocked to total messages (0.0 - 1.0)")
    average_toxicity_score = models.FloatField(default=0.0)
    escalation_count = models.IntegerField(default=0,
        help_text="Number of ESCALATE decisions for this user")
    night_activity_ratio = models.FloatField(default=0.0,
        help_text="Ratio of messages sent between 22h-06h")
    unique_targets_count = models.IntegerField(default=0,
        help_text="Number of different people this user has harassed (harasser profiling)")
    repeated_harassers_count = models.IntegerField(default=0,
        help_text="Number of distinct harassers who targeted this user 3+ times (victim profiling)")

    # --- Tier 2 Features (Digital Twin Extended) ---
    message_frequency_1h = models.FloatField(default=0.0, help_text="Messages in last hour")
    avg_message_length = models.FloatField(default=0.0, help_text="Typical message length")
    first_seen_at = models.DateTimeField(default=timezone.now, null=True, help_text="Account age (can be backdated via WhatsApp history)")
    child_initiated = models.BooleanField(default=False, help_text="True if the child sent the very first message in the relationship")
    shared_groups_count = models.IntegerField(default=0, help_text="Number of shared WhatsApp groups (synced by background task)")
    burst_count_24h = models.IntegerField(default=0, help_text="Number of burst episodes in 24h (5+ msgs in 10 mins)")
    max_toxicity_24h = models.FloatField(default=0.0, help_text="Worst toxicity score today")
    upward_corrections_total = models.IntegerField(default=0, help_text="Times Agent 3 escalated ML decision")
    downward_corrections_total = models.IntegerField(default=0, help_text="Times Agent 3 de-escalated ML decision")
    llm_triggers_total = models.IntegerField(default=0, help_text="Total times Agent 3 was triggered")

    # Risk assessment
    risk_score = models.FloatField(default=0.0)
    risk_level = models.CharField(
        max_length=20,
        choices=RiskLevel.choices,
        default=RiskLevel.LOW,
    )

    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Behavior Profile"

    def __str__(self):
        return f"{self.user_jid} - Risk: {self.risk_level}"




class BehavioralSnapshot(models.Model):
    """
    UML: SnapshotComportemental
    Daily snapshot of a user's behavioral metrics for historical tracking.
    Enables risk trend charts and regression analysis.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(UserBehaviorProfile, on_delete=models.CASCADE,
        related_name='snapshots')

    date_snapshot = models.DateField(help_text="Date this snapshot was taken")
    message_count = models.IntegerField(default=0)
    blocked_count = models.IntegerField(default=0)
    risk_score_snapshot = models.FloatField(default=0.0)

    class Meta:
        verbose_name = "Behavioral Snapshot"
        unique_together = [('profile', 'date_snapshot')]
        ordering = ['-date_snapshot']

    def __str__(self):
        return f"{self.profile.user_jid} @ {self.date_snapshot} (risk: {self.risk_score_snapshot:.2f})"


# ╔══════════════════════════════════════════════════════════════╗
# ║  UML PACKAGE 5 — ALERTS & NOTIFICATIONS                    ║
# ║  SecurityAlert (enhanced)                                   ║
# ╚══════════════════════════════════════════════════════════════╝

class SecurityAlert(models.Model):
    """
    UML Package 5: Alerte
    Notification object generated by the moderation pipeline.
    Enhanced with UML fields: notification channel, resolution, recipient.
    """
    class AlertType(models.TextChoices):
        PUSH = 'push', 'Push Notification'
        EMAIL = 'email', 'Email'
        SMS = 'sms', 'SMS'
        CALL = 'call', 'Phone Call'

    class Severity(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        CRITICAL = 'critical', 'Critical'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    moderation_result = models.ForeignKey(ModerationResult, on_delete=models.CASCADE, related_name='alerts')

    # UML-aligned fields
    alert_type = models.CharField(max_length=10, choices=AlertType.choices, default=AlertType.PUSH,
        help_text="Notification delivery channel")
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.MEDIUM)
    message_preview = models.CharField(max_length=255)

    # Recipient — who this alert is for
    recipient = models.ForeignKey(AegisUser, on_delete=models.CASCADE,
        null=True, blank=True, related_name='received_alerts',
        help_text="User who should receive this alert (parent or admin)")

    # State
    is_read = models.BooleanField(default=False)
    is_resolved = models.BooleanField(default=False)
    parent_notified = models.BooleanField(default=False,
        help_text="External notification (SMS/email/call) was sent to parent")
    sent_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Security Alert"
        ordering = ['-sent_at']

    def __str__(self):
        return f"ALERT {self.severity} - {self.sent_at.strftime('%Y-%m-%d %H:%M')}"

    def mark_as_read(self):
        self.is_read = True
        self.save(update_fields=['is_read'])

    def resolve(self):
        self.is_resolved = True
        self.resolved_at = timezone.now()
        self.save(update_fields=['is_resolved', 'resolved_at'])


# ╔══════════════════════════════════════════════════════════════╗
# ║  UML PACKAGE 6 — AWARENESS & CHATBOT                       ║
# ║  ChatSession, ChatMessage                                   ║
# ╚══════════════════════════════════════════════════════════════╝

class ChatSession(models.Model):
    """
    UML: SessionChatbot
    A RAG chatbot conversation. Knowledge base: Loi 103-13, Loi 09-08,
    UNICEF/UNESCO guides, DGSN procedures. Available in FR/AR/EN.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(AegisUser, on_delete=models.CASCADE,
        related_name='chat_sessions', null=True, blank=True,
        help_text="Authenticated user who started this session (null for anonymous)")

    language = models.CharField(max_length=5, default='fr',
        help_text="Session language: fr, ar, en")
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Chat Session"
        ordering = ['-started_at']

    def __str__(self):
        user_name = self.user.username if self.user else 'Anonymous'
        return f"Chat: {user_name} ({self.started_at.strftime('%Y-%m-%d %H:%M')})"

    def get_history(self):
        return self.messages.order_by('sent_at')

    def get_message_count(self):
        return self.messages.count()

    def close_session(self):
        self.is_active = False
        self.ended_at = timezone.now()
        self.save(update_fields=['is_active', 'ended_at'])


class ChatMessage(models.Model):
    """
    UML: MessageChatbot
    Individual message in a chatbot session.
    Role: 'user' (human question) or 'assistant' (AI response).
    """
    class MessageRole(models.TextChoices):
        USER = 'user', 'User'
        ASSISTANT = 'assistant', 'Assistant'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')

    role = models.CharField(max_length=10, choices=MessageRole.choices)
    content = models.TextField(help_text="Message content")
    retrieved_context = models.TextField(blank=True, default='',
        help_text="RAG context chunks retrieved for this response")

    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Chat Message"
        ordering = ['sent_at']

    def __str__(self):
        preview = self.content[:40] + '...' if len(self.content) > 40 else self.content
        return f"[{self.role}] {preview}"


# ╔══════════════════════════════════════════════════════════════╗
# ║  PACKAGE 7 — APPLICATION-LEVEL BLOCKLIST                    ║
# ║  BlockedContact                                              ║
# ║  Workaround: Baileys updateBlockStatus is broken for LID    ║
# ║  contacts. This model silently drops future messages.       ║
# ╚══════════════════════════════════════════════════════════════╝

class BlockedContact(models.Model):
    """
    Application-level block. When the Enforcer decides BLOCK, the sender's JID
    is saved here. The webhook checks this table BEFORE processing any message —
    if the sender is blocked, the message is silently dropped (no pipeline, no response).
    
    This is a workaround for the Baileys bug where updateBlockStatus returns
    'bad-request' for LID contacts on all Evolution API versions.
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
