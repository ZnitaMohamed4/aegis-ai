import uuid
from django.db import models
from django.utils import timezone

from .users import AegisUser


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
    source_type = models.CharField(max_length=20, default='knowledge_base',
        help_text="Where the answer came from: knowledge_base, web, hybrid")

    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Chat Message"
        ordering = ['sent_at']

    def __str__(self):
        preview = self.content[:40] + '...' if len(self.content) > 40 else self.content
        return f"[{self.role}] {preview}"


# ╔══════════════════════════════════════════════════════════════╗
# ║  UML PACKAGE 11 — BOT CONVERSATION MEMORY                  ║
# ║  BotConversation                                             ║
# ╚══════════════════════════════════════════════════════════════╝

class BotConversation(models.Model):
    """
    Stores child ↔ Aegis Bot conversation history for LLM memory.
    
    Each row is a single message (either from the child or the bot).
    Used by chatbot_service.py to fetch the last N exchanges before
    generating a response, giving the bot conversational context.
    
    Safety-flagged messages and extracted threat intelligence are 
    stored here for audit trail and parent alert generation.
    """
    class Role(models.TextChoices):
        USER = 'user', 'User (Child)'
        ASSISTANT = 'assistant', 'Assistant (Bot)'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    child_jid = models.CharField(max_length=255, db_index=True,
        help_text="WhatsApp JID of the child")
    role = models.CharField(max_length=10, choices=Role.choices,
        help_text="Who sent this message: 'user' (child) or 'assistant' (bot)")
    content = models.TextField(
        help_text="The message text content")
    
    # Safety escalation tracking
    is_safety_flagged = models.BooleanField(default=False,
        help_text="True if this message triggered a safety escalation")
    threat_intel = models.JSONField(null=True, blank=True,
        help_text="Extracted threat intelligence: {threat_type, perpetrator, location, urgency, summary}")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Bot Conversation Message"
        verbose_name_plural = "Bot Conversation Messages"
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['child_jid', 'created_at']),
        ]
    
    def __str__(self):
        preview = self.content[:50] + '...' if len(self.content) > 50 else self.content
        flag = "🚨" if self.is_safety_flagged else ""
        return f"[{self.role}] {flag}{preview}"

    @classmethod
    def cleanup_old(cls, days=30):
        """Remove conversation history older than N days."""
        from django.utils import timezone
        import datetime
        cutoff = timezone.now() - datetime.timedelta(days=days)
        deleted, _ = cls.objects.filter(created_at__lt=cutoff).delete()
        return deleted
