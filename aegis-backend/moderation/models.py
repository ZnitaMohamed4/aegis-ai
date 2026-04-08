import uuid
from django.db import models

class ModerationResult(models.Model):
    """
    UML Package 3: Moderation
    Stores the final result of the AI pipeline after analyzing a message.
    """
    class Decision(models.TextChoices):
        ALLOW = 'ALLOW', 'Allow'
        WARN = 'WARN', 'Warn'
        BLOCK = 'BLOCK', 'Block'
        ESCALATE = 'ESCALATE', 'Escalate'
        REVISE = 'REVISE', 'Revise'  # Grey zone (0.65 - 0.75)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Message Metadata
    instance_name = models.CharField(max_length=255, help_text="Evolution API instance name")
    sender_jid = models.CharField(max_length=255, help_text="WhatsApp ID of the sender")
    raw_text = models.TextField(help_text="Original message text")
    normalized_text = models.TextField(help_text="Message text after V3 normalization")
    message_key_id = models.CharField(max_length=255, null=True, blank=True, help_text="Evolution API message key for deletion")
    primary_class = models.CharField(max_length=50, null=True, blank=True, help_text="M2 detected category (e.g. threat, sexual_harassment)")

    # AI Scores (Agent 2 & 4)
    toxicity_score = models.FloatField(help_text="M1 toxicity score (0-1)")
    confidence_score = models.FloatField(help_text="M2 specialist confidence score")
    behavioral_risk_score = models.FloatField(default=0.0, help_text="Agent 4 score")
    final_score = models.FloatField(help_text="Combined final score")

    # Decision Result
    decision = models.CharField(
        max_length=20, 
        choices=Decision.choices, 
        default=Decision.ALLOW
    )
    
    # AI Explanation (Agent 3 - LLM)
    llm_triggered = models.BooleanField(default=False)
    llm_explanation = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Moderation Result"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.decision} - {self.sender_jid} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"


class UserBehaviorProfile(models.Model):
    """
    UML Package 4: Behavioral Analysis
    Histories the risk level for each unique user over time.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_jid = models.CharField(max_length=255, unique=True)
    
    total_messages_sent = models.IntegerField(default=0)
    total_blocked_messages = models.IntegerField(default=0)
    average_toxicity_score = models.FloatField(default=0.0)
    risk_score = models.FloatField(default=0.0)
    
    risk_level = models.CharField(
        max_length=20, 
        default="LOW",
        help_text="LOW / MEDIUM / HIGH / CRITICAL"
    )
    
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Behavior Profile"

    def __str__(self):
        return f"{self.user_jid} - Risk: {self.risk_level}"


class SecurityAlert(models.Model):
    """
    UML Package 5: Alerts and Notifications
    Notification object pushed to the Angular dashboard in real-time.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    moderation_result = models.ForeignKey(ModerationResult, on_delete=models.CASCADE, related_name='alerts')
    
    severity = models.CharField(max_length=20) # LOW / MEDIUM / HIGH / CRITICAL
    message_preview = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Security Alert"
        ordering = ['-sent_at']

    def __str__(self):
        return f"ALERT {self.severity} - {self.sent_at.strftime('%Y-%m-%d %H:%M')}"
