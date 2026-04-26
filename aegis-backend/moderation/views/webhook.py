"""
Webhook endpoint — Evolution API posts WhatsApp messages here.

Extracted from views.py during Phase 2 audit refactoring (2026-04-21).
"""
import json
import logging
import os
import time

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

import redis

# Import the LangGraph Orchestrator
from ml_pipeline.graph import aegis_graph

logger = logging.getLogger(__name__)

# ── Redis latency tracking ───────────────────────────────────────────
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/1')
try:
    redis_client = redis.from_url(redis_url)
except Exception:
    redis_client = None


def log_latency(agent, ms):
    if not redis_client: return
    key = f"latency:{agent}"
    try:
        redis_client.lpush(key, ms)
        redis_client.ltrim(key, 0, 99)
    except Exception: pass


def get_avg_latency(agent, default=0):
    if not redis_client: return default
    key = f"latency:{agent}"
    try:
        vals = redis_client.lrange(key, 0, -1)
        if not vals: return default
        return int(sum(float(v) for v in vals) / len(vals))
    except Exception: return default


@csrf_exempt
@require_http_methods(["POST"])
def webhook_messages(request):
    """
    ENDPOINT: POST /api/v1/webhook/messages/
    This is what Evolution API hits when a WhatsApp message arrives!
    """
    t_start = time.time()
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
            logger.debug("Ignoring message older than 2 minutes (backlog).")
            return JsonResponse({"status": "ignored", "reason": "message_too_old"})
    except (ValueError, TypeError):
        pass

    # Extract conversation text. Evolution API nests this depending on the message type.
    raw_text = ""
    
    # 0. Voice transcription from n8n
    if inner_data.get("is_voice_transcription") or data.get("is_voice_transcription"):
        transcribed_text = inner_data.get("transcription") or data.get("transcription") or ""
        if transcribed_text:
            raw_text = f"🎤 [Voice Message] {transcribed_text}"
        else:
            raw_text = "🎤 [Voice Message] (Transcription failed/empty)"
    # 1. Plain text
    elif "conversation" in message:
        raw_text = message["conversation"]
    # 2. Extended text (links, quotes, etc)
    elif "extendedTextMessage" in message:
        raw_text = message["extendedTextMessage"].get("text", "")
    # 3. Audio Message (Forward to n8n for transcription)
    elif "audioMessage" in message:
        logger.info("Audio message detected. Forwarding to n8n for transcription...")
        import requests
        import threading
        
        def forward_to_n8n():
            try:
                # Use the Production URL (remove '-test') so it runs automatically in the background
                requests.post("http://localhost:5678/webhook/evolution-audio", json=body, timeout=5)
            except Exception as e:
                logger.error(f"Failed to forward audio to n8n: {e}")
                
        threading.Thread(target=forward_to_n8n).start()
        
        return JsonResponse({"status": "forwarded_to_n8n", "reason": "audio_message"})
    # 4. Very deeply nested (sometimes Evo API v2 does this for regular messages)
    elif isinstance(message, str):
        raw_text = message

    if not raw_text or not raw_text.strip():
        logger.debug("Ignoring message: raw_text is empty.")
        return JsonResponse({"status": "ignored", "reason": "no_text_content"})

    # Don't moderate messages sent *by* the system running Evolution API
    if key.get("fromMe", False):
        return JsonResponse({"status": "ignored", "reason": "from_me"})

    # 2. Extract Sender Info
    instance = body.get("instance", "unknown_instance")
    sender_jid = key.get("remoteJid", "unknown_sender")
    
    sender_phone_jid = key.get("remoteJidAlt") or sender_jid

    # Note: Evolution API v2 normalizes the incoming webhook, so @lid is NOT present here.
    # We set sender_lid_jid to sender_jid (the phone string) as a base.
    # Agent 5 (Enforcer) will extract the true @lid from the sendText response later!
    sender_lid_jid = sender_jid
    
    pure_number = sender_phone_jid.split('@')[0]
    
    # Extract pushName from data or inner_data
    push_name = data.get("pushName") or inner_data.get("pushName")
    
    is_from_me = key.get("fromMe", False)
    direction_icon = "📤 OUTGOING" if is_from_me else "📥 INCOMING"
    sender_label = push_name if push_name else (pure_number if not is_from_me else "ME (Host)")
    recipient_label = pure_number if is_from_me else "ME (Host)"
    
    print(f"\n┌──────────────────────────────────────────────┐")
    print(f"│ {direction_icon} MESSAGE")
    print(f"│ 👤 Sender:    {sender_label}")
    print(f"│ 🎯 Recipient: {recipient_label}")
    print(f"│ 📝 Text:      '{raw_text[:80] + ('...' if len(raw_text) > 80 else '')}'")

    # 3. 🧠 SEND TO AI PIPELINE (LangGraph Orchestrator)
    t_ml_start = time.time()
    
    # Prepare the initial state
    initial_state = {
        "raw_text": raw_text,
        "sender_jid": sender_lid_jid,        # ← mapped to true LID
        "sender_phone_jid": sender_phone_jid,
        "instance_name": instance,
        "message_key_id": message_key_id,
        "push_name": push_name,
        "is_from_me": is_from_me
    }
    
    # 🚀 EXECUTE THE GRAPH
    final_state = aegis_graph.invoke(initial_state)
    
    t_ml_end = time.time()

    # Extract the final results from the graph's memory!
    decision = final_state.get("decision", "ALLOW")
    m1_score = final_state.get("m1_score", 0.0)
    primary_class = final_state.get("primary_class", "safe")
    m2_confidence = final_state.get("m2_confidence")
    llm_triggered = final_state.get("llm_triggered", False)
    llm_explanation = final_state.get("llm_explanation", "")
    ml_corrected = final_state.get("ml_corrected", False)

    # Print the Multi-Agent Execution Results to the console
    print(f"│ 🧭 [ORCHESTRATOR] Graph Execution Complete in {int((t_ml_end - t_ml_start) * 1000)}ms")
    print(f"│ 🛡️  [AGENT 1: GATEKEEPER] Toxicity Score: {m1_score:.2f}")
    
    if m2_confidence is not None:
        print(f"│ 🔬 [AGENT 2: CLASSIFIER] Primary Threat: {primary_class.upper()} (Confidence: {m2_confidence:.2f})")
        
    # Escalation Gate display
    escalation_risk = final_state.get("escalation_risk", 0.0)
    escalation_reason = final_state.get("escalation_reason", "")
    if escalation_risk >= 0.40:
        print(f"│ 🚨 [ESCALATION GATE] Score: {escalation_risk:.2f} — {escalation_reason}")

    if final_state.get("shadow_reviewed", False):
        print(f"│ 🕵️  [AGENT 3: AUDITOR] Triggered by Shadow Zone! Verified as {decision}")
    elif llm_triggered:
        correction_tag = " 🔁 CORRECTED ML" if ml_corrected else ""
        print(f"│ 🤖 [AGENT 3: AUDITOR] Triggered! Groq Decision: {decision} - \"{llm_explanation}\"{correction_tag}")
        
    print(f"│ 📊 [AGENT 4: PROFILER] Target Risk Score: {final_state.get('risk_score', 0.0):.2f} ({final_state.get('risk_level', 'LOW')})")
    
    # Agent 5 now runs INSIDE the graph — enforcement is complete by this point
    actions = final_state.get("enforcement_actions", [])
    alert_sev = final_state.get("alert_severity", "none") or "none"
    print(f"│ ⚡ [AGENT 5: ENFORCER] Action: {decision} | Severity: {alert_sev} | Actions: {actions}")
    
    print(f"└────────────────────────────────────────────────────────────┘")

    t_end = time.time()
    t_orch = (t_end - t_start) - (t_ml_end - t_ml_start)
    log_latency('agent_5', int(max(0, t_orch) * 1000))

    # 7. Return 200 OK so Evolution API knows we received it
    return JsonResponse({
        "status": "success",
        "decision": decision,
        "m1_score": round(m1_score, 4),
    })
