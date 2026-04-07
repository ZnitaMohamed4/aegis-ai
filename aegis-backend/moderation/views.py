import json
import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.http import JsonResponse
from django.db.models import F
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import ModerationResult, UserBehaviorProfile, SecurityAlert
from .serializers import ModerationResultSerializer

# Import the ML pipeline (Real or Stub)
if getattr(settings, 'AEGIS_STUB_MODE', False):
    from ml_pipeline.inference import run_pipeline_stub as run_pipeline
else:
    from ml_pipeline.inference import run_pipeline

logger = logging.getLogger(__name__)


def _update_behavioral_profile(sender_jid: str, result):
    """
    Agent 4 Logic:
    Updates the sender's historically tracked behavior.
    """
    profile, created = UserBehaviorProfile.objects.get_or_create(user_jid=sender_jid)
    
    profile.total_messages_sent = F('total_messages_sent') + 1
    if result.decision != ModerationResult.Decision.ALLOW:
        profile.total_blocked_messages = F('total_blocked_messages') + 1

    # Fake Risk Level Logic (This could be expanded to real Random Forest later)
    profile.save()
    profile.refresh_from_db() # Refresh F() expressions from database
    
    if profile.total_blocked_messages >= 10:
        profile.risk_level = 'CRITICAL'
    elif profile.total_blocked_messages >= 5:
        profile.risk_level = 'HIGH'
    elif profile.total_blocked_messages >= 2:
        profile.risk_level = 'MEDIUM'
    
    profile.save()


def _push_websocket_alert(alerte: SecurityAlert, moderation: ModerationResult, result):
    """
    Pushes an alert via Django Channels to the Angular Dashboard.
    """
    channel_layer = get_channel_layer()
    payload = {
        "id": str(alerte.id),
        "sender": moderation.sender_jid,
        "text": moderation.raw_text[:120],
        "decision": moderation.decision.lower(),
        "primary_class": result.primary_class,
        "secondary_class": result.secondary_class,
        "m1_score": round(moderation.toxicity_score, 4),
        "m2_confidence": round(moderation.confidence_score, 4) if moderation.confidence_score else None,
        "severity": alerte.severity,
        "timestamp": alerte.sent_at.isoformat(),
    }
    try:
        async_to_sync(channel_layer.group_send)(
            "alerts",
            {"type": "alert.message", "data": payload}
        )
        print(f"  👉 📡 [WS] SUCCESS: Alert pushed to Angular Dashboard!")
    except Exception as e:
        print(f"  👉 ❌ [WS] FAILED to push alert: {e}")


@csrf_exempt
@require_http_methods(["POST"])
def webhook_messages(request):
    """
    ENDPOINT: POST /api/v1/webhook/messages/
    This is what Evolution API hits when a WhatsApp message arrives!
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "reason": "invalid_json"}, status=400)

    # 1. Ignore anything that isn't a new message
    if body.get("event") not in ["MESSAGES_UPSERT", "messages.upsert"]:
        return JsonResponse({"status": "ignored", "reason": "unhandled_event"})

    data = body.get("data", {})
    
    # Evolution API v2 nests the actual payload inside data.message sometimes
    inner_data = data.get("message", data) if isinstance(data, dict) and "message" in data and "key" in data["message"] else data
    
    key = inner_data.get("key", {})
    message = inner_data.get("message", {})
    
    # Print the absolute raw payload so we can debug it perfectly!
    # print(f"\\n--- WEBHOOK RECEIVED [Event: {body.get('event')}] ---")
    # print(json.dumps(body, indent=2))
    # print("------------------------------------------\\n")

    # Extract conversation text. Evolution API nests this depending on the message type.
    raw_text = ""
    # 1. Plain text
    if "conversation" in message:
        raw_text = message["conversation"]
    # 2. Extended text (links, quotes, etc)
    elif "extendedTextMessage" in message:
        raw_text = message["extendedTextMessage"].get("text", "")
    # 3. Very deeply nested (sometimes Evo API v2 does this for regular messages)
    elif isinstance(message, str):
        raw_text = message

    if not raw_text or not raw_text.strip():
        print("[AEGIS-DEBUG] Ignoring because raw_text is empty")
        return JsonResponse({"status": "ignored", "reason": "no_text_content"})

    # Don't moderate messages sent *by* the system running Evolution API (UNLESS TESTING)
    # Since you are messaging yourself for tests, we will bypass this check!
    # if key.get("fromMe", False):
    #     return JsonResponse({"status": "ignored", "reason": "from_me"})

    # 2. Extract Sender Info
    instance = body.get("instance", "unknown_instance")
    sender_jid = key.get("remoteJid", "unknown_sender")
    pure_number = sender_jid.split('@')[0]
    
    is_from_me = key.get("fromMe", False)
    direction_icon = "📤 OUTGOING" if is_from_me else "📥 INCOMING"
    sender_label = "ME (Host)" if is_from_me else pure_number
    recipient_label = pure_number if is_from_me else "ME (Host)"
    
    print(f"\\n┌──────────────────────────────────────────────┐")
    print(f"│ {direction_icon} MESSAGE")
    print(f"│ 👤 Sender:    {sender_label}")
    print(f"│ 🎯 Recipient: {recipient_label}")
    print(f"│ 📝 Text:      '{raw_text[:80] + ('...' if len(raw_text) > 80 else '')}'")

    # 3. 🧠 SEND TO AI PIPELINE
    result = run_pipeline(raw_text)
    
    # Print the AI Brain Predictions
    if result.decision == 'ALLOW':
        print(f"│ 🟢 M1 (GATE):  {result.m1_score:.2f} -> SAFE")
        print(f"│ ✅ VERDICT:    ALLOW")
    else:
        print(f"│ 🔴 M1 (GATE):  {result.m1_score:.2f} -> HARMFUL")
        if result.m2_confidence is not None:
            print(f"│ 🧬 M2 (SPEC):  {result.primary_class.upper()} (Confidence: {result.m2_confidence:.2f})")
        print(f"│ 🚨 VERDICT:    {result.decision}")
    
    print(f"└──────────────────────────────────────────────┘")

    # 4. Save the result to PostgreSQL (ModerationResult)
    moderation = ModerationResult.objects.create(
        instance_name=instance,
        sender_jid=sender_jid,
        raw_text=raw_text,
        normalized_text=result.normalized_text,
        toxicity_score=result.m1_score,
        confidence_score=result.m2_confidence or 0.0,
        final_score=result.m1_score, # Can be adjusted later based on behavioral score 
        decision=result.decision,
        # Defaulting LLM for now, can be updated if 'REVISE' is triggered
        llm_triggered=(result.decision == 'REVISE'), 
    )

    # 5. Agent 4: Update behavior profile
    _update_behavioral_profile(sender_jid, moderation)

    # 6. If it's harmful, trigger an Alert
    if moderation.decision != ModerationResult.Decision.ALLOW:
        # Determine Severity based on the decision
        severity_map = {
            'WARN': 'medium',
            'REVISE': 'high',
            'BLOCK': 'high',
            'ESCALATE': 'critical'
        }
        
        alerte = SecurityAlert.objects.create(
            moderation_result=moderation,
            severity=severity_map.get(moderation.decision, 'low'),
            message_preview=raw_text[:200]
        )
        
        _push_websocket_alert(alerte, moderation, result)

    # 7. Return 200 OK so Evolution API knows we received it
    return JsonResponse({
        "status": "success",
        "decision": moderation.decision,
        "m1_score": round(moderation.toxicity_score, 4),
    })

# --- Simple endpoints for Angular to fetch historical data ---

@api_view(['GET'])
def alert_list(request):
    """GET /api/v1/alerts/ - History for the Admin Dashboard"""
    alerts = ModerationResult.objects.filter(decision__in=['BLOCK', 'ESCALATE', 'REVISE']).order_by('-created_at')[:50]
    serializer = ModerationResultSerializer(alerts, many=True)
    return Response(serializer.data)
