"""
Admin-scoped API endpoints for AEGIS.

Extracted from views.py during Phase 2 audit refactoring (2026-04-21).
"""
import datetime
import logging
import random
import string

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.functions import ExtractHour
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from moderation.models import (
    ModerationResult, UserBehaviorProfile, SecurityAlert,
    MonitoredChild, AegisUser, ParentProfile
)
from moderation.permissions import IsAdminUser
from moderation.services.formatters import get_severity, SEVERITY_MAP, format_phone_number
from moderation.services.risk_calculator import calculate_risk_level
from moderation.views.webhook import get_avg_latency

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def alert_list(request):
    """GET /api/v1/alerts/ - History for the Admin Dashboard (all harmful decisions)"""
    results = ModerationResult.objects.filter(
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
@permission_classes([IsAuthenticated, IsAdminUser])
def review_queue_list(request):
    """
    GET /api/v1/review/
    Returns items needing human review:
    - HUMAN_REVIEW decisions (LLM was too uncertain)
    - REVISE decisions not yet overridden
    - Any message manually flagged_for_review (even ALLOW ones)
    Excludes already human-reviewed items.
    """
    items = ModerationResult.objects.filter(
        human_reviewed=False
    ).filter(
        Q(decision__in=['HUMAN_REVIEW', 'REVISE']) | Q(flagged_for_review=True)
    ).select_related().prefetch_related('alerts').order_by('-created_at')[:200]

    data = []
    for r in items:
        reason = 'HUMAN_REVIEW' if r.decision == 'HUMAN_REVIEW' else (
            'FLAGGED_BY_ADMIN' if r.flagged_for_review else 'SCORE_AMBIGU'
        )
        data.append({
            "id": str(r.id),
            "raw_text": r.raw_text,
            "preview": r.raw_text[:100] + ('...' if len(r.raw_text) > 100 else ''),
            "primary_class": r.primary_class or 'safe',
            "decision": r.decision,
            "toxicity_score": r.toxicity_score,
            "confidence_score": r.confidence_score or 0.0,
            "llm_triggered": r.llm_triggered,
            "llm_explanation": r.llm_explanation,
            "language": r.language or 'unknown',
            "sender_jid": r.sender_jid,
            "contact_number": r.sender_jid.split('@')[0],
            "submitted_at": r.created_at.isoformat(),
            "queue_reason": reason,
            "flagged_for_review": r.flagged_for_review,
        })
    return Response(data)


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def human_override(request, moderation_id):
    """
    POST /api/v1/review/<id>/override/
    Human admin overrides AI decision AND class label.
    Body: { "decision": "BLOCK", "label": "sexual_harassment", "note": "..." }
    Also works for ALLOW messages flagged as misclassified.
    """
    try:
        body = request.data
        new_decision = body.get("decision", "").upper()
        new_label = body.get("label", "").lower()
        note = body.get("note", "")

        if not new_decision:
            return Response({"status": "error", "reason": "decision is required"}, status=400)

        mod = ModerationResult.objects.get(id=moderation_id)

        # Concurrency guard: prevent overlapping overrides
        if mod.human_reviewed:
            return Response({
                "status": "error",
                "reason": "Already reviewed by another admin",
                "existing_decision": mod.human_decision
            }, status=409)

        # Golden Dataset: Preserve original AI predictions BEFORE overwriting
        mod.original_ai_decision = mod.decision
        mod.original_ai_label = mod.primary_class

        mod.human_reviewed = True
        mod.human_decision = new_decision
        mod.human_label = new_label or mod.primary_class
        mod.human_note = note
        mod.human_reviewed_at = timezone.now()
        mod.flagged_for_review = False  # Mark resolved

        # Apply the override to the live decision and class too
        mod.decision = new_decision
        if new_label:
            mod.primary_class = new_label

        mod.save()
        return Response({
            "status": "success",
            "new_decision": mod.decision,
            "new_label": mod.primary_class,
            "human_reviewed": True,
            "original_ai_decision": mod.original_ai_decision,
            "original_ai_label": mod.original_ai_label,
        })
    except ModerationResult.DoesNotExist:
        return Response({"status": "error", "reason": "Not found"}, status=404)
    except Exception as e:
        return Response({"status": "error", "reason": str(e)}, status=400)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_user_detail(request, user_id):
    """DELETE /api/v1/admin/users/<id>/ - Admin deletes a parent account"""
    try:
        user = AegisUser.objects.get(id=user_id, role=AegisUser.Role.PARENT)
        user.delete()
        return Response({"status": "success"}, status=200)
    except AegisUser.DoesNotExist:
        return Response({"error": "User not found."}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=400)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_user_list(request):
    """GET /api/v1/admin/users/ - List parents for the admin dashboard
       POST /api/v1/admin/users/ - Admin creates a new parent user (child optional)"""
    
    if request.method == 'POST':
        from django.contrib.auth.hashers import make_password
        import string, random
        data = request.data
        
        # Validation
        email = data.get('email', '').strip()
        full_name = data.get('full_name', '').strip()
        phone = data.get('phone', '').strip()
        
        if not email or not full_name or not phone:
            return Response({"error": "Full name, email, and phone are required."}, status=400)

        # 1. Check if email already exists
        if AegisUser.objects.filter(email=email).exists():
            return Response({"error": "A user with this email already exists."}, status=400)
            
        names = full_name.split(' ', 1)
        first_name = names[0]
        last_name = names[1] if len(names) > 1 else ''
        
        # 2. Create the User. Role automatically sets PARENT
        temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        
        user = AegisUser.objects.create(
            username=email,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone_number=data.get('phone', ''),
            role=AegisUser.Role.PARENT,
            password=make_password(temp_password)
        )
        
        # The ParentProfile is automatically created by a Django Signal
        profile = user.parent_profile
        
        # 3. Create the child if provided (optional)
        if data.get('child_identifier') and data.get('child_whatsapp'):
            from moderation.models import MonitoredChild
            MonitoredChild.objects.create(
                parent=profile,
                full_name=data.get('child_identifier'),
                whatsapp_jid=f"{data.get('child_whatsapp').strip('+').replace(' ', '')}@s.whatsapp.net",
                whatsapp_display_number=data.get('child_whatsapp')
            )
            
        return Response({"status": "success", "user_id": user.id}, status=201)

    parents = AegisUser.objects.filter(role=AegisUser.Role.PARENT, is_superuser=False).select_related('parent_profile')
    
    data = []
    for user in parents:
        profile = getattr(user, 'parent_profile', None)
        child_data = None
        
        if profile:
            child = profile.children.filter(is_monitored=True).first()
            if child:
                child_data = {
                    "identifier": child.full_name,
                    "whatsapp_number": child.whatsapp_display_number or child.whatsapp_jid,
                    "risk_level": child.get_risk_level().lower(),
                    "whatsapp_connected": profile.evolution_connected
                }
            elif profile.evolution_connected or profile.evolution_instance_name:
                # Calculate real risk level based on the instance's history
                from django.utils import timezone
                import datetime
                instance_risk = 'low'
                if profile.evolution_instance_name:
                    thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
                    blocked_count = ModerationResult.objects.filter(
                        instance_name=profile.evolution_instance_name,
                        decision__in=['BLOCK', 'ESCALATE', 'WARN', 'REVISE'],
                        created_at__gte=thirty_days_ago
                    ).count()
                    if blocked_count >= 10:
                        instance_risk = 'critical'
                    elif blocked_count >= 5:
                        instance_risk = 'high'
                    elif blocked_count >= 1:
                        instance_risk = 'medium'

                wa_number = "Setup Pending"
                wa_identifier = f"Device: {profile.evolution_instance_name}"
                
                try:
                    from moderation.evolution_api import get_instance_details
                    evo_details = get_instance_details(profile.evolution_instance_name)
                    if evo_details and evo_details.get('ownerJid'):
                        raw_jid = evo_details.get('ownerJid', '').split('@')[0]
                        if raw_jid:
                            wa_number = f"+{raw_jid}"
                        p_name = evo_details.get('profileName')
                        if p_name:
                            wa_identifier = f"{p_name} ({profile.evolution_instance_name})"
                except Exception:
                    pass

                child_data = {
                    "identifier": wa_identifier,
                    "whatsapp_number": wa_number,
                    "risk_level": instance_risk,
                    "whatsapp_connected": True
                }
                
        data.append({
            "id": str(user.id),
            "full_name": user.get_full_name() or user.username,
            "email": user.email,
            "phone": user.phone_number,
            "status": "active",
            "monitoring_active": True if child_data else False,
            "alert_threshold": profile.alert_threshold if profile else 0.75,
            "sms_notifications": profile.receive_sms_alerts if profile else True,
            "email_notifications": profile.receive_email_alerts if profile else True,
            "linked_child": child_data,
            "joined_at": user.created_at.strftime('%b %d, %Y'),
            "last_login": user.last_login.strftime('%b %d, %Y') if user.last_login else "Never"
        })
        
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_conversations(request):
    """GET /api/v1/admin/conversations/?limit=500"""
    limit = min(int(request.query_params.get('limit', 500)), 2000)
    all_results = ModerationResult.objects.all().order_by('-created_at')[:limit]
    
    contacts_map = {}
    messages_map = {}
    
    # We group by (instance_name, sender_jid) to unique conversations
    # OR if sender is the child (is_from_me), we need to know who they were talking to.
    # Actually, Evolution API gives the same remoteJid for both incoming and outgoing in a chat.
    # So (instance_name, remoteJid) is the conversation ID.
    
    sender_jids = list(all_results.values_list('sender_jid', flat=True).distinct())
    profiles = UserBehaviorProfile.objects.filter(user_jid__in=sender_jids)
    profile_dict = {p.user_jid: p for p in profiles}
    
    for r in all_results:
        jid = r.sender_jid
        if not jid: continue
        
        # ID is unique per (Child Device, Remote Contact)
        conv_id = f"{r.instance_name}_{jid}"
        
        if conv_id not in contacts_map:
            prof = profile_dict.get(jid)
            
            # Find logic for parent and child names
            instance_name = r.instance_name
            parent_name = "Unknown Parent"
            child_name = "Unknown Child"
            
            parent_profile = ParentProfile.objects.filter(evolution_instance_name=instance_name).first()
            if parent_profile:
                parent_name = parent_profile.user.get_full_name() or parent_profile.user.username
                child = parent_profile.children.first()
                if child:
                    child_name = child.full_name
                else:
                    child_name = f"Device: {instance_name}"
            
            # Base fallback name
            raw_n = jid.split('@')[0]
            if jid.endswith('@g.us'):
                display_name = f"Group ({raw_n[-4:]})"
            elif jid.endswith('@s.whatsapp.net'):
                display_name = f"+{raw_n}"
            else:
                display_name = jid
                
            # If the most recent message is from the remote contact, use their name
            has_real_name = False
            if r.sender_name and not r.is_from_me:
                display_name = r.sender_name
                has_real_name = True
                    
            contacts_map[conv_id] = {
                "id": conv_id,
                "raw_jid": jid,
                "name": display_name,
                "number": f"+{jid.split('@')[0]}" if jid.endswith('@s.whatsapp.net') else f"Group ({jid.split('@')[0][-4:]})",
                "child_name": child_name,
                "child_id": "child-" + instance_name,
                "parent_name": parent_name,
                "sender_name": display_name,
                "has_real_name": has_real_name,
                "sender_risk_score": prof.risk_score if prof else 0.1,
                "risk_level": prof.risk_level.lower() if prof else "low",
                "plateforme": "WhatsApp",
                "is_first_contact": False,
                "last_message": r.raw_text[:50],
                "last_message_at": r.created_at.strftime('%H:%M'),
                "total_messages": 0,
                "blocked_count": 0,
                "unread": 0
            }
            messages_map[conv_id] = []
            
        # Update name if we find the remote contact's name in an older message
        if r.sender_name and not r.is_from_me and not contacts_map[conv_id].get("has_real_name"):
            contacts_map[conv_id]["name"] = r.sender_name
            contacts_map[conv_id]["sender_name"] = r.sender_name
            contacts_map[conv_id]["has_real_name"] = True
            
        contacts_map[conv_id]["total_messages"] += 1
        is_blocked = r.decision in ['BLOCK', 'ESCALATE']
        if is_blocked:
            contacts_map[conv_id]["blocked_count"] += 1
            
        messages_map[conv_id].append({
            "id": str(r.id),
            "content_preview": r.raw_text,
            "direction": 'outgoing' if r.is_from_me else 'incoming', 
            "is_blocked": is_blocked,
            "language": r.language,
            "sent_at": r.created_at.strftime('%H:%M'),
            "decision": r.decision,
            "toxicity_score": r.toxicity_score,
            "category": r.primary_class,
            "llm_triggered": r.llm_triggered
        })

    for jid in messages_map:
        messages_map[jid].reverse()

    return Response({
        "contacts": list(contacts_map.values()),
        "messages": messages_map
    })


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def flag_for_review(request, moderation_id):
    """
    POST /api/v1/review/<id>/flag/
    Admin flags ANY message (including ALLOW ones) for human review.
    """
    try:
        mod = ModerationResult.objects.get(id=moderation_id)
        mod.flagged_for_review = True
        mod.save()
        return Response({"status": "success", "flagged": True})
    except ModerationResult.DoesNotExist:
        return Response({"status": "error", "reason": "Not found"}, status=404)
    except Exception as e:
        return Response({"status": "error", "reason": str(e)}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def dashboard_stats(request):
    """GET /api/v1/stats/dashboard/ - Live stats from PostgreSQL"""
    today = timezone.now().date()
    
    # 1. Grab all moderation results for today
    today_results = ModerationResult.objects.filter(created_at__date=today)
    
    # 2. Count the core metrics
    total_messages = today_results.count()
    total_blocked = today_results.filter(decision__in=['BLOCK', 'ESCALATE']).count()
    
    # 3. Alerts are any message that isn't 'ALLOW'
    total_alerts = SecurityAlert.objects.filter(sent_at__date=today).count()
    
    # 4. Agent 3 Interventions (LLM triggered)
    llm_interventions = ModerationResult.objects.filter(llm_triggered=True, created_at__date=today).count()
    
    # 5. At-Risk Children (Agent 4 Behavior)
    risky_profiles = UserBehaviorProfile.objects.order_by('-total_blocked_messages_sent')[:5]
    at_risk_users = [
        {
            "id": str(p.id),
            "whatsapp": p.user_jid,
            "risk_score": p.risk_score,
            "risk_level": p.risk_level,
            "blocked_total": p.total_blocked_messages_sent,
            "sent_total": p.total_messages_sent
        }
        for p in risky_profiles
    ]
    
    # 6. We group by primary_class (Fixed from decision)
    category_counts = today_results.exclude(primary_class='safe').values('primary_class').annotate(count=Count('id'))
    category_breakdown = {item['primary_class']: item['count'] for item in category_counts}

    # 7. Weekly Activity (Bar Chart - last 7 days)
    seven_days_ago = today - timezone.timedelta(days=6)
    recent_results = ModerationResult.objects.filter(created_at__date__gte=seven_days_ago)
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

    # 8. Hourly Activity (Today)
    from django.db.models.functions import ExtractHour
    hourly_counts = today_results.annotate(hour=ExtractHour('created_at')).values('hour', 'decision').annotate(count=Count('id'))
    
    hourly_data = {
        "labels": ['00h', '02h', '04h', '06h', '08h', '10h', '12h', '14h', '16h', '18h', '20h', '22h'],
        "threats": [0] * 12,
        "safe": [0] * 12
    }
    
    for entry in hourly_counts:
        hour = entry['hour']
        bucket_idx = hour // 2
        if entry['decision'] in ['BLOCK', 'ESCALATE', 'WARN', 'REVISE']:
            hourly_data["threats"][bucket_idx] += entry['count']
        elif entry['decision'] == 'ALLOW':
            hourly_data["safe"][bucket_idx] += entry['count']

    # 9. Language Distribution (Live from DB)
    lang_counts = ModerationResult.objects.exclude(
        language__isnull=True
    ).exclude(
        language='other'
    ).exclude(
        language='error'
    ).values('language').annotate(count=Count('id')).order_by('-count')

    lang_labels = []
    lang_data = []
    
    for item in lang_counts:
        lang = str(item['language']).upper()
        if lang:  # Ensure it's not empty string
            lang_labels.append(lang)
            lang_data.append(item['count'])
            
    # Fallback to empty chart if no language labels exist yet
    language_distribution = {
        "labels": lang_labels if lang_labels else ['UNKNOWN'],
        "data": lang_data if lang_data else [1]
    }

    # Send the "Package" back to Angular
    return Response({
        "stats": {
            "total_messages_today": total_messages,
            "total_alerts_today": total_alerts,
            "total_blocked_today": total_blocked,
            "llm_interventions": llm_interventions,
            "avg_latency_ms": get_avg_latency('agent_1', 42) + get_avg_latency('agent_2', 287) + get_avg_latency('agent_5', 12),
            "latencies": {
                "agent_1": get_avg_latency('agent_1', 42),
                "agent_2": get_avg_latency('agent_2', 287),
                "agent_3": get_avg_latency('agent_3', 1240),
                "agent_4": get_avg_latency('agent_4', 95),
                "agent_5": get_avg_latency('agent_5', 12)
            }
        },
        "category_breakdown": category_breakdown,
        "weekly_activity": weekly_data,
        "at_risk_users": at_risk_users,
        "hourly_activity": hourly_data,
        "language_distribution": language_distribution
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def llm_audit_list(request):
    """GET /api/v1/audits/llm/ - History of LLM interventions"""
    audits = ModerationResult.objects.filter(llm_triggered=True).order_by('-created_at')[:50]
    
    data = []
    for a in audits:
        data.append({
            "id": str(a.id),
            "preview": a.raw_text[:60] + "..." if len(a.raw_text) > 60 else a.raw_text,
            "full_preview": a.raw_text,
            "tentative_label": a.primary_class or "safe",
            "queue_reason": "SCORE_AMBIGU" if a.confidence_score and a.confidence_score < 0.75 else "LANGUE_NON_IDENTIFIABLE",
            "confidence_score": a.confidence_score or 0.0,
            "toxicity_score": a.toxicity_score,
            "behavioral_risk_score": a.behavioral_risk_score if a.behavioral_risk_score else 0.0,
            "final_score": a.toxicity_score,
            "language": a.language or 'unknown',
            "agents_used": ["Agent 1", "Agent 2", "Agent 3"],
            "llm_explanation": a.llm_explanation,
            "submitted_at": a.created_at.isoformat(),
            "contact_number": a.sender_jid.split('@')[0],
            "decision": a.decision,
            "child": {
                "id": a.sender_jid,
                "name": a.sender_name or a.sender_jid.split('@')[0],
                "risk_level": "medium",
                "risk_score": a.behavioral_risk_score if a.behavioral_risk_score else 0.0
            },
            "previous_messages": []
        })
    return Response(data)

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def override_llm_decision(request, moderation_id):
    """POST /api/v1/audits/llm/<id>/override/ - Admin overriding LLM"""
    try:
        body = request.data  # Use DRF parser (not json.loads)
        new_decision = body.get("decision", "ALLOW")
        
        mod = ModerationResult.objects.get(id=moderation_id)
        mod.original_ai_decision = mod.decision  # Preserve original
        mod.decision = new_decision
        mod.save()
        return Response({"status": "success", "new_decision": mod.decision})
    except Exception as e:
        return Response({"status": "error", "reason": str(e)}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def activity_feed(request):
    """
    GET /api/v1/activity/
    Returns the last 20 moderation events (ALL decisions including ALLOW).
    Used to seed the dashboard activity feed on page refresh.
    """
    results = ModerationResult.objects.all().order_by('-created_at')[:20]
    
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
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_risk_profiles(request):
    """GET /api/v1/admin/risk-profiles/"""
    
    # 1. Build Children Profiles
    children_profiles = []
    
    # Actually, we can get devices connected via parent profile or MonitoredChild directly
    children = MonitoredChild.objects.all()
    
    # Also fetch parent profiles connected but without a registered child
    parents_with_devices = ParentProfile.objects.exclude(evolution_instance_name__isnull=True).exclude(evolution_instance_name='')
    
    # We will build a map of instance_name -> child info
    instances = {}
    
    for c in children:
        if c.parent and c.parent.evolution_instance_name:
            instances[c.parent.evolution_instance_name] = c
            
    for p in parents_with_devices:
        if p.evolution_instance_name not in instances:
            instances[p.evolution_instance_name] = p
            
    # Calculate stats per instance
    import datetime
    thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
    
    for instance_name, entity in instances.items():
        results = ModerationResult.objects.filter(instance_name=instance_name)
        
        is_child = isinstance(entity, MonitoredChild)
        
        c_id = f"c_{instance_name}"
        identifier = entity.full_name if is_child else f"Device: {instance_name}"
        wa_number = entity.whatsapp_display_number if is_child else ""
        parent_id = str(entity.parent.user.id) if is_child else str(entity.user.id)
        
        base_risk = 'LOW'
        blocked_count = results.filter(decision__in=['BLOCK', 'ESCALATE', 'WARN', 'REVISE']).count()
        if blocked_count >= 10: base_risk = 'CRITICAL'
        elif blocked_count >= 5: base_risk = 'HIGH'
        elif blocked_count >= 1: base_risk = 'MEDIUM'
        
        risk_score = 0.1
        if base_risk == 'CRITICAL': risk_score = 0.85
        elif base_risk == 'HIGH': risk_score = 0.65
        elif base_risk == 'MEDIUM': risk_score = 0.35
        
        children_profiles.append({
            "id": c_id,
            "identifier": identifier,
            "whatsapp_number": wa_number,
            "parent_user_id": parent_id,
            "date_naissance": "2010-01-01",
            "nom_ecole": entity.school_name if is_child else "",
            "niveau_scolaire": entity.school_level if is_child else "",
            "victim_risk_level": base_risk.lower(),
            "victim_risk_score": risk_score,
            "total_incoming": results.exclude(is_from_me=True).count(),
            "total_blocked": blocked_count,
            "total_messages_bloques_envoyes": results.filter(is_from_me=True, decision__in=['BLOCK', 'ESCALATE']).count(),
            "activite_nocturne": 0.1,
            "unique_harassers": len(list(results.exclude(is_from_me=True).values_list('sender_jid', flat=True).distinct())),
            "escalation_count": results.filter(decision='ESCALATE').count(),
            "most_common_category": "threat" if blocked_count > 0 else "N/A",
            "risk_trend": [round(risk_score, 2)] * 7,  # Flat trend (no BehavioralSnapshot data yet)
            "snapshots": [],
            "category_breakdown": {
                "verbal": 0, "threat": blocked_count, "sexual": 0, "discrimination": 0
            },
            "last_activity": timezone.now().isoformat(),
            "monitored_since": timezone.now().isoformat()
        })
        
    # 2. Build Contacts Profiles
    profiles = UserBehaviorProfile.objects.all().order_by('-total_blocked_messages_sent')[:50]
    contact_profiles = []
    
    for prof in profiles:
        # Find which child instance they talked to
        # Also let's extract their push name from their recent ModerationResults
        results = ModerationResult.objects.filter(sender_jid=prof.user_jid)
        instances_talked_to = list(results.values_list('instance_name', flat=True).distinct())
        
        # Try to find recent sender_name
        recent_name_result = results.exclude(sender_name__isnull=True).exclude(sender_name='').order_by('-created_at').first()
        push_name = recent_name_result.sender_name if recent_name_result else ""
        
        # Format the numbers nicely
        raw_num = prof.user_jid.split('@')[0]
        if raw_num.isdigit():
            formatted_number = f"+{raw_num[:3]} {raw_num[3:]}" if len(raw_num) > 4 else f"+{raw_num}"
        else:
            formatted_number = raw_num # For groups or weird system jids
            
        display_name = f"{push_name} ({formatted_number})" if push_name and push_name != raw_num else formatted_number
        if not display_name.strip():
            display_name = formatted_number
            
        # Calculate dominant category dynamically
        cat_counts = results.exclude(primary_class='safe').exclude(primary_class__isnull=True).values('primary_class').annotate(count=Count('id')).order_by('-count')
        dominant_cat = cat_counts.first()['primary_class'] if cat_counts else "N/A"
        
        related_child_ids = [f"c_{inst}" for inst in instances_talked_to]
        
        contact_profiles.append({
            "id": str(prof.id),
            "raw_jid": prof.user_jid,
            "whatsapp_number": display_name,
            "threat_level": prof.risk_level.lower(),
            "threat_score": prof.risk_score,
            "total_sent": prof.total_messages_sent,
            "total_blocked": prof.total_blocked_messages_sent,
            "block_ratio": prof.block_ratio,
            "escalation_count": prof.escalation_count,
            "night_activity_ratio": prof.night_activity_ratio,
            "activite_nocturne": prof.night_activity_ratio,
            "avg_toxicity": prof.average_toxicity_score,
            "repeated_targeting": prof.unique_targets_count > 1,
            "targets_count": prof.unique_targets_count,
            "nombre_cibles_differentes": len(related_child_ids),
            "other_monitored_children_count": len(related_child_ids) - 1 if len(related_child_ids) > 0 else 0,
            "dominant_category": dominant_cat,
            "toxicity_trend": [round(prof.risk_score, 2)] * 7,  # Flat trend (no BehavioralSnapshot data yet)
            "last_seen": timezone.now().isoformat(),
            "related_child_ids": related_child_ids
        })

    return Response({
        "children": children_profiles,
        "contacts": contact_profiles
    })


