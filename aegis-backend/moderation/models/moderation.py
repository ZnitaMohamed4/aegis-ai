import uuid
from django.db import models
from django.utils import timezone

from .users import AegisUser


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
        REVISE = 'REVISE', 'Revise'
        HUMAN_REVIEW = 'HUMAN_REVIEW', 'Human Review'
        EDUCATE = 'EDUCATE', 'Educate'
        SELF_WARN = 'SELF_WARN', 'Self Warning'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Message Metadata
    instance_name = models.CharField(max_length=255, help_text="Evolution API instance name")
    sender_jid = models.CharField(max_length=255, help_text="WhatsApp ID of the sender")
    raw_text = models.TextField(help_text="Original message text")
    normalized_text = models.TextField(help_text="Message text after V3 normalization")
    language = models.CharField(max_length=20, default='en', help_text="Detected language (e.g. en, fr, ar, darija)")
    message_key_id = models.CharField(max_length=255, null=True, blank=True, db_index=True,
        help_text="Evolution API message key for deletion and deduplication")
    primary_class = models.CharField(max_length=50, null=True, blank=True, help_text="M2 detected category (e.g. threat, sexual_harassment)")

    # Image Analysis fields
    has_image = models.BooleanField(default=False)
    image_nsfw_detected = models.BooleanField(default=False)
    image_violence_detected = models.BooleanField(default=False)
    image_nsfw_score = models.FloatField(null=True, blank=True)
    image_violence_score = models.FloatField(null=True, blank=True)
    image_ocr_text = models.TextField(null=True, blank=True)
    image_metadata = models.JSONField(null=True, blank=True, help_text="EXIF data like GPS, camera info")
    
    # Sender details
    sender_name = models.CharField(max_length=255, null=True, blank=True, help_text="Push name or display name of the sender")
    is_from_me = models.BooleanField(default=False, help_text="True if the monitored child sent this message")
    is_self_moderation = models.BooleanField(default=False, help_text="True if this was a self-moderation event (child's own toxic message caught)")

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
    processing_time_ms = models.IntegerField(default=0, help_text="Total pipeline processing time in milliseconds")

    # Decision Result
    decision = models.CharField(max_length=20, choices=Decision.choices, default=Decision.ALLOW)
    
    # AI Explanation (Agent 3 - LLM)
    llm_triggered = models.BooleanField(default=False)
    llm_explanation = models.TextField(null=True, blank=True)

    # Human Review / Override fields
    flagged_for_review = models.BooleanField(default=False, help_text="Admin flagged this message (even ALLOW) for manual review")
    human_reviewed = models.BooleanField(default=False, help_text="A human admin has reviewed and overridden the AI decision")
    human_decision = models.CharField(max_length=20, null=True, blank=True, help_text="Admin's override decision (BLOCK/WARN/ALLOW/etc.)")
    human_label = models.CharField(max_length=50, null=True, blank=True, help_text="Admin's corrected category (e.g. sexual_harassment)")
    human_note = models.TextField(null=True, blank=True, help_text="Optional admin note on the override")
    human_reviewed_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp of when the human reviewed this message")
    reviewed_by = models.ForeignKey(AegisUser, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_moderations',
        help_text="The admin who performed the human review")

    # Golden Dataset
    original_ai_decision = models.CharField(max_length=20, null=True, blank=True, help_text="AI's original decision before human override")
    original_ai_label = models.CharField(max_length=50, null=True, blank=True, help_text="AI's original class label before human override")

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
