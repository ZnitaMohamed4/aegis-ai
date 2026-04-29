"""
Parent-scoped API endpoints for AEGIS.
These mirror admin endpoints but filter data to ONLY show results
related to the logged-in parent's monitored child(ren).

Extracted from views.py during Phase 2 audit refactoring (2026-04-21).
"""
import datetime
import datetime as _dt
import logging

from django.db.models import Count, Q
from django.db.models.functions import ExtractHour
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from moderation.models import (
    ModerationResult, UserBehaviorProfile, SecurityAlert,
    MonitoredChild, ParentProfile
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
    import datetime
    thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
    
    blocked_count = all_results.filter(
        decision__in=['BLOCK', 'ESCALATE', 'WARN', 'REVISE'],
        created_at__gte=thirty_days_ago
    ).count()

    base_level = 'LOW'
    if blocked_count >= 10: base_level = 'CRITICAL'
    elif blocked_count >= 5: base_level = 'HIGH'
    elif blocked_count >= 1: base_level = 'MEDIUM'

    # Get max threat actor risk
    sender_jids_all = list(all_results.exclude(sender_jid__in=child_jids).exclude(sender_jid='').values_list('sender_jid', flat=True).distinct())
    max_actor_risk = 0.0
    if sender_jids_all:
        risky = UserBehaviorProfile.objects.filter(user_jid__in=sender_jids_all).order_by('-total_blocked_messages_sent')[:10]
        for p in risky:
            if p.risk_score > 0:
                max_actor_risk = max(max_actor_risk, p.risk_score)
                
    dynamic_risk_level = base_level
    if max_actor_risk >= 0.8 and base_level in ['LOW', 'MEDIUM']: dynamic_risk_level = 'HIGH'
    elif max_actor_risk >= 0.3 and base_level == 'LOW': dynamic_risk_level = 'MEDIUM'
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
    total_blocked = today_results.filter(decision__in=['BLOCK', 'ESCALATE']).count()

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
    total_blocked_all_time = all_results.filter(decision__in=['BLOCK', 'ESCALATE']).count()
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
            "blocked": day_results.filter(decision__in=['BLOCK', 'ESCALATE']).count(),
            "warned": day_results.filter(decision__in=['WARN', 'REVISE']).count(),
            "safe": day_results.filter(decision='ALLOW').count()
        })

    # Hourly activity (today)
    from django.db.models.functions import ExtractHour
    hourly_counts = today_results.annotate(hour=ExtractHour('created_at')).values('hour', 'decision').annotate(count=Count('id'))

    hourly_data = {
        "labels": ['00h', '02h', '04h', '06h', '08h', '10h', '12h', '14h', '16h', '18h', '20h', '22h'],
        "threats": [0] * 12,
        "safe": [0] * 12
    }
    for entry in hourly_counts:
        bucket_idx = entry['hour'] // 2
        if entry['decision'] in ['BLOCK', 'ESCALATE', 'WARN', 'REVISE']:
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
        decision__in=['BLOCK', 'ESCALATE', 'REVISE', 'WARN', 'HUMAN_REVIEW']
    ).select_related().prefetch_related('alerts').order_by('-created_at')[:100]

    severity_map = {
        'WARN': 'medium',
        'REVISE': 'high',
        'BLOCK': 'high',
        'ESCALATE': 'critical',
        'HUMAN_REVIEW': 'high',
    }

    data = []
    for r in results:
        alert_obj = r.alerts.first()
        severity = alert_obj.severity if alert_obj else severity_map.get(r.decision, 'medium')
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
    """
    user = request.user

    parent_q, _, _ = _get_parent_filter(user)

    results = ModerationResult.objects.filter(parent_q).order_by('-created_at')[:20]

    severity_map = {
        'WARN': 'medium',
        'REVISE': 'high',
        'BLOCK': 'high',
        'ESCALATE': 'critical',
        'HUMAN_REVIEW': 'high',
        'ALLOW': 'none',
    }

    data = []
    for r in results:
        data.append({
            "id": str(r.id),
            "created_at": r.created_at.isoformat(),
            "raw_text": r.raw_text,
            "primary_class": r.primary_class or 'safe',
            "decision": r.decision,
            "severity": severity_map.get(r.decision, 'medium'),
            "toxicity_score": r.toxicity_score,
            "confidence_score": r.confidence_score,
            "llm_triggered": r.llm_triggered,
            "llm_explanation": r.llm_explanation,
            "language": r.language or 'unknown',
            "sender_jid": r.sender_jid,
        })
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsParentUser])
def parent_blocked_messages(request):
    """GET /api/v1/parent/blocked-messages/ - Only BLOCK or ESCALATE"""
    user = request.user

    parent_q, profile, child_jids = _get_parent_filter(user)
    
    # We want ModerationResults with BLOCK or ESCALATE
    blocked = ModerationResult.objects.filter(parent_q).filter(decision__in=['BLOCK', 'ESCALATE']).order_by('-created_at')
    
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
            "is_blocked": r.decision in ['BLOCK', 'ESCALATE'],
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
                
    # Recalculate robust risk level based on actual messages matching parent_q (even if child object is missing)
    import datetime
    thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
    
    blocked_count = all_results.filter(
        decision__in=['BLOCK', 'ESCALATE', 'WARN', 'REVISE'],
        created_at__gte=thirty_days_ago
    ).count()

    if blocked_count >= 10:
        base_level = 'CRITICAL'
    elif blocked_count >= 5:
        base_level = 'HIGH'
    elif blocked_count >= 1:
        base_level = 'MEDIUM'
    else:
        base_level = 'LOW'

    # Escalate if communicating with a highly risky actor (like someone with 1.0 risk)
    if max_actor_risk >= 0.8 and base_level in ['LOW', 'MEDIUM']:
        risk_level = 'HIGH'
    elif max_actor_risk >= 0.5 and base_level == 'LOW':
        risk_level = 'MEDIUM'
    elif max_actor_risk >= 0.3 and base_level == 'LOW':
        risk_level = 'MEDIUM'
    else:
        risk_level = base_level

    # Compute a slightly more dynamic score based on the new risk_level
    if risk_level == 'CRITICAL':
        current_score = 0.88 + min(0.12, blocked_count * 0.01)
    elif risk_level == 'HIGH':
        current_score = 0.65 + min(0.2, blocked_count * 0.02)
    elif risk_level == 'MEDIUM':
        current_score = 0.35 + min(0.25, blocked_count * 0.02)
    else:
        current_score = 0.10
        
    current_score = min(1.0, round(current_score, 2))
    
    # Generate trend data based on actual moderation history (not random)
    import datetime as _dt
    trend_data = []
    trend_labels = ["Week 1", "Week 2", "Week 3", "Week 4", "Today"]
    for i in range(4):
        week_start = timezone.now() - _dt.timedelta(weeks=4-i)
        week_end = timezone.now() - _dt.timedelta(weeks=3-i)
        week_blocked = all_results.filter(
            decision__in=['BLOCK', 'ESCALATE', 'WARN', 'REVISE'],
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

