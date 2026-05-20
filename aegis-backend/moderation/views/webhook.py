"""
Webhook endpoint — Evolution API posts WhatsApp messages here.

Extracted from views.py during Phase 2 audit refactoring (2026-04-21).
"""
import json
import logging
import os
import time

# The Aegis Bot's WhatsApp JID — messages FROM the child TO the bot must be
# excluded from the moderation pipeline (they're private chats with the assistant).
# Format: 212XXXXXXXXX@s.whatsapp.net (phone number without leading +)
AEGIS_BOT_JID = os.getenv('AEGIS_BOT_JID', '212668896664@s.whatsapp.net')

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
    # 4. Image Message (ViT + OCR Pipeline)
    is_image = False
    image_msg = None
    if "imageMessage" in message:
        is_image = True
        image_msg = message["imageMessage"]
    elif "documentMessage" in message and message["documentMessage"].get("mimetype", "").startswith("image/"):
        is_image = True
        image_msg = message["documentMessage"]
    elif "documentWithCaptionMessage" in message:
        doc_msg = message["documentWithCaptionMessage"].get("message", {}).get("documentMessage", {})
        if doc_msg.get("mimetype", "").startswith("image/"):
            is_image = True
            image_msg = doc_msg
            # The caption is sometimes at the top level of documentWithCaptionMessage
            if not image_msg.get("caption"):
                image_msg["caption"] = message["documentWithCaptionMessage"].get("message", {}).get("caption", "")

    if is_image:
        caption = image_msg.get("caption", "")
        
        logger.info("Image (or Document Image) detected. Running multimodal analysis...")
        from ml_pipeline.image_analyzer import analyze_image
        image_result = analyze_image(body.get("instance", "unknown"), inner_data)
        
        # 📸 Print image analysis results to terminal
        nsfw_icon = "🔴" if image_result.get("nsfw") else "🟢"
        violent_icon = "🔴" if image_result.get("violent") else "🟢"
        ocr_preview = image_result.get("ocr_text", "")[:80] or "(none)"
        metadata_keys = list(image_result.get("metadata", {}).keys())
        metadata_preview = f"{len(metadata_keys)} tags found" if metadata_keys else "(none stripped)"
        
        print(f"\n┌──────────────────────────────────────────────┐")
        print(f"│ 📸 IMAGE ANALYSIS RESULTS")
        print(f"│ {nsfw_icon} NSFW:     {image_result.get('nsfw', False)}  (score: {image_result.get('nsfw_score', 0):.4f})")
        print(f"│ {violent_icon} Violence: {image_result.get('violent', False)}  (score: {image_result.get('violent_score', 0):.4f})")
        print(f"│ 📝 OCR:      {ocr_preview}")
        print(f"│ 🗺️  EXIF:     {metadata_preview}")
        if metadata_keys:
            print(f"│   Tags: {', '.join(metadata_keys[:5])}...")
        print(f"└──────────────────────────────────────────────┘\n")
        
        parts = []
        if caption: 
            parts.append(caption)
        if image_result.get("ocr_text"):
            parts.append(f"[Image Text]: {image_result['ocr_text']}")
        if image_result.get("nsfw"):
            parts.append("[IMAGE FLAGGED: NSFW Content Detected]")
        if image_result.get("violent"):
            parts.append("[IMAGE FLAGGED: Violence Detected]")
            
        raw_text = " | ".join(parts) if parts else ""
        
        # Store the image results in a temporary location for the LangGraph state
        request._image_analysis_result = image_result

    elif isinstance(message, str):
        raw_text = message

    if not raw_text or not raw_text.strip():
        logger.debug("Ignoring message: raw_text is empty.")
        return JsonResponse({"status": "ignored", "reason": "no_text_content"})

    # Self-Moderation: Process outgoing messages too (fromMe=True)
    # Instead of ignoring them, we route them through the pipeline with a flag.
    # The Enforcer (Agent 5) uses is_from_me to pick the softer enforcement path:
    #   - Delete for Everyone + educational DM (not punitive warning)
    #   - Constructive parent notification (not alarm)
    is_from_me = key.get("fromMe", False)

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

    # ── 🤖 AEGIS BOT BYPASS & ROUTING ────────────────────────────────────────────
    # Two cases to handle involving the Aegis Assistant bot:
    #
    # CASE A — Child replies TO the bot (fromMe=True, remoteJid = bot's JID):
    #   Instance 1 sees this as an outgoing message. We MUST skip the moderation
    #   pipeline (it would delete the child's reply!). Instead, we forward it
    #   directly to the chatbot handler so the bot can respond.
    #   This also handles misconfigured Instance 2 webhook URLs gracefully.
    #
    # CASE B — Bot messages arrive at Instance 1 as INCOMING (fromMe=False, sender = bot):
    #   When aegis-bot DMs the child, Instance 1 also receives that DM. We must
    #   skip it to prevent the bot being profiled as a threat actor (Groomer Pattern!).
    # ─────────────────────────────────────────────────────────────────────────────

    if is_from_me and sender_jid == AEGIS_BOT_JID:
        # CASE A: Child is replying to the bot — forward to chatbot handler.
        # For fromMe=True: remoteJid = RECIPIENT = bot's JID (not the child's).
        # We need to resolve the child's own JID to reply in the correct thread.
        logger.debug(f"[WEBHOOK] ⏩ child→bot reply detected, forwarding to chatbot handler")
        if os.getenv('AEGIS_BOT_ENABLED', 'False').lower() in ('true', '1', 'yes'):
            try:
                from moderation.services.chatbot_service import get_chatbot
                from moderation.models import MonitoredChild

                # Resolve child JID: look up the monitored child linked to this instance
                child_jid = None
                child_record = MonitoredChild.objects.filter(
                    parent__evolution_instance_name=instance
                ).first()
                if child_record and child_record.whatsapp_jid:
                    child_jid = child_record.whatsapp_jid
                else:
                    # Fallback: ask Evolution API for the instance owner's JID
                    try:
                        from moderation.evolution_api import get_instance_details
                        details = get_instance_details(instance)
                        if details and details.get('ownerJid'):
                            child_jid = details['ownerJid']
                    except Exception:
                        pass

                if child_jid:
                    chatbot = get_chatbot()
                    monitor_instance = os.getenv('EVOLUTION_INSTANCE_NAME', instance)
                    is_safety_event = False
                    threat_intel = None
                    
                    # 1. Save child's message to conversation memory
                    chatbot.save_message(child_jid, 'user', raw_text)
                    
                    # 2. Static keyword safety check (fast fallback)
                    is_critical_keyword, matched_keyword = chatbot.check_safety_escalation(raw_text)
                    if is_critical_keyword:
                        is_safety_event = True
                        logger.warning(f"[WEBHOOK] 🚨 Keyword SAFETY ESCALATION in child→bot chat: '{matched_keyword}'")

                    # 3. Generate LLM response
                    raw_response = chatbot.generate_response(child_jid, raw_text)
                    
                    # 4. Parse THREAT_INTEL tag from response
                    response_text, threat_intel = chatbot.parse_threat_intel(raw_response)
                    
                    if threat_intel:
                        is_safety_event = True
                        logger.warning(f"[WEBHOOK] 🚨 THREAT_INTEL extracted: {threat_intel.get('threat_type')} | urgency={threat_intel.get('urgency')}")
                    
                    # 5. Check legacy tag
                    if "[SAFETY_ESCALATE]" in response_text:
                        response_text = response_text.replace("[SAFETY_ESCALATE]", "").strip()
                        is_safety_event = True
                        logger.warning(f"[WEBHOOK] 🚨 LLM Reasoned SAFETY ESCALATION detected!")
                    
                    # 6. Send parent alert if safety event detected
                    if is_safety_event:
                        if threat_intel:
                            chatbot.notify_parent_safety_detailed(chatbot.bot_instance, child_jid, threat_intel)
                        else:
                            chatbot.notify_parent_safety(chatbot.bot_instance, child_jid, matched_keyword or "LLM Danger Assessment")
                    
                    # 7. Send clean response to child
                    chatbot.send_reply(child_jid, response_text)
                    
                    # 8. Save bot's response to conversation memory
                    chatbot.save_message(
                        child_jid, 'assistant', response_text,
                        is_safety_flagged=is_safety_event,
                        threat_intel=threat_intel,
                    )
                    
                    logger.info(f"[WEBHOOK] 🤖 Chatbot replied to child ({child_jid}): {len(response_text)} chars"
                                + (" 🚨 SAFETY" if is_safety_event else ""))
                else:
                    logger.warning(f"[WEBHOOK] ⚠️ Could not resolve child JID for chatbot reply (instance={instance})")
            except Exception as e:
                logger.error(f"[WEBHOOK] Chatbot forwarding failed: {e}")
        return JsonResponse({"status": "forwarded_to_chatbot", "reason": "child_to_bot_conversation"})

    if not is_from_me and sender_jid == AEGIS_BOT_JID:
        # CASE B: Bot's own DM arriving at Instance 1 — skip entirely
        logger.debug(f"[WEBHOOK] ⏩ Skipping bot's own message at Instance 1")
        return JsonResponse({"status": "ignored", "reason": "bot_own_message"})
        
    # We also explicitly ignore messages if they happen to come from the aegis-bot instance
    # just in case the user did manage to configure the webhook properly for it.
    BOT_INSTANCE_NAME = os.getenv('AEGIS_BOT_INSTANCE_NAME', 'aegis-bot')
    if instance == BOT_INSTANCE_NAME:
        return JsonResponse({"status": "ignored", "reason": "bot_instance_webhook"})
    # ─────────────────────────────────────────────────────────────────────────────

    direction_icon = "📤 OUTGOING (Self-Moderation)" if is_from_me else "📥 INCOMING"
    sender_label = push_name if push_name else (pure_number if not is_from_me else "ME (Host)")
    recipient_label = pure_number if is_from_me else "ME (Host)"
    
    print(f"\n┌──────────────────────────────────────────────┐")
    print(f"│ {direction_icon} MESSAGE")
    print(f"│ 👤 Sender:    {sender_label}")
    print(f"│ 🎯 Recipient: {recipient_label}")
    print(f"│ 📝 Text:      '{raw_text[:80] + ('...' if len(raw_text) > 80 else '')}'")

    # 3. 🧠 SEND TO AI PIPELINE (LangGraph Orchestrator)
    t_ml_start = time.time()

    # Grab the image results we saved earlier (if any)
    image_result = getattr(request, '_image_analysis_result', {})
    
    # Resolve monitoring mode for this instance
    monitoring_mode = 'child'  # default
    try:
        from moderation.models import ParentProfile
        parent_profile = ParentProfile.objects.filter(
            evolution_instance_name=instance
        ).first()
        if parent_profile:
            monitoring_mode = getattr(parent_profile, 'monitoring_mode', 'child')
    except Exception:
        pass

    # Prepare the initial state
    initial_state = {
        "monitoring_mode": monitoring_mode,
        "raw_text": raw_text,
        "sender_jid": sender_lid_jid,        # ← mapped to true LID
        "sender_phone_jid": sender_phone_jid,
        "instance_name": instance,
        "message_key_id": message_key_id,
        "push_name": push_name,
        "is_from_me": is_from_me,
        "start_time_ms": int(t_ml_start * 1000),

        # IMAGE ANALYSIS DATA
        "image_analyzed": bool(image_result),
        "image_nsfw": image_result.get("nsfw", False),
        "image_violent": image_result.get("violent", False),
        "image_nsfw_score": image_result.get("nsfw_score", 0.0),
        "image_violent_score": image_result.get("violent_score", 0.0),
        "image_ocr_text": image_result.get("ocr_text", ""),
        "image_metadata": image_result.get("metadata", {})
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
