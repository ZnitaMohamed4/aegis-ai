"""
Webhook endpoint for the Aegis Assistant chatbot (Instance 2).
Receives messages sent directly to the Aegis bot number.

Different from webhook.py (which handles Instance 1 monitoring).
This endpoint powers the conversational chatbot experience.
"""
import json
import logging
import os
import time

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def webhook_chatbot(request):
    """
    ENDPOINT: POST /api/v1/webhook/chatbot/
    Evolution API hits this when someone messages the Aegis Assistant bot.
    """
    # Check if bot is enabled
    if not os.getenv('AEGIS_BOT_ENABLED', 'False').lower() in ('true', '1', 'yes'):
        return JsonResponse({"status": "ignored", "reason": "bot_disabled"})
    
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "reason": "invalid_json"}, status=400)

    # Only handle new messages
    if body.get("event") not in ["MESSAGES_UPSERT", "messages.upsert"]:
        return JsonResponse({"status": "ignored", "reason": "unhandled_event"})

    data = body.get("data", {})
    inner_data = data.get("message", data) if isinstance(data, dict) and "message" in data and "key" in data["message"] else data
    
    key = inner_data.get("key", {})
    message = inner_data.get("message", {})
    
    # Ignore messages older than 2 minutes (backlog on restart)
    message_timestamp = inner_data.get("messageTimestamp", 0)
    try:
        if message_timestamp and (int(time.time()) - int(message_timestamp) > 120):
            return JsonResponse({"status": "ignored", "reason": "message_too_old"})
    except (ValueError, TypeError):
        pass
    
    # Ignore messages FROM the bot itself (prevent infinite loop)
    if key.get("fromMe", False):
        return JsonResponse({"status": "ignored", "reason": "from_bot"})

    # Extract text
    raw_text = ""
    if "conversation" in message:
        raw_text = message["conversation"]
    elif "extendedTextMessage" in message:
        raw_text = message["extendedTextMessage"].get("text", "")
    elif isinstance(message, str):
        raw_text = message

    if not raw_text or not raw_text.strip():
        return JsonResponse({"status": "ignored", "reason": "no_text_content"})

    sender_jid = key.get("remoteJid", "unknown_sender")
    push_name = data.get("pushName") or inner_data.get("pushName") or "friend"
    instance_name = body.get("instance", "aegis-bot")
    
    logger.info(
        f"[CHATBOT] Incoming message from {push_name} ({sender_jid}) | "
        f"Text='{raw_text[:80]}{'...' if len(raw_text) > 80 else ''}'"
    )
    
    # ── Process with chatbot service ─────────────────────────────
    from moderation.services.chatbot_service import get_chatbot
    
    chatbot = get_chatbot()
    
    monitor_instance = os.getenv('EVOLUTION_INSTANCE_NAME', instance_name)
    is_safety_event = False
    threat_intel = None
    
    # 1. Save child's message to conversation memory
    chatbot.save_message(sender_jid, 'user', raw_text)
    
    # 2. Static keyword safety check (fast fallback)
    is_critical_keyword, matched_keyword = chatbot.check_safety_escalation(raw_text)
    if is_critical_keyword:
        is_safety_event = True
        logger.warning(f"[CHATBOT_WEBHOOK] 🚨 Keyword SAFETY ESCALATION: '{matched_keyword}'")

    # 3. Generate LLM response
    t_start = time.time()
    raw_response = chatbot.generate_response(sender_jid, raw_text)
    t_elapsed = int((time.time() - t_start) * 1000)
    
    # 4. Parse THREAT_INTEL tag from response
    response_text, threat_intel = chatbot.parse_threat_intel(raw_response)
    
    if threat_intel:
        is_safety_event = True
        logger.warning(f"[CHATBOT_WEBHOOK] 🚨 THREAT_INTEL extracted: {threat_intel.get('threat_type')} | urgency={threat_intel.get('urgency')}")
    
    # 5. Check legacy tag
    if "[SAFETY_ESCALATE]" in response_text:
        response_text = response_text.replace("[SAFETY_ESCALATE]", "").strip()
        is_safety_event = True
        logger.warning(f"[CHATBOT_WEBHOOK] 🚨 LLM Reasoned SAFETY ESCALATION detected!")
    
    # 6. Send parent alert if safety event detected
    if is_safety_event:
        if threat_intel:
            chatbot.notify_parent_safety_detailed(monitor_instance, sender_jid, threat_intel)
        else:
            chatbot.notify_parent_safety(monitor_instance, sender_jid, matched_keyword or "LLM Danger Assessment")
    
    logger.info(f"[CHATBOT] Response ({t_elapsed}ms): '{response_text[:80]}{'...' if len(response_text) > 80 else ''}'")
    
    # 7. Send clean response to child
    chatbot.send_reply(sender_jid, response_text)
    
    # 8. Save bot's response to conversation memory
    chatbot.save_message(
        sender_jid, 'assistant', response_text,
        is_safety_flagged=is_safety_event,
        threat_intel=threat_intel,
    )
    
    return JsonResponse({
        "status": "success",
        "response_length": len(response_text),
        "safety_escalation": is_safety_event,
    })
