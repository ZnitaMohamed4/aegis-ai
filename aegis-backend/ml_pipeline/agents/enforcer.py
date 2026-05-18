"""
AGENT 5: The Enforcer — executes final enforcement actions.

Responsibilities:
  1. Persist the ModerationResult + SecurityAlert to PostgreSQL
  2. Create Conversation + Message records for the admin dashboard
  3. Broadcast real-time events via Django Channels (WebSocket)
  4. Execute WhatsApp enforcement actions:
     - DELETE harmful messages (BLOCK/ESCALATE)
     - REACT with 🚨 emoji on flagged messages
     - SEND warning auto-reply to the sender
     - NOTIFY parent on critical escalations

This node was previously inline in views.py, then moved to graph.py.
Split into its own module during Phase 2 audit refactoring (2026-04-21).

NOTE: time.sleep(5.0) was removed during Phase 2 — it was blocking
the entire request thread. When archive is re-enabled, use
threading.Timer or a Celery task instead.
"""
import hashlib
import logging
import time

from .state import ModerationState

logger = logging.getLogger(__name__)

# ANSI colors for Agent 5 logging
C5_PURPLE = "\033[95m"
C5_GREEN  = "\033[92m"
C5_RED    = "\033[91m"


def enforcer_node(state: ModerationState) -> dict:
    """
    AGENT 5: The Enforcer
    Executes the final enforcement action based on the pipeline's decision.
    """
    # Lazy imports to avoid circular dependencies at module load time
    from moderation.evolution_api import (
        delete_message_from_whatsapp, send_aegis_warning,
        send_aegis_reaction, send_aegis_presence, send_parent_alert,
        send_educational_dm, send_constructive_parent_alert,
    )
    from moderation.models import (
        ModerationResult, SecurityAlert, HarassmentCategory,
        Conversation, Message, MonitoredChild, SelfModerationEvent
    )
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    # Extract state
    decision = state.get("decision", "ALLOW")
    raw_text = state.get("raw_text", "")
    sender_jid = state.get("sender_jid", "")
    instance_name = state.get("instance_name", "")
    message_key_id = state.get("message_key_id")
    push_name = state.get("push_name")
    is_from_me = state.get("is_from_me", False)
    m1_score = state.get("m1_score", 0.0)
    primary_class = state.get("primary_class", "safe")
    m2_confidence = state.get("m2_confidence")
    llm_triggered = state.get("llm_triggered", False)
    llm_explanation = state.get("llm_explanation", "")
    ml_corrected = state.get("ml_corrected", False)
    ml_original_decision = state.get("ml_original_decision")
    ml_original_class = state.get("ml_original_class")

    enforcement_actions = []
    alert_severity = None

    # ── SELF-MODERATION: Detect child's own toxic messages ────────
    # If is_from_me=True AND the pipeline flagged it, this is a self-moderation event.
    # We convert the decision to EDUCATE and use a softer enforcement path.
    is_self_moderation = is_from_me and decision != 'ALLOW'
    original_pipeline_decision = decision  # Preserve for SelfModerationEvent
    
    if is_self_moderation:
        decision = 'EDUCATE'  # Override to educational decision

    # ── 1. Save ModerationResult to PostgreSQL ───────────────────
    is_human_review = decision == 'HUMAN_REVIEW'

    # Link to HarassmentCategory reference table
    harassment_category = None
    try:
        harassment_category = HarassmentCategory.objects.get(code=primary_class)
    except HarassmentCategory.DoesNotExist:
        pass  # Unknown category — leave FK null

    moderation = ModerationResult.objects.create(
        instance_name=instance_name,
        sender_jid=sender_jid,
        sender_name=push_name,
        is_from_me=is_from_me,
        is_self_moderation=is_self_moderation,
        raw_text=raw_text,
        normalized_text=state.get("normalized_text", ""),
        message_key_id=message_key_id,
        primary_class=primary_class,
        category=harassment_category,
        toxicity_score=m1_score,
        confidence_score=m2_confidence,
        final_score=m1_score,
        decision=decision,
        llm_triggered=llm_triggered,
        llm_explanation=llm_explanation,
        flagged_for_review=is_human_review,
        behavioral_risk_score=state.get("risk_score", 0.0),

        # IMAGE DATA
        has_image=state.get("image_analyzed", False),
        image_nsfw_detected=state.get("image_nsfw", False),
        image_violence_detected=state.get("image_violent", False),
        image_nsfw_score=state.get("image_nsfw_score", 0.0),
        image_violence_score=state.get("image_violent_score", 0.0),
        image_ocr_text=state.get("image_ocr_text", ""),
        
        # 🔁 Retraining fields: preserve what the ML said before Agent 3 corrected it
        ml_corrected=ml_corrected,
        ml_original_decision=ml_original_decision,
        ml_original_class=ml_original_class,
        processing_time_ms=int(time.time() * 1000) - state.get("start_time_ms", int(time.time() * 1000)),
    )
    enforcement_actions.append("persist")

    # ── 2. Create Conversation + Message records ─────────────────
    child = None
    try:
        child = MonitoredChild.objects.filter(
            parent__evolution_instance_name=instance_name,
        ).first()
    except Exception:
        pass

    conversation = None
    try:
        conversation, _ = Conversation.objects.get_or_create(
            contact_jid=sender_jid,
            child=child,
            defaults={
                'contact_name': push_name or '',
                'platform': 'whatsapp',
            }
        )
        if push_name and push_name != conversation.contact_name:
            conversation.contact_name = push_name
            conversation.save(update_fields=['contact_name', 'updated_at'])
    except Exception as e:
        logger.warning(f"[AGENT 5: ENFORCER] Could not create Conversation: {e}")

    try:
        Message.objects.create(
            conversation=conversation,
            content=raw_text,
            content_hash=hashlib.sha256(raw_text.encode('utf-8')).hexdigest(),
            language=state.get('detected_language', 'unknown') or 'unknown',
            is_blocked=decision in ('BLOCK', 'ESCALATE'),
            is_displayed=decision not in ('BLOCK', 'ESCALATE'),
            platform='whatsapp',
            platform_message_id=message_key_id or '',
            sender_jid=sender_jid,
            moderation_result=moderation,
        )
    except Exception as e:
        logger.warning(f"[AGENT 5: ENFORCER] Could not create Message: {e}")

    # ── 3. Broadcast via WebSocket ───────────────────────────────
    def _broadcast(mod, alerte=None):
        """Push real-time event to Angular Dashboard via Django Channels."""
        channel_layer = get_channel_layer()
        payload = {
            "id": str(alerte.id) if alerte else str(mod.id),
            "type": "alert" if alerte else "log",
            "sender": mod.sender_jid,
            "text": mod.raw_text,
            "decision": mod.decision.lower(),
            "primary_class": mod.primary_class or 'safe',
            "language": getattr(mod, 'language', 'unknown'),
            "m1_score": round(mod.toxicity_score, 4),
            "m2_confidence": round(mod.confidence_score, 4) if mod.confidence_score else None,
            "llm_triggered": mod.llm_triggered,
            "llm_explanation": mod.llm_explanation,
            "severity": alerte.severity if alerte else "none",
            "timestamp": (alerte.sent_at if alerte else mod.created_at).isoformat(),
        }
        try:
            # 1. Global Admin Broadcast
            async_to_sync(channel_layer.group_send)(
                "alerts",
                {"type": "alert.message", "data": payload}
            )
            # 2. Instance-Scoped Parent Broadcast
            if mod.instance_name:
                async_to_sync(channel_layer.group_send)(
                    f"alerts_{mod.instance_name}",
                    {"type": "alert.message", "data": payload}
                )
        except Exception as e:
            logger.warning(f"[AGENT 5: ENFORCER] WS broadcast failed: {e}")

    # ── 4. Enforce Decision ──────────────────────────────────────
    
    # ── 4a. SELF-MODERATION PATH (Child's own toxic message) ─────
    if is_self_moderation:
        from moderation.services.formatters import SEVERITY_MAP
        alert_severity = SEVERITY_MAP.get(decision, 'low')
        
        alerte = SecurityAlert.objects.create(
            moderation_result=moderation,
            severity=alert_severity,
            message_preview=raw_text[:200]
        )
        enforcement_actions.append("alert")
        _broadcast(moderation, alerte)
        enforcement_actions.append("broadcast")
        
        # Step 1: Delete the toxic message for everyone (via Instance 1)
        # We always delete if it was flagged, regardless of whether the Auditor downgraded it to WARN.
        message_deleted = False
        if message_key_id:
            phone_jid = state.get("sender_phone_jid") or sender_jid
            delete_result = delete_message_from_whatsapp(instance_name, message_key_id, phone_jid, True)
            message_deleted = bool(delete_result)
            if message_deleted:
                enforcement_actions.append("delete_for_everyone")
        
        # Step 2: Send educational DM via Aegis Assistant bot (Instance 2)
        import os as _os
        bot_instance = _os.getenv('AEGIS_BOT_INSTANCE_NAME', '')
        
        # When is_from_me=True, sender_jid is the recipient (the harasser).
        # We need to send the DM to the child themselves.
        child_jid_for_dm = child.whatsapp_jid if child else None
        
        dm_sent = False
        dm_text = ''
        if bot_instance and child_jid_for_dm:
            dm_key_id, dm_text = send_educational_dm(bot_instance, child_jid_for_dm, primary_class, raw_text)
            dm_sent = dm_key_id is not None
            if dm_sent:
                enforcement_actions.append("educational_dm")
        else:
            logger.warning("[AGENT 5: ENFORCER] ⚠️ Cannot send DM. Bot instance or child JID missing.")
        
        # Step 3: (Removed) Parent WhatsApp Alert
        # As requested, we no longer send a WhatsApp ping to the parent for self-moderation.
        # This will strictly be visible on the Dashboard.
        parent_notified = False
        
        # Step 4: Record the SelfModerationEvent
        try:
            SelfModerationEvent.objects.create(
                moderation_result=moderation,
                category=primary_class,
                original_decision=original_pipeline_decision,
                message_deleted=message_deleted,
                educational_dm_sent=dm_sent,
                educational_dm_text=dm_text,
                parent_notified=parent_notified,
            )
            enforcement_actions.append("self_mod_event")
        except Exception as e:
            logger.error(f"[AGENT 5: ENFORCER] Failed to create SelfModerationEvent: {e}")
        
        print(f"\n  📚 [SELF-MODERATION] Child message caught!")
        print(f"     Category: {primary_class} | Original: {original_pipeline_decision} → EDUCATE")
        print(f"     Deleted: {'✅' if message_deleted else '❌'} | DM Sent: {'✅' if dm_sent else '❌'} | Parent: {'✅' if parent_notified else '❌'}")
    
    # ── 4b. STANDARD PATH (Incoming harmful messages) ────────────
    elif decision != 'ALLOW':
        from moderation.services.formatters import SEVERITY_MAP
        alert_severity = SEVERITY_MAP.get(decision, 'medium')

        alerte = SecurityAlert.objects.create(
            moderation_result=moderation,
            severity=alert_severity,
            message_preview=raw_text[:200]
        )
        enforcement_actions.append("alert")

        _broadcast(moderation, alerte)
        enforcement_actions.append("broadcast")

        # ACTIVE SHIELD: Delete harmful messages from WhatsApp
        if decision in ['BLOCK', 'ESCALATE'] and is_from_me:
            if message_key_id:
                delete_message_from_whatsapp(instance_name, message_key_id, sender_jid, True)
                enforcement_actions.append("delete")

        # AUTO-REPLY: Tag + warn (not for HUMAN_REVIEW — wait for admin)
        if decision in ['BLOCK', 'ESCALATE', 'WARN', 'REVISE']:
            if message_key_id:
                react_emoji_map = {'ESCALATE': '🚨', 'BLOCK': '🛑', 'WARN': '⚠️', 'REVISE': '👀'}
                chosen_emoji = react_emoji_map.get(decision, '⚠️')
                send_aegis_reaction(instance_name, sender_jid, message_key_id, is_from_me, chosen_emoji)
                enforcement_actions.append("react")

            # [FIX] Resolve phone JID BEFORE sending the warning, so the warning's
            # remoteJid in Prisma matches the JID we'll use in the archive payload.
            phone_jid = state.get("sender_phone_jid") or sender_jid
            
            # Build image flags for context-specific warning messages
            image_flags = None
            if state.get("image_analyzed"):
                image_flags = {
                    "nsfw": state.get("image_nsfw", False),
                    "violent": state.get("image_violent", False),
                    "ocr_text": state.get("image_ocr_text", ""),
                }
            
            send_aegis_presence(instance_name, phone_jid, "composing", 1500)
            warning_result = send_aegis_warning(instance_name, phone_jid, primary_class, is_from_me, decision, message_key_id, image_flags=image_flags)
            enforcement_actions.append("warn")
            
            # Extract exact warning message key ID, timestamp, and full node for archive anchor
            warning_msg_key_id = None
            exact_warning_ts = None
            full_warning_message = None
            
            if isinstance(warning_result, tuple) and len(warning_result) == 3:
                warning_msg_key_id, exact_warning_ts, full_warning_message = warning_result
                logger.info(f"[AGENT 5: ENFORCER] 📌 Captured exact warning anchor (full node): id={warning_msg_key_id}, ts={exact_warning_ts}")
                
                # ── EXTRACT LID FROM WARNING RESPONSE ───────────────────────
                # The sendText response contextInfo contains the real @lid identity
                # This is the ONLY place Evolution API exposes it reliably
                warning_context = full_warning_message.get("contextInfo", {}) or {}
                lid_from_warning = (
                    warning_context.get("participant", "") or
                    warning_context.get("remoteJid", "")
                )
                if lid_from_warning and "@lid" in lid_from_warning:
                    # Override sender_jid in state with the real LID
                    state["sender_jid"] = lid_from_warning
                    logger.info(f"[AGENT 5: ENFORCER] ✅ LID extracted from warning contextInfo: {lid_from_warning}")
                # ────────────────────────────────────────────────────────────
                
            elif isinstance(warning_result, tuple) and len(warning_result) == 2:
                warning_msg_key_id, exact_warning_ts = warning_result
                logger.info(f"[AGENT 5: ENFORCER] 📌 Captured exact warning anchor (stripped node): id={warning_msg_key_id}, ts={exact_warning_ts}")
            elif isinstance(warning_result, str) and len(warning_result) > 5:
                # Fallback for old return type
                warning_msg_key_id = warning_result

            # PARENT ALERT: Notify parent on critical escalations
            if decision == 'ESCALATE' and child and child.parent and child.parent.user.phone_number:
                send_parent_alert(instance_name, child.parent.user.phone_number, child.full_name, primary_class, raw_text)
                enforcement_actions.append("parent_alert")
                
            # 🛡️ INCOMING ATTACKER NEUTRALIZATION (Archive + Block)
            if decision in ['BLOCK', 'ESCALATE'] and not is_from_me:
                lid_jid = state.get("sender_jid")
                
                logger.info(
                    f"[AGENT 5: ENFORCER] 🗃️ Archive target: "
                    f"lid={lid_jid} | phone={phone_jid} | "
                    f"has_full_msg={full_warning_message is not None}"
                )
                
                # 📦 Archive + Block are disabled due to Baileys protocol instability.
                # See docs/DISABLED_FEATURES.md for the original code.
                # NOTE: time.sleep(5.0) was removed during Phase 2 refactoring.
                # When archive is re-enabled, use threading.Timer or Celery instead.
                logger.info(
                    f"[AGENT 5: ENFORCER] ⚠️ Archive/Block disabled for {phone_jid} "
                    f"(decision={decision}). See DISABLED_FEATURES.md."
                )
    else:
        # Safe message — still broadcast for the Activity Feed
        _broadcast(moderation)
        enforcement_actions.append("broadcast")

    # ── 5. Terminal Logging ──────────────────────────────────────
    action_icon = "🟢" if decision == "ALLOW" else "🔴"
    logger.info(
        f"[AGENT 5: ENFORCER] {action_icon} decision={decision} | "
        f"actions={enforcement_actions} | moderation_id={moderation.id}"
    )

    return {
        "moderation_id": str(moderation.id),
        "alert_severity": alert_severity,
        "enforcement_actions": enforcement_actions,
    }
