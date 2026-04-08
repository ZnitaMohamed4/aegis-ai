import json
import logging
import time
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.http import JsonResponse
from django.db.models import F
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .evolution_api import delete_message_from_whatsapp, send_aegis_warning

# for calculating some stats in the fly
from django.utils import timezone
from django.db.models import Count

from .models import ModerationResult, UserBehaviorProfile, SecurityAlert
from .serializers import ModerationResultSerializer

# import llm agent for grey zone classification
from ml_pipeline.llm_agent import analyze_grey_zone

# Import the ML pipeline (Real or Stub)
if getattr(settings, 'AEGIS_STUB_MODE', False):
    from ml_pipeline.inference import run_pipeline_stub as run_pipeline
else:
    from ml_pipeline.inference import run_pipeline

logger = logging.getLogger(__name__)


def _update_behavioral_profile(sender_jid: str, result):
    """
    Agent 4 Logic:
    Updates the sender's historically tracked behavior and computes risk score.
    """
    profile, created = UserBehaviorProfile.objects.get_or_create(user_jid=sender_jid)
    
    profile.total_messages_sent += 1
    
    # Exponential moving average for toxicity (recent messages matter more)
    alpha = 0.3 
    profile.average_toxicity_score = (profile.average_toxicity_score * (1 - alpha)) + (result.toxicity_score * alpha)
    
    if result.decision != ModerationResult.Decision.ALLOW:
        profile.total_blocked_messages += 1

    # Real-world mathematical Risk Score (0.0 to 1.0)
    # A high absolute volume of blocked messages is the strongest indicator of risk
    
    # 1. Volume Penalty: +8% risk for EVERY blocked message. 
    # (e.g. 10 blocked messages = 80% baseline risk automatically!)
    volume_penalty = profile.total_blocked_messages * 0.08
    
    # 2. Ratio Penalty: Up to +20% risk if a high percentage of their overall messages are bad
    blocked_ratio = profile.total_blocked_messages / max(1, profile.total_messages_sent)
    ratio_penalty = blocked_ratio * 0.20
    
    # 3. Toxicity Penalty: Up to +30% based on how severe the AI scores their texts on average
    toxicity_penalty = profile.average_toxicity_score * 0.30
    
    raw_risk = volume_penalty + ratio_penalty + toxicity_penalty
        
    profile.risk_score = min(1.0, max(0.0, raw_risk))
    
    # Map back to Risk Level for the Angular Dashboard icons
    if profile.risk_score >= 0.8:
        profile.risk_level = 'CRITICAL'
    elif profile.risk_score >= 0.5:
        profile.risk_level = 'HIGH'
    elif profile.risk_score >= 0.25:
        profile.risk_level = 'MEDIUM'
    else:
        profile.risk_level = 'LOW'
        
    profile.save()


def _broadcast_moderation_event(moderation: ModerationResult, result, alerte: SecurityAlert = None):
    """
    Pushes an event via Django Channels to the Angular Dashboard.
    If it's an Alert, it includes severity. If just a log, severity is none.
    """
    channel_layer = get_channel_layer()
    payload = {
        "id": str(alerte.id) if alerte else str(moderation.id),
        "type": "alert" if alerte else "log",
        "sender": moderation.sender_jid,
        "text": moderation.raw_text,
        "decision": moderation.decision.lower(),
        "primary_class": getattr(result, 'primary_class', 'safe') or 'safe',
        "m1_score": round(moderation.toxicity_score, 4),
        "m2_confidence": round(moderation.confidence_score, 4) if moderation.confidence_score else None,
        "llm_triggered": moderation.llm_triggered,
        "llm_explanation": moderation.llm_explanation,
        "severity": alerte.severity if alerte else "none",
        "timestamp": (alerte.sent_at if alerte else moderation.created_at).isoformat(),
    }
    try:
        async_to_sync(channel_layer.group_send)(
            "alerts",
            {"type": "alert.message", "data": payload}
        )
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
    message_key_id = key.get("id", None)
    message = inner_data.get("message", {})
    
    # 1.5 Ignore old messages so we don't process backlog on restart
    message_timestamp = inner_data.get("messageTimestamp", 0)
    try:
        # messageTimestamp is in seconds in Evolution API
        if message_timestamp and (int(time.time()) - int(message_timestamp) > 120):
            print("[AEGIS-DEBUG] Ignoring message because it is older than 2 minutes (backlog).")
            return JsonResponse({"status": "ignored", "reason": "message_too_old"})
    except (ValueError, TypeError):
        pass

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

    # --- NEW: AGENT 3 (LLM) INTERVENTION ---
    llm_explanation = None
    llm_triggered = False

    # If it is NOT completely safe, AND confidence is low (< 0.75), call Groq!
    if result.decision != 'ALLOW' and result.m2_confidence is not None and result.m2_confidence < 0.75:
        print(f"│ 🤖 [AGENT 3] Low confidence ({result.m2_confidence:.2f} -> {result.primary_class}). Asking Groq...")
        
        llm_response = analyze_grey_zone(raw_text, result.primary_class, result.m2_confidence, result.m1_score)
        
        # Override the ML's decisions with Groq's smart decisions
        result.decision = llm_response.get("decision", "REVISE") 
        result.primary_class = llm_response.get("category", result.primary_class)
        llm_explanation = llm_response.get("explanation", "")
        llm_triggered = True
        
        print(f"│ ✨ [AGENT 3] Groq says: {result.decision} ({result.primary_class}) - {llm_explanation}")
    # ---------------------------------------

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
        message_key_id=message_key_id,
        primary_class=getattr(result, 'primary_class', 'safe'),
        toxicity_score=result.m1_score,
        confidence_score=result.m2_confidence or 0.0,
        final_score=result.m1_score, # Can be adjusted later based on behavioral score 
        decision=result.decision,
        llm_triggered=llm_triggered,            
        llm_explanation=llm_explanation,
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
        
        _broadcast_moderation_event(moderation, result, alerte)

        # --- SPRINT 2: ACTIVE SHIELD (DELETE MESSAGE) ---
        # If the AI decided to BLOCK or ESCALATE, we remove the message from WhatsApp
        if moderation.decision in ['BLOCK', 'ESCALATE']:
            if message_key_id:
                # 'instance' was extracted from the Evolution API payload above
                delete_message_from_whatsapp(instance, message_key_id, sender_jid, is_from_me)

        # --- SPRINT 2: ACTIVE SHIELD (AUTO-REPLY) ---
        # Send a warning back to the attacker for all harmful decisions
        if moderation.decision in ['BLOCK', 'ESCALATE', 'WARN', 'REVISE']:
            # We now pass `is_from_me` and `decision` so the warning text changes appropriately
            send_aegis_warning(instance, sender_jid, result.primary_class, is_from_me, moderation.decision)
        # -----------------------------------------------
    else:
        # It's SAFE! Broadcast it so the Activity Feed shows the system actively ignoring good messages
        _broadcast_moderation_event(moderation, result)

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


@api_view(['GET'])
def dashboard_stats(request):
    """GET /api/v1/stats/dashboard/ - Live stats from PostgreSQL"""
    today = timezone.now().date()
    
    # 1. Grab all moderation results for today
    today_results = ModerationResult.objects.filter(created_at__date=today)
    
    # 2. Count the core metrics
    total_messages = today_results.count()
    total_blocked = today_results.filter(decision__in=['BLOCK', 'ESCALATE']).count()
    
    # 3. Alerts are any message that isn't 'ALLOW'
    total_alerts = SecurityAlert.objects.filter(sent_at__date=today).count()
    
    # 4. Agent 3 Interventions (LLM triggered)
    llm_interventions = ModerationResult.objects.filter(llm_triggered=True, created_at__date=today).count()
    
    # 5. At-Risk Children (Agent 4 Behavior)
    risky_profiles = UserBehaviorProfile.objects.order_by('-total_blocked_messages')[:5]
    at_risk_users = [
        {
            "id": str(p.id),
            "whatsapp": p.user_jid,
            "risk_score": p.risk_score,
            "risk_level": p.risk_level,
            "blocked_total": p.total_blocked_messages,
            "sent_total": p.total_messages_sent
        }
        for p in risky_profiles
    ]
    
    # 6. We group by primary_class (Fixed from decision)
    category_counts = today_results.exclude(primary_class='safe').values('primary_class').annotate(count=Count('id'))
    category_breakdown = {item['primary_class']: item['count'] for item in category_counts}

    # 7. Weekly Activity (Bar Chart - last 7 days)
    seven_days_ago = today - timezone.timedelta(days=6)
    recent_results = ModerationResult.objects.filter(created_at__date__gte=seven_days_ago)
    weekly_data = []
    for i in range(7):
        day_date = today - timezone.timedelta(days=6-i)
        day_results = recent_results.filter(created_at__date=day_date)
        weekly_data.append({
            "day": day_date.strftime("%a"),
            "blocked": day_results.filter(decision__in=['BLOCK', 'ESCALATE']).count(),
            "warned": day_results.filter(decision__in=['WARN', 'REVISE']).count(),
            "safe": day_results.filter(decision='ALLOW').count()
        })

    # 8. Hourly Activity (Today)
    from django.db.models.functions import ExtractHour
    hourly_counts = today_results.annotate(hour=ExtractHour('created_at')).values('hour', 'decision').annotate(count=Count('id'))
    
    hourly_data = {
        "labels": ['00h', '02h', '04h', '06h', '08h', '10h', '12h', '14h', '16h', '18h', '20h', '22h'],
        "threats": [0] * 12,
        "safe": [0] * 12
    }
    
    for entry in hourly_counts:
        hour = entry['hour']
        bucket_idx = hour // 2
        if entry['decision'] in ['BLOCK', 'ESCALATE', 'WARN', 'REVISE']:
            hourly_data["threats"][bucket_idx] += entry['count']
        elif entry['decision'] == 'ALLOW':
            hourly_data["safe"][bucket_idx] += entry['count']

    # 9. Language Distribution (Stub API)
    language_distribution = {
        "labels": ['FR', 'AR', 'EN'],
        "data": [72, 20, 8]  # Simulated percentage values
    }

    # Send the "Package" back to Angular
    return Response({
        "stats": {
            "total_messages_today": total_messages,
            "total_alerts_today": total_alerts,
            "total_blocked_today": total_blocked,
            "llm_interventions": llm_interventions,
            "avg_latency_ms": 115, # Hardcoded default for now
        },
        "category_breakdown": category_breakdown,
        "weekly_activity": weekly_data,
        "at_risk_users": at_risk_users,
        "hourly_activity": hourly_data,
        "language_distribution": language_distribution
    })

@api_view(['GET'])
def llm_audit_list(request):
    """GET /api/v1/audits/llm/ - History of LLM interventions"""
    audits = ModerationResult.objects.filter(llm_triggered=True).order_by('-created_at')[:50]
    
    data = []
    for a in audits:
        data.append({
            "id": str(a.id),
            "preview": a.raw_text[:60] + "..." if len(a.raw_text) > 60 else a.raw_text,
            "full_preview": a.raw_text,
            "tentative_label": a.primary_class or "safe",
            "queue_reason": "SCORE_AMBIGU" if a.confidence_score and a.confidence_score < 0.75 else "LANGUE_NON_IDENTIFIABLE",
            "confidence_score": a.confidence_score or 0.0,
            "toxicity_score": a.toxicity_score,
            "behavioral_risk_score": 0.5, # Safe fallback
            "final_score": a.toxicity_score,
            "language": "unknown",
            "agents_used": ["Agent 1", "Agent 2", "Agent 3"],
            "llm_explanation": a.llm_explanation,
            "submitted_at": a.created_at.isoformat(),
            "contact_number": a.sender_jid.split('@')[0],
            "decision": a.decision,
            "child": {
                "id": a.sender_jid,
                "name": a.sender_jid.split('@')[0],
                "risk_level": "medium",
                "risk_score": 0.5
            },
            "previous_messages": []
        })
    return Response(data)

@csrf_exempt
@api_view(['POST'])
def override_llm_decision(request, moderation_id):
    """POST /api/v1/audits/llm/<id>/override/ - Admin overriding LLM"""
    try:
        body = json.loads(request.body)
        new_decision = body.get("decision", "ALLOW")
        
        mod = ModerationResult.objects.get(id=moderation_id)
        mod.decision = new_decision
        mod.save()
        return Response({"status": "success", "new_decision": mod.decision})
    except Exception as e:
        return Response({"status": "error", "reason": str(e)}, status=400)
