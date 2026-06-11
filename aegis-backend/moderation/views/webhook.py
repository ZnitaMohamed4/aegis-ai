"""
Webhook endpoint — Evolution API posts WhatsApp messages here.

Extracted from views.py during Phase 2 audit refactoring (2026-04-21).
"""
import hmac
import json
import logging
import os
import time
import traceback

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
from moderation.models import FailedMessage, ModerationResult
from ml_pipeline.models_pkg.language_detector import detect_language, is_likely_darija

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


def _has_arabic_script(text: str) -> bool:
    """Check if text contains Arabic-script characters."""
    return any('\u0600' <= c <= '\u06FF' for c in text)


@csrf_exempt
@require_http_methods(["POST"])
def webhook_messages(request):
    """
    ENDPOINT: POST /api/v1/webhook/messages/
    This is what Evolution API hits when a WhatsApp message arrives!
    """
    t_start = time.time()

    # 🔒 WEBHOOK AUTHENTICATION — verify the request came from Evolution API
    # The ngrok tunnel is public, so anyone who knows/guesses the URL can POST.
    # Evolution API sends its apikey header with every webhook — we validate it here.
    expected_key = os.getenv('EVOLUTION_API_KEY', '')
    incoming_key = request.headers.get('apikey', '')
    if not expected_key or not hmac.compare_digest(incoming_key, expected_key):
        logger.warning(
            "Unauthorized webhook attempt from %s (apikey=%s…)",
            request.META.get('REMOTE_ADDR', 'unknown'),
            incoming_key[:8] if incoming_key else '<missing>',
        )
        return JsonResponse({"status": "unauthorized"}, status=401)

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
    is_voice_message = False
    audio_message_data = None  # Set when audioMessage detected — Agent 0 will transcribe

    # 1. Plain text
    if "conversation" in message:
        raw_text = message["conversation"]
    # 2. Extended text (links, quotes, etc)
    elif "extendedTextMessage" in message:
        raw_text = message["extendedTextMessage"].get("text", "")
    # 3. Audio Message — Agent 0 (Transcription Agent) will handle inside the graph
    elif "audioMessage" in message:
        logger.info("Audio message detected. Agent 0 will transcribe inside the pipeline.")
        is_voice_message = True
        audio_message_data = inner_data
        raw_text = ""  # Will be set by Agent 0
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
        
        # Log image analysis results
        ocr_preview = image_result.get("ocr_text", "")[:80] or "(none)"
        metadata_keys = list(image_result.get("metadata", {}).keys())
        metadata_preview = f"{len(metadata_keys)} tags found" if metadata_keys else "(none stripped)"
        
        logger.info(
            f"[WEBHOOK: IMAGE] NSFW={image_result.get('nsfw', False)} "
            f"(score={image_result.get('nsfw_score', 0):.4f}) | "
            f"Violence={image_result.get('violent', False)} "
            f"(score={image_result.get('violent_score', 0):.4f}) | "
            f"OCR={ocr_preview} | EXIF={metadata_preview}"
        )
        
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

    # Allow audio messages through even with empty raw_text (Agent 0 will transcribe)
    if (not raw_text or not raw_text.strip()) and not audio_message_data:
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

    # 🚫 APPLICATION-LEVEL BLOCKLIST CHECK
    # If this sender has been blocked by the Enforcer, silently drop their message.
    # No pipeline, no response, no warning — they're shouting into the void.
    # Only applies to incoming messages (outgoing self-moderation must always run).
    if not is_from_me:
        from moderation.models import BlockedContact
        if BlockedContact.objects.filter(
            sender_jid__in=[sender_jid, sender_phone_jid],
            is_active=True,
        ).exists():
            logger.info(
                "[WEBHOOK] 🚫 BLOCKED sender %s — message silently dropped.",
                sender_phone_jid,
            )
            return JsonResponse({"status": "blocked", "reason": "sender_blocked"})

    direction = "OUTGOING (Self-Moderation)" if is_from_me else "INCOMING"
    voice_tag = " 🎤 VOICE" if is_voice_message else ""
    sender_label = push_name if push_name else (pure_number if not is_from_me else "ME (Host)")
    recipient_label = pure_number if is_from_me else "ME (Host)"
    
    logger.info(
        f"[WEBHOOK] {direction} message{voice_tag} | "
        f"Sender={sender_label} | Recipient={recipient_label} | "
        f"Text='{'(audio — Agent 0 will transcribe)' if audio_message_data else raw_text[:80] + ('...' if len(raw_text) > 80 else '')}'"
    )
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

    # 🔤 LANGUAGE DETECTION (fasttext, <1ms)
    detected_lang = detect_language(raw_text)
    if is_likely_darija(raw_text, detected_lang):
        detected_lang = "darija"

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
        "detected_language": detected_lang,
        "is_voice_message": is_voice_message,

        # AUDIO DATA (for Agent 0 Transcription)
        "audio_message_data": audio_message_data,

        # IMAGE ANALYSIS DATA
        "image_analyzed": bool(image_result),
        "image_nsfw": image_result.get("nsfw", False),
        "image_violent": image_result.get("violent", False),
        "image_nsfw_score": image_result.get("nsfw_score", 0.0),
        "image_violent_score": image_result.get("violent_score", 0.0),
        "image_ocr_text": image_result.get("ocr_text", ""),
        "image_metadata": image_result.get("metadata", {})
    }
    
    # 🔒 DEDUPLICATION — reject duplicate webhooks from Evolution API retries
    if message_key_id and ModerationResult.objects.filter(message_key_id=message_key_id).exists():
        logger.info("Duplicate message_key_id=%s from %s — skipping", message_key_id, sender_lid_jid)
        return JsonResponse({"status": "duplicate", "message_key_id": message_key_id})

    # 🚀 EXECUTE THE GRAPH — wrapped in crash net
    try:
        final_state = aegis_graph.invoke(initial_state)
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error(
            "Pipeline crashed for message from %s on instance %s: %s\n%s",
            sender_lid_jid, instance, exc, tb,
        )
        # Persist the failed message so it is never silently lost
        try:
            FailedMessage.objects.create(
                raw_text=raw_text,
                sender_jid=sender_lid_jid,
                instance_name=instance,
                message_key_id=message_key_id,
                push_name=push_name,
                error_type=type(exc).__name__,
                error_message=tb,
                pipeline_stage="graph_invoke",
                metadata={
                    "image_analyzed": bool(image_result),
                    "is_from_me": is_from_me,
                },
            )
        except Exception:
            # Last-resort: if even the DB write fails, log it so at least
            # the error appears in server logs.
            logger.critical("FailedMessage persistence also failed: %s",
                            traceback.format_exc())

        # Return 200 so Evolution API does NOT blindly retry the webhook
        return JsonResponse({
            "status": "error",
            "error": "Pipeline processing failed — message persisted for review",
        }, status=200)

    t_ml_end = time.time()

    # Extract the final results from the graph's memory!
    decision = final_state.get("decision", "ALLOW")
    m1_score = final_state.get("m1_score", 0.0)
    primary_class = final_state.get("primary_class", "safe")
    m2_confidence = final_state.get("m2_confidence")
    llm_triggered = final_state.get("llm_triggered", False)
    llm_explanation = final_state.get("llm_explanation", "")
    ml_corrected = final_state.get("ml_corrected", False)

    # Log the Multi-Agent Execution Results
    logger.info(f"[ORCHESTRATOR] Graph Execution Complete in {int((t_ml_end - t_ml_start) * 1000)}ms")

    # Agent 0: Transcription (only for voice messages)
    a0_latency = final_state.get("agent_0_latency_ms", 0)
    if a0_latency > 0:
        logger.info(f"[AGENT 0: TRANSCRIBER] Transcription latency: {a0_latency}ms")

    logger.info(f"[AGENT 1: GATEKEEPER] Toxicity Score: {m1_score:.2f}")
    
    if m2_confidence is not None:
        logger.info(f"[AGENT 2: CLASSIFIER] Primary Threat: {primary_class.upper()} (Confidence: {m2_confidence:.2f})")
        
    # Escalation Gate
    escalation_risk = final_state.get("escalation_risk", 0.0)
    escalation_reason = final_state.get("escalation_reason", "")
    if escalation_risk >= 0.40:
        logger.info(f"[ESCALATION GATE] Score: {escalation_risk:.2f} — {escalation_reason}")

    if final_state.get("shadow_reviewed", False):
        logger.info(f"[AGENT 3: AUDITOR] Triggered by Shadow Zone! Verified as {decision}")
    elif llm_triggered:
        correction_tag = " CORRECTED ML" if ml_corrected else ""
        logger.info(f"[AGENT 3: AUDITOR] Triggered! Groq Decision: {decision} - \"{llm_explanation}\"{correction_tag}")
        
    logger.info(f"[AGENT 4: PROFILER] Target Risk Score: {final_state.get('risk_score', 0.0):.2f} ({final_state.get('risk_level', 'LOW')})")
    
    # Agent 5 now runs INSIDE the graph — enforcement is complete by this point
    actions = final_state.get("enforcement_actions", [])
    alert_sev = final_state.get("alert_severity", "none") or "none"
    logger.info(f"[AGENT 5: ENFORCER] Action: {decision} | Severity: {alert_sev} | Actions: {actions}")

    t_end = time.time()
    t_orch = int((t_end - t_start) * 1000)
    
    # Extract agent latencies from state or fallback to defaults/orchestrator time
    a0_lat = final_state.get("agent_0_latency_ms", 0)
    a1_2_lat = final_state.get("agent_1_2_latency_ms", int((t_ml_end - t_ml_start) * 1000))
    a3_lat = final_state.get("agent_3_latency_ms", 0)
    a4_lat = final_state.get("agent_4_latency_ms", 0)
    a5_lat = final_state.get("agent_5_latency_ms", max(1, t_orch - a0_lat - a1_2_lat - a3_lat - a4_lat))

    if a0_lat > 0:
        log_latency('agent_0', a0_lat)
    log_latency('agent_1', a1_2_lat // 2)
    log_latency('agent_2', a1_2_lat // 2)
    if final_state.get("llm_triggered") or final_state.get("shadow_reviewed"):
        log_latency('agent_3', a3_lat)
    log_latency('agent_4', a4_lat)
    log_latency('agent_5', a5_lat)

    # 7. Return 200 OK so Evolution API knows we received it
    return JsonResponse({
        "status": "success",
        "decision": decision,
        "m1_score": round(m1_score, 4),
    })
