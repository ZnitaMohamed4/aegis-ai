import logging
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from moderation.models import ChatSession, ChatMessage, IndexedDocument
from moderation.services.rag_service import ask_question
from moderation.services.rag_ingest import ingest_document, delete_document
from moderation.services.rag_retrieval import get_knowledge_stats
from moderation.services.rag_config import SUGGESTED_QUESTIONS

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
#  CHATBOT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ask_chatbot(request):
    """POST /api/v1/chatbot/ask/"""
    data = request.data
    message = data.get('message', '').strip()
    session_id = data.get('session_id')
    language = data.get('language', 'fr')

    if not message:
        return Response({"error": "Message is required"}, status=400)

    try:
        response_data = ask_question(
            question=message,
            session_id=session_id,
            user=request.user,
            language=language
        )
        return Response(response_data)
    except Exception as e:
        logger.error(f"[RAG API] Error in ask_chatbot: {e}")
        return Response({"error": str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def suggested_questions(request):
    """GET /api/v1/chatbot/suggested-questions/

    Returns curated starter questions for the chatbot UI based on
    the requested language.
    """
    language = request.query_params.get('language', 'fr')
    questions = SUGGESTED_QUESTIONS.get(language, SUGGESTED_QUESTIONS.get('fr', []))
    return Response(questions)


def _parse_sources(m):
    """Safely parse the retrieved_context string into a list of source dicts."""
    if m.role == 'user' or not getattr(m, 'retrieved_context', None):
        return []
    
    sources = []
    is_web = getattr(m, 'source_type', 'knowledge_base') == 'web'
    
    for c in m.retrieved_context.split("; "):
        if c.strip() and "(" in c:
            try:
                parts = c.strip().split(" (")
                name = parts[0]
                val = parts[1].replace(")", "")
                
                if is_web:
                    sources.append({"name": name, "url": val, "score": 0.0})
                else:
                    try:
                        score = float(val)
                    except ValueError:
                        score = 0.0
                    sources.append({"name": name, "score": score})
            except Exception:
                continue
    return sources


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_sessions(request):
    """GET /api/v1/chatbot/sessions/"""
    sessions = ChatSession.objects.filter(user=request.user).order_by('-started_at')
    
    data = []
    for s in sessions:
        # Title is the first user message, or default
        first_msg = s.messages.filter(role='user').order_by('sent_at').first()
        title = first_msg.content[:50] + "..." if first_msg and len(first_msg.content) > 50 else (first_msg.content if first_msg else "Nouvelle conversation")
        
        # Include messages in the response to match the frontend Conversation interface
        messages = []
        for m in s.messages.order_by('sent_at'):
            messages.append({
                "id": str(m.id),
                "role": 'bot' if m.role == 'assistant' else 'user',
                "text": m.content,
                "timestamp": m.sent_at.isoformat(),
                "source_type": getattr(m, 'source_type', 'knowledge_base'),
                "sources": _parse_sources(m)
            })

        data.append({
            "id": str(s.id),
            "title": title,
            "updatedAt": s.started_at.isoformat(), # using started_at as approximation for simplicity
            "messages": messages
        })
        
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_session_detail(request, session_id):
    """GET /api/v1/chatbot/sessions/<id>/"""
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        messages = session.messages.order_by('sent_at')
        
        data = []
        for m in messages:
            data.append({
                "id": str(m.id),
                "role": 'bot' if m.role == 'assistant' else 'user',
                "text": m.content,
                "timestamp": m.sent_at.isoformat(),
                "source_type": getattr(m, 'source_type', 'knowledge_base'),
                "sources": _parse_sources(m)
            })
        return Response(data)
    except ChatSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=404)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_chat_session(request, session_id):
    """DELETE /api/v1/chatbot/sessions/<id>/"""
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        session.delete()
        return Response({"status": "success"}, status=200)
    except ChatSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=404)
    except Exception as e:
        logger.error(f"[RAG API] Error deleting session {session_id}: {e}")
        return Response({"error": "Failed to delete session"}, status=500)


# ═══════════════════════════════════════════════════════════════════════
#  KNOWLEDGE BASE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_knowledge_document(request):
    """POST /api/v1/knowledge/upload/"""
    file_obj = request.FILES.get('file')
    language = request.data.get('language', 'fr')
    category = request.data.get('category', 'other')

    if not file_obj:
        return Response({"error": "No file uploaded"}, status=400)

    try:
        result = ingest_document(
            file_obj=file_obj,
            filename=file_obj.name,
            category=category,
            language=language,
            uploaded_by=request.user
        )
        return Response(result, status=201)
    except Exception as e:
        logger.error(f"[RAG API] Error in upload_knowledge_document: {e}")
        return Response({"error": str(e)}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_knowledge_documents(request):
    """GET /api/v1/knowledge/documents/"""
    docs = IndexedDocument.objects.all().order_by('-created_at')
    
    data = []
    for d in docs:
        data.append({
            "id": str(d.id),
            "name": d.name,
            "category": d.category,
            "language": d.language,
            "chunkCount": d.chunk_count,
            "dateAdded": d.created_at.isoformat(),
            "status": d.status,
            "size": d.file_size
        })
        
    return Response(data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_knowledge_document(request, doc_id):
    """DELETE /api/v1/knowledge/documents/<id>/"""
    try:
        delete_document(doc_id)
        return Response({"status": "success"}, status=200)
    except Exception as e:
        logger.error(f"[RAG API] Error in delete_knowledge_document: {e}")
        return Response({"error": str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_rag_stats(request):
    """GET /api/v1/knowledge/stats/"""
    try:
        stats = get_knowledge_stats()
        return Response(stats)
    except Exception as e:
        logger.error(f"[RAG API] Error in get_rag_stats: {e}")
        return Response({"error": str(e)}, status=500)
