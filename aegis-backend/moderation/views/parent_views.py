"""
Parent-scoped API endpoints for AEGIS.
These mirror admin endpoints but filter data to ONLY show results
related to the logged-in parent's monitored child(ren).

Extracted from views.py during Phase 2 audit refactoring (2026-04-21).
"""
import datetime
import logging

from django.db.models import Count, Q
from django.db.models.functions import ExtractHour
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from moderation.models import (
    ModerationResult, UserBehaviorProfile, SecurityAlert,
    MonitoredChild, ParentProfile, SelfModerationEvent
)
from moderation.permissions import IsParentUser
from moderation.services.formatters import get_severity, SEVERITY_MAP, format_phone_number
from moderation.services.risk_calculator import (
    calculate_risk_level, escalate_risk_by_actor, risk_score_from_level
)
from moderation.views.webhook import get_avg_latency

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════
# PARENT-SCOPED API ENDPOINTS
# These mirror the admin endpoints but filter data to ONLY show results
# related to the logged-in parent's monitored child(ren).
# ════════════════════════════════════════════════════════════════════════

def _get_parent_filter(user):
    """
    Returns a Q filter that restricts ModerationResults to only those
    belonging to the logged-in parent's child(ren).
    Uses both the Evolution API instance name AND child WhatsApp JIDs.
    """
    profile = user.parent_profile
    instance_name = profile.evolution_instance_name

    # Get all child JIDs linked to this parent
    child_jids = list(profile.children.values_list('whatsapp_jid', flat=True))

    # Build filter: match by instance OR by sender_jid being a child JID
    q = Q()
    if instance_name:
        q |= Q(instance_name=instance_name)
    if child_jids:
        q |= Q(sender_jid__in=child_jids)

    return q, profile, child_jids


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsParentUser])
def parent_dashboard_stats(request):
    """
    GET /api/v1/parent/stats/
    Dashboard stats filtered to the parent's child only.
    Same structure as /stats/dashboard/ but scoped.
    """
    user = request.user

    parent_q, profile, child_jids = _get_parent_filter(user)
    today = timezone.now().date()

    # All moderation results scoped to this parent's child
    all_results = ModerationResult.objects.filter(parent_q)
    today_results = all_results.filter(created_at__date=today)

    # ---------------- CALCULATE RISK LEVEL DYNAMICALLY ----------------
    thirty_days_ago = timezone.now() - datetime.timedelta(days=30)

    blocked_count = all_results.filter(
        decision__in=['BLOCK', 'ESCALATE', 'WARN', 'REVISE', 'SELF_WARN'],
        created_at__gte=thirty_days_ago
    ).count()

    base_level, _ = calculate_risk_level(blocked_count)

    # Get max threat actor risk
    sender_jids_all = list(all_results.exclude(sender_jid__in=child_jids).exclude(sender_jid='').values_list('sender_jid', flat=True).distinct())
    max_actor_risk = 0.0
    if sender_jids_all:
        risky = UserBehaviorProfile.objects.filter(user_jid__in=sender_jids_all).order_by('-total_blocked_messages_sent')[:10]
        for p in risky:
            if p.risk_score > 0:
                max_actor_risk = max(max_actor_risk, p.risk_score)

    dynamic_risk_level = escalate_risk_by_actor(base_level, max_actor_risk)
    # ------------------------------------------------------------------

    # Get child info for the UI header
    children = profile.children.all()
    if children.exists():
        child = children.first()
        child_info = {
            "id": str(child.id),
            "name": child.full_name,
            "whatsapp_jid": child.whatsapp_jid,
            "display_number": child.whatsapp_display_number,
            "risk_level": dynamic_risk_level,
            "is_monitored": child.is_monitored,
        }
    else:
        connected_number = "Device Linked"
        if profile.evolution_instance_name:
            try:
                from moderation.evolution_api import get_instance_details
                details = get_instance_details(profile.evolution_instance_name)
                if details and details.get('ownerJid'):
                    raw_num = details['ownerJid'].split('@')[0]
                    connected_number = f"+{raw_num[:3]} {raw_num[3:]}" if len(raw_num) > 4 else f"+{raw_num}"
            except Exception:
                pass

        child_info = {
            "id": "unknown",
            "name": "Your Monitored Device",
            "whatsapp_jid": "",
            "display_number": connected_number,
            "risk_level": dynamic_risk_level,
            "is_monitored": bool(profile.evolution_instance_name),
        }

    # Core metrics
    total_messages = today_results.count()
    total_blocked = today_results.filter(decision__in=['BLOCK', 'ESCALATE', 'SELF_WARN']).count()

    # Alerts scoped to the parent's child
    alert_q = Q()
    if profile.evolution_instance_name:
        alert_q |= Q(moderation_result__instance_name=profile.evolution_instance_name)
    if child_jids:
        alert_q |= Q(moderation_result__sender_jid__in=child_jids)
    total_alerts = SecurityAlert.objects.filter(alert_q, sent_at__date=today).count()

    # LLM interventions
    llm_interventions = today_results.filter(llm_triggered=True).count()

    # All-time stats for more persistent dashboard cards
    total_messages_all_time = all_results.count()
    total_blocked_all_time = all_results.filter(decision__in=['BLOCK', 'ESCALATE', 'SELF_WARN']).count()
    total_alerts_all_time = SecurityAlert.objects.filter(alert_q).count()

    # Category breakdown
    category_counts = today_results.exclude(primary_class='safe').values('primary_class').annotate(count=Count('id'))
    category_breakdown = {item['primary_class']: item['count'] for item in category_counts}

    # Weekly activity (7 days)
    seven_days_ago = today - timezone.timedelta(days=6)
    recent_results = all_results.filter(created_at__date__gte=seven_days_ago)
    weekly_data = []
    for i in range(7):
        day_date = today - timezone.timedelta(days=6-i)
        day_results = recent_results.filter(created_at__date=day_date)
        weekly_data.append({
            "day": day_date.strftime("%a"),
            "blocked": day_results.filter(decision__in=['BLOCK', 'ESCALATE', 'SELF_WARN']).count(),
            "warned": day_results.filter(decision__in=['WARN', 'REVISE']).count(),
            "safe": day_results.filter(decision='ALLOW').count()
        })

    # Hourly activity (today)
    hourly_counts = today_results.annotate(hour=ExtractHour('created_at')).values('hour', 'decision').annotate(count=Count('id'))

    hourly_data = {
        "labels": ['00h', '02h', '04h', '06h', '08h', '10h', '12h', '14h', '16h', '18h', '20h', '22h'],
        "threats": [0] * 12,
        "safe": [0] * 12
    }
    for entry in hourly_counts:
        bucket_idx = entry['hour'] // 2
        if entry['decision'] in ['BLOCK', 'ESCALATE', 'WARN', 'REVISE', 'SELF_WARN']:
            hourly_data["threats"][bucket_idx] += entry['count']
        elif entry['decision'] == 'ALLOW':
            hourly_data["safe"][bucket_idx] += entry['count']

    # Child's risk profile (behavioral profile for the child's contacts)
    at_risk_contacts = []
    # Get behavioral profiles for senders who contacted this child
    sender_jids = list(all_results.exclude(sender_jid__in=child_jids).exclude(sender_jid='').values_list('sender_jid', flat=True).distinct())
    if sender_jids:
        risky = UserBehaviorProfile.objects.filter(user_jid__in=sender_jids).order_by('-total_blocked_messages_sent')[:5]
        at_risk_contacts = [{
            "id": str(p.id),
            "whatsapp": p.user_jid,
            "risk_score": p.risk_score,
            "risk_level": p.risk_level,
            "blocked_total": p.total_blocked_messages_sent,
            "sent_total": p.total_messages_sent
        } for p in risky]

    # Language distribution scoped to parent's child
    lang_counts = all_results.exclude(
        language__isnull=True
    ).exclude(language='other').exclude(language='error').values('language').annotate(count=Count('id')).order_by('-count')

    lang_labels = []
    lang_data = []
    for item in lang_counts:
        lang = str(item['language']).upper()
        if lang:
            lang_labels.append(lang)
            lang_data.append(item['count'])

    language_distribution = {
        "labels": lang_labels if lang_labels else ['UNKNOWN'],
        "data": lang_data if lang_data else [1]
    }

    return Response({
        "child": child_info,
        "stats": {
            "total_messages_today": total_messages,
            "total_alerts_today": total_alerts,
            "total_blocked_today": total_blocked,
            "total_messages_all_time": total_messages_all_time,
            "total_alerts_all_time": total_alerts_all_time,
            "total_blocked_all_time": total_blocked_all_time,
            "llm_interventions": llm_interventions,
            "avg_latency_ms": get_avg_latency('agent_1', 42) + get_avg_latency('agent_2', 287) + get_avg_latency('agent_5', 12),
        },
        "category_breakdown": category_breakdown,
        "weekly_activity": weekly_data,
        "at_risk_contacts": at_risk_contacts,
        "hourly_activity": hourly_data,
        "language_distribution": language_distribution,
    })


# ────────────────────────────────────────────────────────────────────────────────
# DIGITAL CITIZENSHIP ENDPOINT
# ────────────────────────────────────────────────────────────────────────────────

# Parenting tips shown per category — constructive & non-punitive
PARENTING_TIPS = {
    'verbal_harassment': "Children often lash out verbally when they're frustrated or overwhelmed. Ask them calmly how they're feeling without mentioning the message.",
    'threat': "Sending threats is often a sign of helplessness or escalating conflict. Try creating a safe space for your child to express strong emotions verbally instead.",
    'sexual_harassment': "This can indicate exposure to inappropriate content or peer pressure. Consider an open, non-judgmental conversation about respectful communication.",
    'discrimination': "Discriminatory language is often learned from the environment. This is a good opportunity to discuss respect for others regardless of background.",
    'repeated_messages': "Sending repeated messages can be a sign of anxiety or conflict. Ask if they are in a conflict situation that needs your support.",
    'identity_theft': "Impersonation online can have serious consequences. This is a great moment to discuss digital identity and the impact of online actions.",
}
DEFAULT_TIP = "This is a good opportunity to have a calm, open conversation about digital kindness and responsible messaging."


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsParentUser])
def parent_digital_citizenship(request):
    """
    GET /api/v1/parent/digital-citizenship/
    Returns SelfModerationEvent records for the parent's Digital Citizenship tab.

    Privacy-first: Parents see WHAT CATEGORY of message was caught and WHAT
    the bot said to their child, but NOT the raw offensive text. This preserves
    the educational intent and avoids triggering punitive reactions.

    Response includes constructive parenting tips per category.
    """
    user = request.user
    parent_q, profile, child_jids = _get_parent_filter(user)

    # 1. Fetch self-moderation events linked to this parent's child
    events = SelfModerationEvent.objects.filter(
        moderation_result__in=ModerationResult.objects.filter(parent_q)
    ).select_related('moderation_result').order_by('-created_at')[:50]
    
    # 2. Fetch BotConversations linked to the child
    from moderation.models import BotConversation
    bot_messages = BotConversation.objects.filter(
        child_jid__in=child_jids
    ).order_by('created_at')

    # Summary stats
    total_events = events.count()
    deleted_count = sum(1 for e in events if e.message_deleted)
    dm_sent_count = sum(1 for e in events if e.educational_dm_sent)

    # Category breakdown
    category_counts: dict = {}
    for e in events:
        cat = e.category or 'unknown'
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # Build the self-moderation data list
    interventions_data = []
    for e in events:
        cat = e.category or 'unknown'
        interventions_data.append({
            "type": "intervention",
            "id": f"sm_{e.id}",
            "created_at": e.created_at.isoformat(),
            "category": cat,
            "category_label": cat.replace('_', ' ').title(),
            "original_severity": e.original_decision,
            "message_deleted": e.message_deleted,
            "educational_dm_sent": e.educational_dm_sent,
            "educational_dm_text": e.educational_dm_text or "",
            "parent_notified": e.parent_notified,
            "parenting_tip": PARENTING_TIPS.get(cat, DEFAULT_TIP),
        })

    # 3. Group BotConversations into Sessions (1 hour gap = new session)
    sessions_data = []
    current_session = None
    
    for msg in bot_messages:
        if not current_session:
            current_session = {
                "type": "bot_session",
                "id": f"bs_{msg.id}",
                "created_at": msg.created_at.isoformat(),
                "last_activity": msg.created_at,
                "message_count": 1,
                "has_safety_alert": msg.is_safety_flagged,
                "threat_intel": msg.threat_intel,
            }
        else:
            gap = (msg.created_at - current_session["last_activity"]).total_seconds()
            if gap > 3600: # 1 hour gap -> new session
                # Save previous session
                current_session["last_activity"] = current_session["last_activity"].isoformat()
                sessions_data.append(current_session)
                
                # Start new session
                current_session = {
                    "type": "bot_session",
                    "id": f"bs_{msg.id}",
                    "created_at": msg.created_at.isoformat(),
                    "last_activity": msg.created_at,
                    "message_count": 1,
                    "has_safety_alert": msg.is_safety_flagged,
                    "threat_intel": msg.threat_intel,
                }
            else:
                # Update current session
                current_session["message_count"] += 1
                current_session["last_activity"] = msg.created_at
                if msg.is_safety_flagged:
                    current_session["has_safety_alert"] = True
                if msg.threat_intel:
                    current_session["threat_intel"] = msg.threat_intel
                    
    if current_session:
        current_session["last_activity"] = current_session["last_activity"].isoformat()
        sessions_data.append(current_session)
        
    # Stats for Bot Sessions
    total_sessions = len(sessions_data)
    total_alerts = sum(1 for s in sessions_data if s["has_safety_alert"])
    
    # Merge and sort all items (interventions + bot sessions) by created_at DESC
    all_timeline_items = interventions_data + sessions_data
    all_timeline_items.sort(key=lambda x: x["created_at"], reverse=True)

    return Response({
        "summary": {
            "total_events": total_events,
            "messages_deleted": deleted_count,
            "educational_dms_sent": dm_sent_count,
            "category_breakdown": category_counts,
            "total_bot_sessions": total_sessions,
            "total_safety_alerts": total_alerts,
        },
        "timeline": all_timeline_items,
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsParentUser])
def parent_alert_list(request):
    """
    GET /api/v1/parent/alerts/
    Alerts filtered to the parent's child only.
    Same response format as /alerts/ for UI reuse.
    """
    user = request.user

    parent_q, profile, child_jids = _get_parent_filter(user)

    results = ModerationResult.objects.filter(parent_q).filter(
        decision__in=['BLOCK', 'ESCALATE', 'REVISE', 'WARN', 'HUMAN_REVIEW', 'SELF_WARN']
    ).select_related().prefetch_related('alerts').order_by('-created_at')[:100]

    data = []
    for r in results:
        alert_obj = r.alerts.first()
        severity = get_severity(r.decision, alert_obj)
        data.append({
            "id": str(r.id),
            "created_at": r.created_at.isoformat(),
            "raw_text": r.raw_text,
            "primary_class": r.primary_class or 'safe',
            "decision": r.decision,
            "severity": severity,
            "toxicity_score": r.toxicity_score,
            "confidence_score": r.confidence_score,
            "llm_triggered": r.llm_triggered,
            "llm_explanation": r.llm_explanation,
            "language": r.language or 'unknown',
            "sender_jid": r.sender_jid,
            "human_reviewed": r.human_reviewed,
            "human_decision": r.human_decision,
            "human_label": r.human_label,
        })
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsParentUser])
def parent_activity_feed(request):
    """
    GET /api/v1/parent/activity/
    Recent moderation events (ALL decisions) filtered to parent's child only.
    Seeds the parent dashboard activity feed.
    
    Privacy: raw_text is ONLY returned for flagged decisions (BLOCK, ESCALATE, WARN, etc).
    For ALLOW (safe messages), raw_text is withheld — parents see behavioral signals,
    not the message content. This aligns with our Loi 09-08 compliance philosophy.
    For EDUCATE (self-moderation), the category and DM are shown, not the raw offensive text.
    """
    user = request.user

    parent_q, _, _ = _get_parent_filter(user)

    results = ModerationResult.objects.filter(parent_q).order_by('-created_at')[:20]



    # Decisions where the parent is allowed to see raw content
    CONTENT_ALLOWED_DECISIONS = {'WARN', 'BLOCK', 'ESCALATE', 'REVISE', 'HUMAN_REVIEW', 'SELF_WARN'}

    data = []
    for r in results:
        # Privacy gate: safe messages and educational events don't expose raw text
        is_content_visible = r.decision in CONTENT_ALLOWED_DECISIONS
        
        # For EDUCATE events, surface the educational DM text instead of the offensive message
        educational_dm_text = None
        if r.decision == 'EDUCATE':
            try:
                educational_dm_text = r.self_moderation_event.educational_dm_text
            except Exception:
                pass
        
        data.append({
            "id": str(r.id),
            "created_at": r.created_at.isoformat(),
            # raw_text: only for flagged messages, never for ALLOW or EDUCATE
            "raw_text": r.raw_text if is_content_visible else None,
            "primary_class": r.primary_class or 'safe',
            "decision": r.decision,
            "severity": SEVERITY_MAP.get(r.decision, 'medium'),
            "toxicity_score": r.toxicity_score,
            "confidence_score": r.confidence_score,
            "llm_triggered": r.llm_triggered,
            "llm_explanation": r.llm_explanation if is_content_visible else None,
            "language": r.language or 'unknown',
            "sender_jid": r.sender_jid,
            "is_self_moderation": r.is_self_moderation,
            "educational_dm_text": educational_dm_text,
        })
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsParentUser])
def parent_blocked_messages(request):
    """GET /api/v1/parent/blocked-messages/ - Only BLOCK or ESCALATE"""
    user = request.user

    parent_q, profile, child_jids = _get_parent_filter(user)
    
    # We want ModerationResults with BLOCK or ESCALATE
    blocked = ModerationResult.objects.filter(parent_q).filter(decision__in=['BLOCK', 'ESCALATE', 'SELF_WARN']).order_by('-created_at')
    
    data = []
    for r in blocked:
        data.append({
            "id": str(r.id),
            "senderName": r.sender_jid,
            "senderAvatar": f"https://ui-avatars.com/api/?name={r.sender_jid[:2]}&background=ef4444&color=fff",
            "timestamp": r.created_at.isoformat(),
            "snippet": r.raw_text[:40] + ("..." if len(r.raw_text) > 40 else ""),
            "fullMessage": r.raw_text,
            "aiReason": r.primary_class,
            "aiExplanation": r.llm_explanation or "Intercepted by Active Shield.",
            "confidenceScore": r.confidence_score or r.toxicity_score
        })
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsParentUser])
def parent_conversations(request):
    """GET /api/v1/parent/conversations/"""
    user = request.user

    parent_q, profile, child_jids = _get_parent_filter(user)
    
    # We want to group everything by conversation.
    # In AEGIS, messages are stored in `Message` model which links to `Conversation`.
    # Let's just fetch all Conversations for this Parent's instance or child.
    instance_name = profile.evolution_instance_name
    
    # We can just fetch ModerationResults to build contacts and conversations dynamically
    all_results = ModerationResult.objects.filter(parent_q).order_by('-created_at')
    
    contacts_map = {}
    
    sender_jids = list(all_results.values_list('sender_jid', flat=True).distinct())
    profiles = UserBehaviorProfile.objects.filter(user_jid__in=sender_jids)
    profile_dict = {p.user_jid: p for p in profiles}
    
    for r in all_results:
        jid = r.sender_jid
        if not jid: continue
        if jid not in contacts_map:
            prof = profile_dict.get(jid)
            contacts_map[jid] = {
                "id": jid,
                "name": jid,
                "platform": "whatsapp",
                "risk_level": prof.risk_level.lower() if prof else "low",
                "risk_score": prof.risk_score if prof else 0.1,
                "avatar": f"https://ui-avatars.com/api/?name={jid[:2]}&background=64748b&color=fff",
                "messages": []
            }
            
        contacts_map[jid]["messages"].append({
            "id": str(r.id),
            "direction": "incoming", 
            "content": r.raw_text,
            "timestamp": r.created_at.isoformat(),
            "is_flagged": r.decision != 'ALLOW',
            "is_blocked": r.decision in ['BLOCK', 'ESCALATE', 'SELF_WARN'],
            "decision": r.decision,
            "toxicity_score": r.toxicity_score,
            "category": r.primary_class,
            "ai_explanation": r.llm_explanation
        })
        
    # Reverse messages inside each contact to chronological (they were appended in reverse chronological)
    for j in contacts_map:
        contacts_map[j]["messages"].reverse()
        
    return Response({
        "contacts": list(contacts_map.values())
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsParentUser])
def parent_risk_profile(request):
    """GET /api/v1/parent/risk-profile/"""
    user = request.user

    parent_q, profile, child_jids = _get_parent_filter(user)
    
    child = profile.children.first()
    
    connected_number = "Unknown"
    if not child and profile.evolution_instance_name:
        try:
            from moderation.evolution_api import get_instance_details
            details = get_instance_details(profile.evolution_instance_name)
            if details and details.get('ownerJid'):
                raw_num = details['ownerJid'].split('@')[0]
                connected_number = f"+{raw_num[:3]} {raw_num[3:]}" if len(raw_num) > 4 else f"+{raw_num}"
        except Exception:
            pass

    child_info = {
        "name": child.full_name if child else "Your Monitored Device",
        "number": child.whatsapp_display_number or child.whatsapp_jid if child else connected_number
    }
    
    if child:
        risk_level = child.get_risk_level()
    else:
        risk_level = 'LOW'
        
    # Build threat actors
    all_results = ModerationResult.objects.filter(parent_q)
    sender_jids = list(all_results.exclude(sender_jid__in=child_jids).exclude(sender_jid='').values_list('sender_jid', flat=True).distinct())
    
    threat_actors = []
    max_actor_risk = 0.0
    
    if sender_jids:
        risky = UserBehaviorProfile.objects.filter(user_jid__in=sender_jids).order_by('-total_blocked_messages_sent')[:10]
        for p in risky:
            if p.risk_score > 0:
                max_actor_risk = max(max_actor_risk, p.risk_score)
                
                # Fetch recent name to determine if stranger
                contact_results = all_results.filter(sender_jid=p.user_jid)
                recent_name_result = contact_results.exclude(sender_name__isnull=True).exclude(sender_name='').order_by('-created_at').first()
                push_name = recent_name_result.sender_name if recent_name_result else ""
                
                raw_num = p.user_jid.split('@')[0]
                formatted_number = f"+{raw_num[:3]} {raw_num[3:]}" if len(raw_num) > 4 else f"+{raw_num}"
                days_known = (timezone.now() - p.first_seen_at).days if p.first_seen_at else 0
                is_stranger = days_known < 14
                display_name = push_name if not is_stranger else "Unknown Contact"

                threat_actors.append({
                    "id": str(p.id),
                    "name": display_name,
                    "number": formatted_number,
                    "score": p.risk_score,
                    "level": p.risk_level.lower(),
                    "child_initiated": p.child_initiated,
                    "night_activity": p.night_activity_ratio,
                    "is_stranger": is_stranger,
                    "archetype": "Suspicious Activity" # Generic for parents
                })
                
    # Recalculate robust risk level using extracted service functions
    thirty_days_ago = timezone.now() - datetime.timedelta(days=30)

    blocked_count = all_results.filter(
        decision__in=['BLOCK', 'ESCALATE', 'WARN', 'REVISE', 'SELF_WARN'],
        created_at__gte=thirty_days_ago
    ).count()

    base_level, _ = calculate_risk_level(blocked_count)
    risk_level = escalate_risk_by_actor(base_level, max_actor_risk)
    current_score = risk_score_from_level(risk_level, blocked_count)
    
    # Generate trend data based on actual moderation history (not random)
    trend_data = []
    trend_labels = ["Week 1", "Week 2", "Week 3", "Week 4", "Today"]
    for i in range(4):
        week_start = timezone.now() - datetime.timedelta(weeks=4-i)
        week_end = timezone.now() - datetime.timedelta(weeks=3-i)
        week_blocked = all_results.filter(
            decision__in=['BLOCK', 'ESCALATE', 'WARN', 'REVISE', 'SELF_WARN'],
            created_at__range=(week_start, week_end)
        ).count()
        # Map weekly blocked count to a 0-1 score using same thresholds
        if week_blocked >= 10: point = 0.85
        elif week_blocked >= 5: point = 0.65
        elif week_blocked >= 1: point = 0.35
        else: point = 0.10
        trend_data.append(round(point, 2))
    trend_data.append(current_score)
                
    return Response({
        "child": child_info,
        "risk_level": risk_level.lower(),
        "risk_score": current_score,
        "threat_actors": threat_actors,
        "risk_trend": {
            "labels": trend_labels,
            "data": trend_data
        }
    })


# ════════════════════════════════════════════════════════════════════════
# EMOTIONAL PATTERN HEATMAP
# ════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsParentUser])
def parent_emotional_heatmap(request):
    """
    Returns a 7×6 heatmap matrix (day-of-week × time-slot) showing
    when the user's flagged messages occur most frequently.
    
    Response:
        {
            "days": ["Mon", "Tue", ...],
            "slots": ["12am-4am", "4am-8am", ...],
            "matrix": [[0, 1, 0, ...], ...]   # rows=slots, cols=days
        }
    """
    user = request.user
    parent_q, profile, child_jids = _get_parent_filter(user)
    
    # Only flagged/harmful messages (not ALLOW)
    flagged = ModerationResult.objects.filter(parent_q).exclude(
        decision='ALLOW'
    )
    
    # Optional: filter to last N days
    range_param = request.GET.get('range', '30')
    try:
        days_back = int(range_param)
    except ValueError:
        days_back = 30
    cutoff = timezone.now() - datetime.timedelta(days=days_back)
    flagged = flagged.filter(created_at__gte=cutoff)
    
    # Time slots: 6 buckets of 4 hours
    SLOT_LABELS = [
        "12am-4am", "4am-8am", "8am-12pm",
        "12pm-4pm", "4pm-8pm", "8pm-12am"
    ]
    DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    
    # Initialize 6×7 matrix (slots × days)
    matrix = [[0] * 7 for _ in range(6)]
    
    for ts in flagged.values_list('created_at', flat=True):
        dow = ts.weekday()   # 0=Mon, 6=Sun
        hour = ts.hour
        slot_idx = min(hour // 4, 5)
        matrix[slot_idx][dow] += 1
    
    return Response({
        "days": DAY_LABELS,
        "slots": SLOT_LABELS,
        "matrix": matrix
    })


# ════════════════════════════════════════════════════════════════════════
# FORENSIC EVIDENCE EXPORT
# ════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsParentUser])
def parent_export_evidence(request):
    """
    Generates a forensic-grade JSON report of all flagged messages
    with timestamps, severity scores, SHA-256 content hashes, and
    sender behavior profiles. Designed for legal evidence.
    
    Query params:
        ?days=30    — how far back to include (default: 30)
    """
    import hashlib
    
    user = request.user
    parent_q, profile, child_jids = _get_parent_filter(user)
    
    days_back = int(request.GET.get('days', '30'))
    cutoff = timezone.now() - datetime.timedelta(days=days_back)
    
    results = ModerationResult.objects.filter(parent_q).filter(
        decision__in=['BLOCK', 'ESCALATE', 'WARN', 'REVISE', 'SELF_WARN'],
        created_at__gte=cutoff
    ).order_by('created_at')
    
    evidence_entries = []
    for r in results:
        content_hash = hashlib.sha256(
            (r.raw_text or '').encode('utf-8')
        ).hexdigest()
        
        evidence_entries.append({
            "id": str(r.id),
            "timestamp": r.created_at.isoformat(),
            "sender_jid": r.sender_jid,
            "sender_name": r.sender_name or '',
            "content": r.raw_text,
            "content_hash_sha256": content_hash,
            "decision": r.decision,
            "primary_class": r.primary_class or 'unknown',
            "toxicity_score": round(r.toxicity_score, 4),
            "confidence_score": round(r.confidence_score, 4) if r.confidence_score else None,
            "ai_explanation": r.llm_explanation or '',
            "is_from_me": r.is_from_me,
        })
    
    # Gather unique senders and their behavioral profiles
    sender_jids = set(r.sender_jid for r in results if not r.is_from_me)
    sender_profiles = []
    for jid in sender_jids:
        try:
            bp = UserBehaviorProfile.objects.get(user_jid=jid)
            sender_profiles.append({
                "jid": jid,
                "risk_level": bp.risk_level,
                "risk_score": round(bp.risk_score, 4),
                "total_messages": bp.total_messages_sent,
                "total_blocked": bp.total_blocked_messages_sent,
                "block_ratio": round(bp.block_ratio, 4),
                "escalation_count": bp.escalation_count,
            })
        except UserBehaviorProfile.DoesNotExist:
            pass
    
    return Response({
        "report_title": "AEGIS Forensic Evidence Report",
        "generated_at": timezone.now().isoformat(),
        "generated_by": f"{user.first_name} {user.last_name}".strip() or user.username,
        "period": f"Last {days_back} days",
        "total_incidents": len(evidence_entries),
        "summary": {
            "total_flagged": len(evidence_entries),
            "total_block": sum(1 for e in evidence_entries if e['decision'] == 'BLOCK'),
            "total_escalate": sum(1 for e in evidence_entries if e['decision'] == 'ESCALATE'),
            "total_warn": sum(1 for e in evidence_entries if e['decision'] in ['WARN', 'REVISE']),
            "total_self_warn": sum(1 for e in evidence_entries if e['decision'] == 'SELF_WARN'),
            "unique_senders": len(sender_jids),
        },
        "incidents": evidence_entries,
        "sender_profiles": sender_profiles,
        "integrity_note": (
            "Each message includes a SHA-256 content hash computed at export time. "
            "This hash can be used to verify that the content has not been modified "
            "since this report was generated."
        ),
    })
