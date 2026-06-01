"""
AEGIS RAG Ingest — Document Upload, Text Extraction & Chunking.

Pipeline: Upload → Extract Text → Chunk → Embed → Store in ChromaDB.
Supports PDF (via PyMuPDF), TXT, and Markdown files.
"""
import os
import uuid
import logging

from .rag_config import CHUNK_SIZE, CHUNK_OVERLAP
from .rag_retrieval import _get_embedder, _get_knowledge_collection

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  TEXT EXTRACTION
# ═══════════════════════════════════════════════════════════════════════

def _extract_text_from_file(file_obj, filename: str) -> str:
    """Extract raw text from an uploaded file (PDF or TXT)."""
    ext = os.path.splitext(filename)[1].lower()

    if ext == '.txt':
        content = file_obj.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')
        return content

    elif ext == '.pdf':
        try:
            import fitz  # PyMuPDF
            content = file_obj.read()
            doc = fitz.open(stream=content, filetype="pdf")
            text_parts = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                text_parts.append(page.get_text())
            doc.close()
            return "\n\n".join(text_parts)
        except ImportError:
            logger.error("[RAG] PyMuPDF (fitz) not installed. Install with: pip install PyMuPDF")
            raise ValueError("PDF support requires PyMuPDF. Install with: pip install PyMuPDF")

    elif ext in ('.md', '.markdown'):
        content = file_obj.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')
        return content

    else:
        raise ValueError(f"Unsupported file format: {ext}. Supported: .pdf, .txt, .md")


# ═══════════════════════════════════════════════════════════════════════
#  CHUNKING — Article-Aware Recursive Splitting
# ═══════════════════════════════════════════════════════════════════════

def _chunk_text(text: str, source_name: str, category: str, language: str) -> list[dict]:
    """
    Split text into overlapping chunks using Recursive Character Splitting.

    Strategy: Article-aware splitting for legal texts.
    - Tries to split at "Article" boundaries first to keep legal articles intact
    - Falls back to chapter/section/paragraph boundaries
    - 3000 chars per chunk with 400 char overlap
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=[
            "\nArticle ",     # Split at article boundaries first (legal texts)
            "\nChapitre ",    # Then chapter boundaries
            "\nSection ",     # Then section boundaries
            "\n\n",           # Double newline (paragraph)
            "\n",             # Single newline
            ". ",             # Sentence boundary
            " ",              # Word boundary
            "",               # Character boundary (last resort)
        ],
        length_function=len,
    )

    raw_chunks = splitter.split_text(text)

    chunks = []
    for i, chunk_text in enumerate(raw_chunks):
        # Skip chunks that are too small to be useful
        if len(chunk_text.strip()) < 50:
            continue
        chunks.append({
            "id": str(uuid.uuid4()),
            "text": chunk_text.strip(),
            "metadata": {
                "source": source_name,
                "source_type": "document",   # vs "web" for auto-learned
                "category": category,
                "language": language,
                "chunk_index": i,
                "total_chunks": len(raw_chunks),
            }
        })

    return chunks


# ═══════════════════════════════════════════════════════════════════════
#  INGESTION PIPELINE
# ═══════════════════════════════════════════════════════════════════════

def ingest_document(file_obj, filename: str, category: str, language: str, uploaded_by=None) -> dict:
    """
    Full ingestion pipeline: Upload → Extract → Chunk → Embed → Store.

    Returns:
        dict with keys: doc_id, name, chunk_count, status
    """
    from moderation.models import IndexedDocument

    # 1. Extract raw text
    logger.info(f"[RAG] Ingesting document: {filename}")
    raw_text = _extract_text_from_file(file_obj, filename)

    if not raw_text or len(raw_text.strip()) < 100:
        raise ValueError("Document is empty or too short to index.")

    # 2. Chunk the text
    chunks = _chunk_text(raw_text, filename, category, language)
    if not chunks:
        raise ValueError("No valid chunks could be extracted from this document.")

    # 3. Embed all chunks
    embedder = _get_embedder()
    if embedder is None:
        raise RuntimeError("Embedding model not available. Check server startup logs.")

    texts = [c["text"] for c in chunks]
    embeddings = embedder.encode(texts).tolist()

    # 4. Store in ChromaDB
    collection = _get_knowledge_collection()

    doc_id = str(uuid.uuid4())

    # Tag all chunks with the parent document ID for bulk deletion later
    for chunk in chunks:
        chunk["metadata"]["document_id"] = doc_id

    collection.add(
        ids=[c["id"] for c in chunks],
        embeddings=embeddings,
        documents=texts,
        metadatas=[c["metadata"] for c in chunks],
    )

    # 5. Save record in Django DB
    file_size = 0
    if hasattr(file_obj, 'size'):
        file_size = file_obj.size
    elif hasattr(file_obj, 'seek') and hasattr(file_obj, 'tell'):
        pos = file_obj.tell()
        file_obj.seek(0, 2)
        file_size = file_obj.tell()
        file_obj.seek(pos)

    doc_record = IndexedDocument.objects.create(
        id=doc_id,
        name=filename,
        category=category,
        language=language,
        chunk_count=len(chunks),
        file_size=file_size,
        status='indexed',
        uploaded_by=uploaded_by,
    )

    logger.info(f"[RAG] ✅ Indexed '{filename}': {len(chunks)} chunks stored in ChromaDB")

    return {
        "doc_id": str(doc_record.id),
        "name": filename,
        "chunk_count": len(chunks),
        "status": "indexed",
    }


def delete_document(doc_id: str):
    """Remove a document and all its chunks from ChromaDB + Django DB."""
    from moderation.models import IndexedDocument

    # 1. Remove chunks from ChromaDB by document_id metadata filter
    try:
        collection = _get_knowledge_collection()
        collection.delete(where={"document_id": doc_id})
        logger.info(f"[RAG] Deleted chunks for document {doc_id} from ChromaDB")
    except Exception as e:
        logger.error(f"[RAG] Error deleting from ChromaDB: {e}")

    # 2. Remove from Django DB
    try:
        IndexedDocument.objects.filter(id=doc_id).delete()
    except Exception as e:
        logger.error(f"[RAG] Error deleting from DB: {e}")
