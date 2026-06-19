"""
AEGIS Proactive Alert Service
==============================
Generates proactive chatbot alerts when a parent's child receives
multiple flagged messages within a rolling time window.

Architecture:
  Enforcer creates SecurityAlert
       │
       └─► check_and_trigger_proactive_alert(parent_user, instance_name)
               │
               ├─ Count recent alerts (rolling 24h window)
               ├─ Check cooldown (4h between proactive alerts)
               ├─ Generate LLM summary (Groq)
               ├─ Create ChatSession + ChatMessage (is_proactive=True)
               ├─ Broadcast via Django Channels (ws/chatbot/)
               └─ Create ProactiveAlert tracking record

This service is designed to be called from the enforcer pipeline
after each SecurityAlert creation. It is fail-safe: any exception
is caught and logged without disrupting the moderation pipeline.
"""
import os
import logging
import datetime

from django.utils import timezone

logger = logging.getLogger(__name__)


def check_and_trigger_proactive_alert(parent_user, instance_name: str) -> bool:
    """
    Check if a proactive alert should be triggered for a parent.
    
    Called from the enforcer after each SecurityAlert creation.
    Returns True if a proactive alert was generated, False otherwise.
    
    Args:
        parent_user: The AegisUser (parent) to potentially alert
        instance_name: The Evolution API instance name
    
    Returns:
        bool: True if proactive alert was generated
    """
    from moderation.models import (
        SecurityAlert, ChatSession, ChatMessage, ProactiveAlert,
        MonitoredChild, ModerationResult,
    )
    from .rag_config import (
        PROACTIVE_ALERT_THRESHOLD,
        PROACTIVE_ALERT_WINDOW_HOURS,
        PROACTIVE_ALERT_COOLDOWN_HOURS,
    )
    
    if not parent_user or not instance_name:
        return False
    
    try:
        # ── 1. Count recent flagged messages in the rolling window ────────
        cutoff = timezone.now() - datetime.timedelta(hours=PROACTIVE_ALERT_WINDOW_HOURS)
        
        # Get all child JIDs linked to this parent's instance
        child_jids = list(
            MonitoredChild.objects.filter(
                parent__user=parent_user
            ).values_list('whatsapp_jid', flat=True)
        )
        
        if not child_jids:
            return False
        
        # Count SecurityAlerts in the window for this parent's children
        recent_alerts = SecurityAlert.objects.filter(
            moderation_result__instance_name=instance_name,
            moderation_result__sender_jid__in=child_jids,
            sent_at__gte=cutoff,
        ).select_related('moderation_result')
        
        alert_count = recent_alerts.count()
        
        if alert_count < PROACTIVE_ALERT_THRESHOLD:
            return False
        
        # ── 2. Check cooldown — don't spam the parent ─────────────────────
        cooldown_cutoff = timezone.now() - datetime.timedelta(hours=PROACTIVE_ALERT_COOLDOWN_HOURS)
        
        recent_proactive = ProactiveAlert.objects.filter(
            parent=parent_user,
            created_at__gte=cooldown_cutoff,
        ).exists()
        
        if recent_proactive:
            logger.debug(
                f"[PROACTIVE] Cooldown active for parent {parent_user.username}, skipping"
            )
            return False
        
        # ── 3. Collect alert metadata for LLM context ─────────────────────
        categories = list(
            recent_alerts.values_list(
                'moderation_result__primary_class', flat=True
            ).distinct()
        )
        categories = [c for c in categories if c and c != 'safe']
        
        # Get child's risk level
        child = MonitoredChild.objects.filter(
            parent__user=parent_user
        ).first()
        risk_level = child.get_risk_level() if child else 'UNKNOWN'
        
        # ── 4. Generate LLM summary ──────────────────────────────────────
        language = getattr(parent_user, 'language_preference', 'fr') or 'fr'
        
        summary = _generate_proactive_summary(
            trigger_count=alert_count,
            categories=categories,
            risk_level=risk_level,
            language=language,
        )
        
        if not summary:
            logger.warning("[PROACTIVE] LLM summary generation failed")
            return False
        
        # ── 5. Create ChatSession + ChatMessage ──────────────────────────
        session = ChatSession.objects.create(
            user=parent_user,
            language=language,
            is_proactive=True,
        )
        
        assistant_msg = ChatMessage.objects.create(
            session=session,
            role='assistant',
            content=summary,
            source_type='proactive',
            is_proactive=True,
        )
        
        # ── 6. Create ProactiveAlert tracking record ─────────────────────
        proactive_alert = ProactiveAlert.objects.create(
            parent=parent_user,
            chat_session=session,
            chat_message=assistant_msg,
            trigger_count=alert_count,
            trigger_window_hours=PROACTIVE_ALERT_WINDOW_HOURS,
            alert_categories=categories,
        )
        
        # ── 7. Broadcast via WebSocket to parent's chatbot ───────────────
        _broadcast_proactive_alert(parent_user, session, assistant_msg, proactive_alert)
        
        logger.info(
            f"[PROACTIVE] Alert generated for parent {parent_user.username}: "
            f"{alert_count} flagged messages, categories={categories}, "
            f"session={session.id}"
        )
        
        return True
        
    except Exception as e:
        logger.error(f"[PROACTIVE] Error in check_and_trigger: {e}", exc_info=True)
        return False


def _generate_proactive_summary(
    trigger_count: int,
    categories: list[str],
    risk_level: str,
    language: str,
) -> str | None:
    """
    Generate an LLM summary for the proactive alert using Groq.
    
    Args:
        trigger_count: Number of flagged messages
        categories: List of detected categories
        risk_level: Child's current risk level
        language: Parent's preferred language
    
    Returns:
        str: Generated summary message, or None on failure
    """
    from .rag_config import PROACTIVE_ALERT_SYSTEM_PROMPT, PROACTIVE_ALERT_GREETINGS
    
    try:
        from langchain_groq import ChatGroq
        
        api_key = os.getenv("GROQ_API_KEY", "").strip().strip('"')
        if not api_key:
            logger.error("[PROACTIVE] GROQ_API_KEY not set")
            return None
        
        # Format the categories for display
        categories_str = ", ".join(categories) if categories else "general harmful content"
        
        # Build the system prompt with context
        system_prompt = PROACTIVE_ALERT_SYSTEM_PROMPT.format(
            language=language,
            trigger_count=trigger_count,
            window_hours=24,
            categories=categories_str,
            risk_level=risk_level,
        )
        
        # User prompt — simple trigger
        user_prompt = (
            f"Please generate a proactive alert for the parent. "
            f"{trigger_count} messages were flagged in the last 24 hours "
            f"involving: {categories_str}."
        )
        
        llm = ChatGroq(
            api_key=api_key,
            model_name="qwen/qwen3-32b",
            temperature=0.3,
            max_tokens=500,
        )
        
        response = llm.invoke([
            ("system", system_prompt),
            ("user", user_prompt),
        ])
        
        summary = str(response.content).strip()
        
        # Add language-specific greeting header
        greeting = PROACTIVE_ALERT_GREETINGS.get(language, PROACTIVE_ALERT_GREETINGS.get("en"))
        
        # Convert markdown bold to HTML bold for UI rendering
        import re
        summary = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', summary)
        
        full_message = f"{greeting}\n\n{summary}"
        
        return full_message
        
    except Exception as e:
        logger.error(f"[PROACTIVE] LLM generation error: {e}", exc_info=True)
        
        # Fallback: generate a simple template-based message
        return _generate_fallback_summary(trigger_count, categories, language)


def _generate_fallback_summary(
    trigger_count: int,
    categories: list[str],
    language: str,
) -> str:
    """
    Generate a simple template-based fallback when LLM is unavailable.
    """
    from .rag_config import PROACTIVE_ALERT_GREETINGS
    
    greeting = PROACTIVE_ALERT_GREETINGS.get(language, PROACTIVE_ALERT_GREETINGS.get("en"))
    categories_str = ", ".join(categories) if categories else "harmful content"
    
    templates = {
        "fr": (
            f"{greeting}\n\n"
            f"<b>{trigger_count} messages</b> ont été signalés sur l'appareil de votre enfant "
            f"au cours des dernières 24 heures.\n\n"
            f"Catégories détectées: <b>{categories_str}</b>\n\n"
            f"Nous vous recommandons de:\n"
            f"• Discuter ouvertement avec votre enfant de son activité en ligne\n"
            f"• Vérifier ses paramètres de confidentialité\n\n"
            f"Souhaitez-vous en savoir plus sur les mesures à prendre?"
        ),
        "en": (
            f"{greeting}\n\n"
            f"<b>{trigger_count} messages</b> have been flagged on your child's device "
            f"in the last 24 hours.\n\n"
            f"Categories detected: <b>{categories_str}</b>\n\n"
            f"We recommend you:\n"
            f"• Have an open conversation with your child about their online activity\n"
            f"• Review their privacy settings\n\n"
            f"Would you like to learn more about what steps you can take?"
        ),
        "ar": (
            f"{greeting}\n\n"
            f"<b>{trigger_count} رسائل</b> تم الإبلاغ عنها على جهاز طفلك "
            f"خلال الـ 24 ساعة الماضية.\n\n"
            f"الفئات المكتشفة: <b>{categories_str}</b>\n\n"
            f"ننصحك بـ:\n"
            f"• التحدث بصراحة مع طفلك حول نشاطه على الإنترنت\n"
            f"• مراجعة إعدادات الخصوصية\n\n"
            f"هل تريد معرفة المزيد عن الخطوات التي يمكنك اتخاذها؟"
        ),
        "darija": (
            f"{greeting}\n\n"
            f"<b>{trigger_count} رسائل</b> تم الإبلاغ عنها على جهاز ولدك "
            f"فـ 24 ساعة الأخيرة.\n\n"
            f"الفئات المكتشفة: <b>{categories_str}</b>\n\n"
            f"ننصحك بـ:\n"
            f"• تهدر مع ولدك على نشاطو فـ الإنترنت\n"
            f"• تراجع إعدادات الخصوصية ديالو\n\n"
            f"واش بغيتي تعرف أكثر على الخطوات اللي تقدر دير؟"
        ),
    }
    
    return templates.get(language, templates["en"])


def _broadcast_proactive_alert(parent_user, session, message, proactive_alert):
    """
    Broadcast the proactive alert via Django Channels WebSocket
    to the parent's chatbot connection.
    """
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        
        channel_layer = get_channel_layer()
        
        payload = {
            "type": "proactive_alert",
            "alert_id": str(proactive_alert.id),
            "session_id": str(session.id),
            "message_id": str(message.id),
            "content": message.content,
            "trigger_count": proactive_alert.trigger_count,
            "categories": proactive_alert.alert_categories,
            "timestamp": message.sent_at.isoformat(),
        }
        
        async_to_sync(channel_layer.group_send)(
            f"chatbot_{parent_user.id}",
            {
                "type": "proactive.message",
                "data": payload,
            }
        )
        
        logger.info(
            f"[PROACTIVE] WebSocket broadcast sent to chatbot_{parent_user.id}"
        )
        
    except Exception as e:
        logger.warning(f"[PROACTIVE] WebSocket broadcast failed: {e}")
