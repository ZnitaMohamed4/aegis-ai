import logging
import json
import time
from rest_framework.decorators import api_view, permission_classes, parser_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from django.http import StreamingHttpResponse


# ── Custom Throttle Scopes ────────────────────────────────────────────
class ChatbotThrottle(UserRateThrottle):
    """15 requests/min — protects Groq TPM budget."""
    scope = 'chatbot'


class KnowledgeUploadThrottle(UserRateThrottle):
    """10 requests/min — prevents rapid bulk uploads."""
    scope = 'knowledge_upload'

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
@throttle_classes([ChatbotThrottle])
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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([ChatbotThrottle])
def ask_chatbot_stream(request):
    """POST /api/v1/chatbot/ask-stream/

    SSE (Server-Sent Events) streaming endpoint for the chatbot.
    Sends progressive events:
      - "thinking": pipeline step updates
      - "answer_chunk": word-by-word answer delivery
      - "done": final metadata (sources, message_id, session_id)
    """
    data = request.data
    message = data.get('message', '').strip()
    session_id = data.get('session_id')
    language = data.get('language', 'fr')

    if not message:
        return Response({"error": "Message is required"}, status=400)

    def event_stream():
        """Generator that yields SSE events."""
        try:
            # Run the full pipeline
            response_data = ask_question(
                question=message,
                session_id=session_id,
                user=request.user,
                language=language
            )

            # 1. Stream thinking steps
            for step in response_data.get('thinking_steps', []):
                yield f"data: {json.dumps({'type': 'thinking', 'data': step})}\n\n"

            # 2. Stream answer word-by-word
            answer = response_data.get('answer', '')
            words = answer.split(' ')
            for i, word in enumerate(words):
                chunk = word if i == 0 else ' ' + word
                yield f"data: {json.dumps({'type': 'answer_chunk', 'data': chunk})}\n\n"
                time.sleep(0.03)  # 30ms per word — smooth streaming UX

            # 3. Send done event with metadata
            done_payload = {
                'type': 'done',
                'data': {
                    'session_id': response_data.get('session_id'),
                    'message_id': response_data.get('message_id'),
                    'source_type': response_data.get('source_type'),
                    'sources': response_data.get('sources', []),
                    'cached': response_data.get('cached', False),
                }
            }
            yield f"data: {json.dumps(done_payload)}\n\n"

        except Exception as e:
            logger.error(f"[RAG SSE] Error in stream: {e}")
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream',
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
    return response


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
        
        if s.is_proactive:
            # Proactive sessions get a special title
            proactive_msg = s.messages.filter(role='assistant', is_proactive=True).first()
            trigger_count = s.proactive_alerts.first().trigger_count if s.proactive_alerts.exists() else 0
            title = f"🛡️ Alerte proactive ({trigger_count} messages signalés)"
        else:
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
                "sources": _parse_sources(m),
                "feedback": getattr(m, 'feedback', 'none'),
                "isProactive": getattr(m, 'is_proactive', False),
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
@throttle_classes([KnowledgeUploadThrottle])
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
        # Also include semantic cache stats
        from moderation.services.cache.rag_cache import get_cache_stats
        stats["answer_cache"] = get_cache_stats()
        return Response(stats)
    except Exception as e:
        logger.error(f"[RAG API] Error in get_rag_stats: {e}")
        return Response({"error": str(e)}, status=500)


# ═══════════════════════════════════════════════════════════════════════
#  ANSWER CACHE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_answer_cache_stats(request):
    """GET /api/v1/chatbot/cache/stats/

    Returns semantic cache statistics: entry count, hit rate, TTL settings.
    """
    from moderation.services.cache.rag_cache import get_cache_stats
    try:
        return Response(get_cache_stats())
    except Exception as e:
        logger.error(f"[RAG API] Error in get_answer_cache_stats: {e}")
        return Response({"error": str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clear_answer_cache(request):
    """POST /api/v1/chatbot/cache/clear/

    Clears all cached question→answer pairs. Use after uploading
    new knowledge base documents to force fresh answers.
    """
    from moderation.services.cache.rag_cache import clear_cache
    try:
        deleted = clear_cache()
        return Response({"status": "success", "deleted_entries": deleted})
    except Exception as e:
        logger.error(f"[RAG API] Error in clear_answer_cache: {e}")
        return Response({"error": str(e)}, status=500)


# ═══════════════════════════════════════════════════════════════════════
#  USER FEEDBACK ENDPOINT
# ═══════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_message_feedback(request):
    """POST /api/v1/chatbot/feedback/

    Submit thumbs up/down feedback on a chatbot message.

    Body: {
        "message_id": "<UUID>",
        "feedback": "up" | "down",
        "comment": "optional comment"
    }
    """
    message_id = request.data.get('message_id')
    feedback = request.data.get('feedback')  # 'up' or 'down'
    comment = request.data.get('comment', '')

    if not message_id or feedback not in ('up', 'down', 'none'):
        return Response(
            {"error": "message_id and feedback ('up'|'down'|'none') are required"},
            status=400,
        )

    try:
        msg = ChatMessage.objects.get(id=message_id)
        msg.feedback = feedback
        msg.feedback_comment = comment
        msg.save(update_fields=['feedback', 'feedback_comment'])

        logger.info(
            f"[RAG FEEDBACK] {feedback.upper()} on message {message_id} "
            f"(session={msg.session_id}, comment={comment[:50]})"
        )
        return Response({"status": "success", "message_id": str(msg.id), "feedback": feedback})
    except ChatMessage.DoesNotExist:
        return Response({"error": "Message not found"}, status=404)
    except Exception as e:
        logger.error(f"[RAG API] Error in submit_message_feedback: {e}")
        return Response({"error": str(e)}, status=500)


# ═══════════════════════════════════════════════════════════════════════
#  PROACTIVE ALERT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_proactive_alerts(request):
    """GET /api/v1/chatbot/proactive-alerts/

    Returns unacknowledged proactive alerts for the current user.
    Includes the linked chat message content and session ID so the
    frontend can inject it into the chatbot UI.
    """
    from moderation.models import ProactiveAlert

    alerts = ProactiveAlert.objects.filter(
        parent=request.user,
        is_acknowledged=False,
    ).select_related('chat_session', 'chat_message').order_by('-created_at')[:10]

    data = []
    for alert in alerts:
        data.append({
            "id": str(alert.id),
            "session_id": str(alert.chat_session.id),
            "message_id": str(alert.chat_message.id),
            "content": alert.chat_message.content,
            "trigger_count": alert.trigger_count,
            "categories": alert.alert_categories,
            "created_at": alert.created_at.isoformat(),
        })

    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def acknowledge_proactive_alert(request, alert_id):
    """POST /api/v1/chatbot/proactive-alerts/<id>/acknowledge/

    Mark a proactive alert as acknowledged (dismissed).
    """
    from moderation.models import ProactiveAlert

    try:
        alert = ProactiveAlert.objects.get(id=alert_id, parent=request.user)
        alert.acknowledge()
        return Response({"status": "success", "alert_id": str(alert.id)})
    except ProactiveAlert.DoesNotExist:
        return Response({"error": "Alert not found"}, status=404)
    except Exception as e:
        logger.error(f"[RAG API] Error in acknowledge_proactive_alert: {e}")
        return Response({"error": str(e)}, status=500)
