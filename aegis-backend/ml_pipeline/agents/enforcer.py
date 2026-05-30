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
Decomposed into Strategy functions during Phase 3 refactoring (2026-05-20).

NOTE: time.sleep(5.0) was removed during Phase 2 — it was blocking
the entire request thread. When archive is re-enabled, use
threading.Timer or a Celery task instead.
"""
import hashlib
import logging
import os
import time

from .state import ModerationState

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# ENFORCEMENT CONTEXT — shared state passed to each strategy function
# ══════════════════════════════════════════════════════════════════════════════

class _EnforcementContext:
    """Lightweight container for data shared across enforcement strategies.

    Avoids passing 20+ arguments to each private function.
    """
    __slots__ = (
        'state', 'decision', 'original_decision', 'raw_text', 'sender_jid',
        'instance_name', 'message_key_id', 'push_name', 'is_from_me',
        'm1_score', 'primary_class', 'm2_confidence', 'llm_triggered',
        'llm_explanation', 'ml_corrected', 'ml_original_decision',
        'ml_original_class', 'monitoring_mode', 'is_adult_mode',
        'is_self_moderation', 'moderation', 'child', 'conversation',
        'enforcement_actions', 'alert_severity', 'broadcast_fn',
    )

    def __init__(self, state):
        self.state = state
        self.raw_text = state.get("raw_text", "")
        self.sender_jid = state.get("sender_jid", "")
        self.instance_name = state.get("instance_name", "")
        self.message_key_id = state.get("message_key_id")
        self.push_name = state.get("push_name")
        self.is_from_me = state.get("is_from_me", False)
        self.m1_score = state.get("m1_score", 0.0)
        self.primary_class = state.get("primary_class", "safe")
        self.m2_confidence = state.get("m2_confidence")
        self.llm_triggered = state.get("llm_triggered", False)
        self.llm_explanation = state.get("llm_explanation", "")
        self.ml_corrected = state.get("ml_corrected", False)
        self.ml_original_decision = state.get("ml_original_decision")
        self.ml_original_class = state.get("ml_original_class")
        self.monitoring_mode = state.get("monitoring_mode", "child")
        self.is_adult_mode = self.monitoring_mode == 'adult'

        # Determined by enforcer_node before dispatching
        self.decision = None
        self.original_decision = None
        self.is_self_moderation = False

        # Populated during persistence phase
        self.moderation = None
        self.child = None
        self.conversation = None
        self.enforcement_actions = []
        self.alert_severity = None
        self.broadcast_fn = None


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def enforcer_node(state: ModerationState) -> dict:
    """AGENT 5: The Enforcer — routes to the appropriate enforcement strategy."""
    import time as _time
    _t_start = _time.time()

    # Lazy imports to avoid circular dependencies at module load time
    from moderation.models import (
        ModerationResult, SecurityAlert, HarassmentCategory,
        Conversation, Message, MonitoredChild, SelfModerationEvent,
    )
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    ctx = _EnforcementContext(state)

    # ── Resolve Decision (context-aware) ─────────────────────────────
    decision = state.get("decision", "ALLOW")
    ctx.original_decision = decision

    if ctx.is_adult_mode and decision != 'ALLOW':
        decision = 'SELF_WARN'
    elif not ctx.is_adult_mode and ctx.is_from_me and decision != 'ALLOW':
        ctx.is_self_moderation = True
        decision = 'EDUCATE'

    ctx.decision = decision

    # ── 1. Persist ModerationResult ──────────────────────────────────
    harassment_category = None
    try:
        harassment_category = HarassmentCategory.objects.get(
            code=ctx.primary_class,
        )
    except HarassmentCategory.DoesNotExist:
        pass

    ctx.moderation = ModerationResult.objects.create(
        instance_name=ctx.instance_name,
        sender_jid=ctx.sender_jid,
        sender_name=ctx.push_name,
        is_from_me=ctx.is_from_me,
        is_self_moderation=ctx.is_self_moderation,
        raw_text=ctx.raw_text,
        normalized_text=state.get("normalized_text", ""),
        message_key_id=ctx.message_key_id,
        primary_class=ctx.primary_class,
        category=harassment_category,
        toxicity_score=ctx.m1_score,
        confidence_score=ctx.m2_confidence,
        final_score=ctx.m1_score,
        decision=decision,
        llm_triggered=ctx.llm_triggered,
        llm_explanation=ctx.llm_explanation,
        flagged_for_review=(decision == 'HUMAN_REVIEW'),
        behavioral_risk_score=state.get("risk_score", 0.0),
        # Image data
        has_image=state.get("image_analyzed", False),
        image_nsfw_detected=state.get("image_nsfw", False),
        image_violence_detected=state.get("image_violent", False),
        image_nsfw_score=state.get("image_nsfw_score", 0.0),
        image_violence_score=state.get("image_violent_score", 0.0),
        image_ocr_text=state.get("image_ocr_text", ""),
        image_metadata=state.get("image_metadata", {}),
        # Retraining fields
        ml_corrected=ctx.ml_corrected,
        ml_original_decision=ctx.ml_original_decision,
        ml_original_class=ctx.ml_original_class,
        processing_time_ms=(
            int(time.time() * 1000)
            - state.get("start_time_ms", int(time.time() * 1000))
        ),
    )
    ctx.enforcement_actions.append("persist")

    # ── 2. Create Conversation + Message records ─────────────────────
    try:
        ctx.child = MonitoredChild.objects.filter(
            parent__evolution_instance_name=ctx.instance_name,
        ).first()
    except Exception:
        pass

    try:
        ctx.conversation, _ = Conversation.objects.get_or_create(
            contact_jid=ctx.sender_jid,
            child=ctx.child,
            defaults={
                'contact_name': ctx.push_name or '',
                'platform': 'whatsapp',
            },
        )
        if ctx.push_name and ctx.push_name != ctx.conversation.contact_name:
            ctx.conversation.contact_name = ctx.push_name
            ctx.conversation.save(
                update_fields=['contact_name', 'updated_at'],
            )
    except Exception as e:
        logger.warning(f"[AGENT 5: ENFORCER] Could not create Conversation: {e}")

    try:
        Message.objects.create(
            conversation=ctx.conversation,
            content=ctx.raw_text,
            content_hash=hashlib.sha256(
                ctx.raw_text.encode('utf-8'),
            ).hexdigest(),
            language=state.get('detected_language', 'unknown') or 'unknown',
            is_blocked=decision in ('BLOCK', 'ESCALATE'),
            is_displayed=decision not in ('BLOCK', 'ESCALATE'),
            platform='whatsapp',
            platform_message_id=ctx.message_key_id or '',
            sender_jid=ctx.sender_jid,
            moderation_result=ctx.moderation,
        )
    except Exception as e:
        logger.warning(f"[AGENT 5: ENFORCER] Could not create Message: {e}")

    # ── 3. Prepare broadcast helper ──────────────────────────────────
    channel_layer = get_channel_layer()

    def _broadcast(mod, alerte=None):
        """Push real-time event to Angular Dashboard via Django Channels."""
        payload = {
            "id": str(alerte.id) if alerte else str(mod.id),
            "type": "alert" if alerte else "log",
            "sender": mod.sender_jid,
            "text": mod.raw_text,
            "decision": mod.decision.lower(),
            "primary_class": mod.primary_class or 'safe',
            "language": getattr(mod, 'language', 'unknown'),
            "m1_score": round(mod.toxicity_score, 4),
            "m2_confidence": (
                round(mod.confidence_score, 4) if mod.confidence_score else None
            ),
            "llm_triggered": mod.llm_triggered,
            "llm_explanation": mod.llm_explanation,
            "severity": alerte.severity if alerte else "none",
            "timestamp": (
                alerte.sent_at if alerte else mod.created_at
            ).isoformat(),
        }
        try:
            async_to_sync(channel_layer.group_send)(
                "alerts",
                {"type": "alert.message", "data": payload},
            )
            if mod.instance_name:
                async_to_sync(channel_layer.group_send)(
                    f"alerts_{mod.instance_name}",
                    {"type": "alert.message", "data": payload},
                )
        except Exception as e:
            logger.warning(f"[AGENT 5: ENFORCER] WS broadcast failed: {e}")

    ctx.broadcast_fn = _broadcast

    # ── 4. Dispatch to enforcement strategy ──────────────────────────
    if ctx.is_adult_mode and decision == 'SELF_WARN':
        _enforce_adult_self_moderation(ctx)
    elif ctx.is_self_moderation:
        _enforce_child_self_moderation(ctx)
    elif decision != 'ALLOW':
        _enforce_standard(ctx)
    else:
        _enforce_safe(ctx)

    # ── 5. Terminal Logging ───────────────────────────────────────────
    icon = "🟢" if decision == "ALLOW" else "🔴"
    logger.info(
        f"[AGENT 5: ENFORCER] {icon} decision={decision} | "
        f"actions={ctx.enforcement_actions} | "
        f"moderation_id={ctx.moderation.id}"
    )

    _t_elapsed = int((_time.time() - _t_start) * 1000)

    return {
        "moderation_id": str(ctx.moderation.id),
        "alert_severity": ctx.alert_severity,
        "enforcement_actions": ctx.enforcement_actions,
        "agent_5_latency_ms": _t_elapsed,
    }


# ══════════════════════════════════════════════════════════════════════════════
# STRATEGY FUNCTIONS — one per enforcement path
# ══════════════════════════════════════════════════════════════════════════════

def _enforce_adult_self_moderation(ctx):
    """Adult mode: gentle reaction + self-reflection DM. No deletion."""
    from moderation.models import SecurityAlert
    from moderation.services.formatters import SEVERITY_MAP
    from moderation.evolution_api import (
        send_aegis_reaction, send_text_message,
    )
    from moderation.services.message_templates import get_adult_reflection_text

    severity = (
        'low' if ctx.original_decision in ('WARN', 'REVISE') else 'medium'
    )
    ctx.alert_severity = severity

    alerte = SecurityAlert.objects.create(
        moderation_result=ctx.moderation,
        severity=severity,
        message_preview=ctx.raw_text[:200],
    )
    ctx.enforcement_actions.append("alert")
    ctx.broadcast_fn(ctx.moderation, alerte)
    ctx.enforcement_actions.append("broadcast")

    # Only react + DM if the adult is sending the message (impulse control)
    if ctx.is_from_me:
        if ctx.message_key_id:
            send_aegis_reaction(
                ctx.instance_name, ctx.sender_jid,
                ctx.message_key_id, ctx.is_from_me, '💭',
            )
            ctx.enforcement_actions.append("react_gentle")

        bot_instance = os.getenv('AEGIS_BOT_INSTANCE_NAME', '')
        adult_jid = ctx.child.whatsapp_jid if ctx.child else None

        if bot_instance and adult_jid:
            reflection = get_adult_reflection_text(
                ctx.primary_class, ctx.original_decision,
                ctx.m1_score, ctx.raw_text,
            )
            send_text_message(bot_instance, adult_jid, reflection)
            ctx.enforcement_actions.append("self_reflection_dm")

    print(
        f"\n  💭 [ADULT SELF-MOD] Message flagged for self-reflection!"
        f"\n     Category: {ctx.primary_class} | "
        f"Original: {ctx.original_decision} → SELF_WARN"
        f"\n     No deletion. No parent alert. "
        f"DM sent: {'✅' if ctx.is_from_me else 'N/A'}"
    )


def _enforce_child_self_moderation(ctx):
    """Child's own toxic message: delete + educational DM + constructive parent alert."""
    from moderation.models import SecurityAlert, SelfModerationEvent
    from moderation.services.formatters import SEVERITY_MAP
    from moderation.evolution_api import (
        delete_message_from_whatsapp, send_educational_dm,
        send_constructive_parent_alert,
    )

    ctx.alert_severity = SEVERITY_MAP.get(ctx.decision, 'low')

    alerte = SecurityAlert.objects.create(
        moderation_result=ctx.moderation,
        severity=ctx.alert_severity,
        message_preview=ctx.raw_text[:200],
    )
    ctx.enforcement_actions.append("alert")
    ctx.broadcast_fn(ctx.moderation, alerte)
    ctx.enforcement_actions.append("broadcast")

    # Step 1: Delete the toxic message for everyone
    message_deleted = False
    if ctx.message_key_id:
        phone_jid = ctx.state.get("sender_phone_jid") or ctx.sender_jid
        delete_result = delete_message_from_whatsapp(
            ctx.instance_name, ctx.message_key_id, phone_jid, True,
        )
        message_deleted = bool(delete_result)
        if message_deleted:
            ctx.enforcement_actions.append("delete_for_everyone")

    # Step 2: Send educational DM via Aegis Assistant bot (Instance 2)
    bot_instance = os.getenv('AEGIS_BOT_INSTANCE_NAME', '')
    child_jid = ctx.child.whatsapp_jid if ctx.child else None

    dm_sent = False
    dm_text = ''
    if bot_instance and child_jid:
        dm_key_id, dm_text = send_educational_dm(
            bot_instance, child_jid, ctx.primary_class, ctx.raw_text,
        )
        dm_sent = dm_key_id is not None
        if dm_sent:
            ctx.enforcement_actions.append("educational_dm")
    else:
        logger.warning(
            "[AGENT 5: ENFORCER] ⚠️ Cannot send DM. "
            "Bot instance or child JID missing."
        )

    # Step 3: Send constructive parent notification ("Growth Moment")
    parent_notified = False
    if ctx.child and ctx.child.parent:
        parent_phone = ctx.child.parent.user.phone_number
        if parent_phone:
            try:
                send_constructive_parent_alert(
                    ctx.instance_name, parent_phone,
                    ctx.child.full_name, ctx.primary_class,
                )
                parent_notified = True
                ctx.enforcement_actions.append("constructive_parent_alert")
            except Exception as e:
                logger.warning(
                    f"[AGENT 5: ENFORCER] Constructive parent alert failed: {e}"
                )

    # Step 4: Record the SelfModerationEvent
    try:
        SelfModerationEvent.objects.create(
            moderation_result=ctx.moderation,
            category=ctx.primary_class,
            original_decision=ctx.original_decision,
            message_deleted=message_deleted,
            educational_dm_sent=dm_sent,
            educational_dm_text=dm_text,
            parent_notified=parent_notified,
        )
        ctx.enforcement_actions.append("self_mod_event")
    except Exception as e:
        logger.error(
            f"[AGENT 5: ENFORCER] Failed to create SelfModerationEvent: {e}"
        )

    print(
        f"\n  📚 [SELF-MODERATION] Child message caught!"
        f"\n     Category: {ctx.primary_class} | "
        f"Original: {ctx.original_decision} → EDUCATE"
        f"\n     Deleted: {'✅' if message_deleted else '❌'} | "
        f"DM Sent: {'✅' if dm_sent else '❌'} | "
        f"Parent: {'✅' if parent_notified else '❌'}"
    )


def _enforce_standard(ctx):
    """Incoming harmful message: react + warn + parent alert."""
    from moderation.models import SecurityAlert
    from moderation.services.formatters import SEVERITY_MAP
    from moderation.evolution_api import (
        delete_message_from_whatsapp, send_aegis_warning,
        send_aegis_reaction, send_aegis_presence, send_parent_alert,
    )

    ctx.alert_severity = SEVERITY_MAP.get(ctx.decision, 'medium')

    alerte = SecurityAlert.objects.create(
        moderation_result=ctx.moderation,
        severity=ctx.alert_severity,
        message_preview=ctx.raw_text[:200],
    )
    ctx.enforcement_actions.append("alert")
    ctx.broadcast_fn(ctx.moderation, alerte)
    ctx.enforcement_actions.append("broadcast")

    # ACTIVE SHIELD: Delete harmful messages from WhatsApp
    if ctx.decision in ('BLOCK', 'ESCALATE') and ctx.is_from_me:
        if ctx.message_key_id:
            delete_message_from_whatsapp(
                ctx.instance_name, ctx.message_key_id,
                ctx.sender_jid, True,
            )
            ctx.enforcement_actions.append("delete")

    # AUTO-REPLY: Tag + warn (not for HUMAN_REVIEW — wait for admin)
    if ctx.decision in ('BLOCK', 'ESCALATE', 'WARN', 'REVISE'):
        if ctx.message_key_id:
            react_map = {
                'ESCALATE': '🚨', 'BLOCK': '🛑',
                'WARN': '⚠️', 'REVISE': '👀',
            }
            send_aegis_reaction(
                ctx.instance_name, ctx.sender_jid,
                ctx.message_key_id, ctx.is_from_me,
                react_map.get(ctx.decision, '⚠️'),
            )
            ctx.enforcement_actions.append("react")

        # Resolve phone JID for the warning's remoteJid
        phone_jid = ctx.state.get("sender_phone_jid") or ctx.sender_jid

        # Build image flags for context-specific warning messages
        image_flags = None
        if ctx.state.get("image_analyzed"):
            image_flags = {
                "nsfw": ctx.state.get("image_nsfw", False),
                "violent": ctx.state.get("image_violent", False),
                "ocr_text": ctx.state.get("image_ocr_text", ""),
            }

        send_aegis_presence(ctx.instance_name, phone_jid, "composing", 1500)
        warning_result = send_aegis_warning(
            ctx.instance_name, phone_jid, ctx.primary_class,
            ctx.is_from_me, ctx.decision, ctx.message_key_id,
            image_flags=image_flags,
        )
        ctx.enforcement_actions.append("warn")

        # Extract warning anchor for archive
        warning_msg_key_id = None
        full_warning_message = None

        if isinstance(warning_result, tuple) and len(warning_result) == 3:
            warning_msg_key_id, exact_ts, full_warning_message = warning_result
            logger.info(
                f"[AGENT 5: ENFORCER] 📌 Warning anchor: "
                f"id={warning_msg_key_id}, ts={exact_ts}"
            )
            # Extract LID from warning response contextInfo
            ctx_info = full_warning_message.get("contextInfo", {}) or {}
            lid = (
                ctx_info.get("participant", "")
                or ctx_info.get("remoteJid", "")
            )
            if lid and "@lid" in lid:
                ctx.state["sender_jid"] = lid
                logger.info(
                    f"[AGENT 5: ENFORCER] ✅ LID extracted: {lid}"
                )
        elif isinstance(warning_result, tuple) and len(warning_result) == 2:
            warning_msg_key_id, _ = warning_result
        elif isinstance(warning_result, str) and len(warning_result) > 5:
            warning_msg_key_id = warning_result

        # PARENT ALERT: Notify parent on critical escalations or high-toxicity WARNs
        parent_phone = None
        if ctx.decision in ('ESCALATE', 'BLOCK', 'WARN') and ctx.child and ctx.child.parent:
            alert_threshold = getattr(ctx.child.parent, 'alert_threshold', 0.65)
            # BLOCK/ESCALATE always notify. WARN only notifies if toxicity >= threshold.
            if ctx.decision in ('ESCALATE', 'BLOCK') or (ctx.decision == 'WARN' and ctx.m1_score >= alert_threshold):
                parent_phone = ctx.child.parent.user.phone_number
            if parent_phone:
                send_parent_alert(
                    ctx.instance_name, parent_phone,
                    ctx.child.full_name, ctx.primary_class, ctx.raw_text,
                )
                ctx.enforcement_actions.append("parent_alert")

                # Twilio Emergency Voice Call (temporarily disabled)
                if getattr(ctx.child.parent, 'receive_call_on_critical', False):
                    pass

                # Twilio SMS Alert Backup
                if getattr(ctx.child.parent, 'receive_sms_alerts', False):
                    from moderation.services.twilio_service import send_sms_alert
                    send_sms_alert(
                        parent_phone, ctx.child.full_name,
                        ctx.primary_class, ctx.raw_text[:100],
                    )
                    ctx.enforcement_actions.append("sms_alert")

        # Archive + Block disabled (Baileys protocol instability)
        if ctx.decision in ('BLOCK', 'ESCALATE') and not ctx.is_from_me:
            logger.info(
                f"[AGENT 5: ENFORCER] ⚠️ Archive/Block disabled for "
                f"{phone_jid} (decision={ctx.decision}). "
                f"See DISABLED_FEATURES.md."
            )


def _enforce_safe(ctx):
    """Safe message: broadcast only."""
    ctx.broadcast_fn(ctx.moderation)
    ctx.enforcement_actions.append("broadcast")
