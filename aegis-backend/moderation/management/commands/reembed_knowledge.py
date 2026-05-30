"""
Management command to re-embed all knowledge base chunks after changing the embedder model.

Usage:
    python manage.py reembed_knowledge          # Re-embed knowledge base only
    python manage.py reembed_knowledge --all    # Also re-embed moderation cache
"""
import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Re-embed all knowledge base chunks with the current embedder model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Also re-embed the moderation semantic cache',
        )

    def handle(self, *args, **options):
        import chromadb
        import os
        from moderation.semantic_cache import initialize_semantic_cache

        # Force re-initialization to load the new model
        from moderation import semantic_cache
        semantic_cache._is_initialized = False
        semantic_cache.embedder = None
        initialize_semantic_cache()

        embedder = semantic_cache.embedder
        if embedder is None:
            self.stderr.write(self.style.ERROR("Failed to load embedder model!"))
            return

        self.stdout.write(f"Using embedder: {embedder.__class__.__name__}")

        chroma_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            'chroma_storage'
        )
        client = chromadb.PersistentClient(path=chroma_path)

        # 1. Re-embed knowledge base
        self._reembed_collection(client, embedder, "aegis_knowledge_base")

        # 2. Optionally re-embed moderation cache
        if options['all']:
            self._reembed_collection(client, embedder, "aegis_moderation_cache_v2")

        self.stdout.write(self.style.SUCCESS("Re-embedding complete!"))

    def _reembed_collection(self, client, embedder, collection_name):
        """Re-embed all documents in a ChromaDB collection."""
        try:
            collection = client.get_collection(collection_name)
        except Exception as e:
            self.stderr.write(f"Collection '{collection_name}' not found: {e}")
            return

        count = collection.count()
        if count == 0:
            self.stdout.write(f"  {collection_name}: empty, skipping")
            return

        self.stdout.write(f"  {collection_name}: re-embedding {count} items...")

        # Get all data
        all_data = collection.get(include=['documents', 'metadatas'])

        if not all_data['documents']:
            self.stdout.write(f"  {collection_name}: no documents found, skipping")
            return

        # Re-encode with new embedder
        new_embeddings = embedder.encode(all_data['documents']).tolist()

        # Delete all and re-add with new embeddings
        collection.delete(ids=all_data['ids'])
        collection.add(
            ids=all_data['ids'],
            embeddings=new_embeddings,
            documents=all_data['documents'],
            metadatas=all_data['metadatas'],
        )

        self.stdout.write(self.style.SUCCESS(
            f"  ✅ {collection_name}: {len(all_data['ids'])} items re-embedded successfully"
        ))
