import uuid
from django.db import models

from .users import AegisUser


# ╔══════════════════════════════════════════════════════════════╗
# ║  PACKAGE 10 — RAG KNOWLEDGE BASE                           ║
# ║  IndexedDocument                                             ║
# ╚══════════════════════════════════════════════════════════════╝

class IndexedDocument(models.Model):
    """
    Tracks documents uploaded to the AEGIS RAG knowledge base.
    Each document is chunked, embedded, and stored in ChromaDB.
    This model is the Django-side record for UI display and management.
    """
    class Status(models.TextChoices):
        PROCESSING = 'processing', 'Processing'
        INDEXED = 'indexed', 'Indexed'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text="Original filename")
    category = models.CharField(max_length=50, default='other',
        help_text="Document category: legal, guides, procedures, definitions, other")
    language = models.CharField(max_length=5, default='fr',
        help_text="Document language: fr, ar, en")
    chunk_count = models.IntegerField(default=0,
        help_text="Number of text chunks created from this document")
    file_size = models.IntegerField(default=0,
        help_text="Original file size in bytes")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROCESSING)
    uploaded_by = models.ForeignKey(AegisUser, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='uploaded_documents')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Indexed Document"
        verbose_name_plural = "Indexed Documents"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.status}, {self.chunk_count} chunks)"
