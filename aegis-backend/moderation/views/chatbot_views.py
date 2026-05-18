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
    
    print(f"\n┌──────────────────────────────────────────────┐")
    print(f"│ 🤖 AEGIS ASSISTANT — Incoming Message")
    print(f"│ 👤 From: {push_name} ({sender_jid})")
    print(f"│ 📝 Text: '{raw_text[:80]}{'...' if len(raw_text) > 80 else ''}'")
    
    # ── Process with chatbot service ─────────────────────────────
    from moderation.services.chatbot_service import get_chatbot
    
    chatbot = get_chatbot()
    
    # Step 1: Check for safety escalation keywords
    is_critical, matched_keyword = chatbot.check_safety_escalation(raw_text)
    
    if is_critical:
        print(f"│ 🚨 SAFETY ESCALATION: '{matched_keyword}'")
        # Notify parent immediately
        # Use the monitoring instance to find the child's parent
        monitor_instance = os.getenv('EVOLUTION_INSTANCE_NAME', instance_name)
        chatbot.notify_parent_safety(monitor_instance, sender_jid, matched_keyword)
    
    # Step 2: Generate empathetic response
    t_start = time.time()
    response_text = chatbot.generate_response(sender_jid, raw_text)
    t_elapsed = int((time.time() - t_start) * 1000)
    
    print(f"│ 💬 Response ({t_elapsed}ms): '{response_text[:80]}{'...' if len(response_text) > 80 else ''}'")
    
    # Step 3: Send reply
    chatbot.send_reply(sender_jid, response_text)
    
    print(f"└──────────────────────────────────────────────┘")
    
    return JsonResponse({
        "status": "success",
        "response_length": len(response_text),
        "safety_escalation": is_critical,
    })
