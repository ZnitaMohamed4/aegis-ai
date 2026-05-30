import uuid
from django.db import models
from django.utils import timezone

from .users import MonitoredChild


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
    moderation_result = models.OneToOneField('moderation.ModerationResult', on_delete=models.SET_NULL,
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
