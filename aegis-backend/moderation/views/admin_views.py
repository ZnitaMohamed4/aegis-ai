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
    queryset = ModerationResult.objects.filter(
        decision__in=['BLOCK', 'ESCALATE', 'REVISE', 'WARN', 'HUMAN_REVIEW']
    ).select_related().prefetch_related('alerts').order_by('-created_at')

    sender_jid = request.query_params.get('sender_jid')
    if sender_jid:
        queryset = queryset.filter(sender_jid=sender_jid)

    results = queryset[:100]

    data = []
    for r in results:
        alert_obj = r.alerts.first()
        severity = get_severity(r.decision, alert_obj)
        is_resolved = alert_obj.is_resolved if alert_obj else False
        
        formatted_contact = format_phone_number(r.sender_jid)
        if not formatted_contact:
            raw_jid = r.sender_jid.split('@')[0] if r.sender_jid else 'Unknown'
            formatted_contact = f"+{raw_jid}" if r.sender_jid and '@s.whatsapp.net' in r.sender_jid else raw_jid

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
            "contact_number": formatted_contact,
            "human_reviewed": r.human_reviewed,
            "human_decision": r.human_decision,
            "human_label": r.human_label,
            "is_resolved": is_resolved,
        })
    return Response(data)

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def resolve_alert(request, alert_id):
    """POST /api/v1/alerts/<id>/resolve/ - Mark an alert as resolved"""
    try:
        mod = ModerationResult.objects.get(id=alert_id)
        alert_obj = mod.alerts.first()
        if alert_obj:
            alert_obj.resolve()
        return Response({"status": "success", "resolved": True})
    except ModerationResult.DoesNotExist:
        return Response({"status": "error", "reason": "Not found"}, status=404)
    except Exception as e:
        return Response({"status": "error", "reason": str(e)}, status=400)


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
        mod.reviewed_by = request.user
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


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def review_queue_stats(request):
    """
    GET /api/v1/review/stats/
    Returns statistics for human overrides done today.
    """
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    overrides_today = ModerationResult.objects.filter(
        human_reviewed=True,
        human_reviewed_at__gte=today_start
    )

    resolved_count = overrides_today.count()
    blocked_count = overrides_today.filter(human_decision='BLOCK').count()
    warned_count = overrides_today.filter(human_decision='WARN').count()
    allowed_count = overrides_today.filter(human_decision='ALLOW').count()

    return Response({
        "resolvedCount": resolved_count,
        "blockedCount": blocked_count,
        "warnedCount": warned_count,
        "allowedCount": allowed_count,
    })


@api_view(['DELETE', 'PUT'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_user_detail(request, user_id):
    """DELETE /api/v1/admin/users/<id>/ - Admin deletes a parent account
       PUT /api/v1/admin/users/<id>/ - Admin updates parent/child status"""
    try:
        user = AegisUser.objects.get(id=user_id, role=AegisUser.Role.PARENT)
        
        if request.method == 'PUT':
            data = request.data
            updated = False
            
            # 1. Handle user status (is_active)
            if 'is_active' in data:
                user.is_active = bool(data['is_active'])
                user.save(update_fields=['is_active'])
                updated = True
                
            # 2. Handle child monitoring status (is_monitored)
            if 'is_monitored' in data:
                profile = getattr(user, 'parent_profile', None)
                if profile:
                    child = profile.children.first()
                    if child:
                        child.is_monitored = bool(data['is_monitored'])
                        child.save(update_fields=['is_monitored'])
                        updated = True
                        
            return Response({"status": "success", "updated": updated}, status=200)

        # Handle DELETE
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
            child = profile.children.first()
            if child:
                child_data = {
                    "identifier": child.full_name,
                    "whatsapp_number": child.whatsapp_display_number or child.whatsapp_jid,
                    "risk_level": child.get_risk_level().lower(),
                    "whatsapp_connected": profile.evolution_connected,
                    "is_monitored": child.is_monitored
                }
            elif profile.evolution_connected or profile.evolution_instance_name:
                instance_risk = 'low'
                if profile.evolution_instance_name:
                    thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
                    blocked_count = ModerationResult.objects.filter(
                        instance_name=profile.evolution_instance_name,
                        decision__in=['BLOCK', 'ESCALATE', 'WARN', 'REVISE'],
                        created_at__gte=thirty_days_ago
                    ).count()
                    risk_level, _ = calculate_risk_level(blocked_count)
                    instance_risk = risk_level.lower()

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
            "status": "active" if user.is_active else "inactive",
            "monitoring_active": child_data.get("is_monitored", False) if child_data else False,
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
    
    queryset = ModerationResult.objects.all()
    child_param = request.query_params.get('child')
    if child_param:
        instance_name = child_param.replace('child-', '') if child_param.startswith('child-') else child_param
        queryset = queryset.filter(instance_name=instance_name)
        
    all_results = queryset.order_by('-created_at')[:limit]
    
    contacts_map = {}
    messages_map = {}
    jid_to_conv_id_map = {}
    
    # We group by (instance_name, sender_jid) to unique conversations
    # OR if sender is the child (is_from_me), we need to know who they were talking to.
    
    sender_jids = list(set([r.sender_jid for r in all_results if r.sender_jid]))
    profiles = UserBehaviorProfile.objects.filter(user_jid__in=sender_jids)
    profile_dict = {p.user_jid: p for p in profiles}
    
    for r in all_results:
        jid = r.sender_jid
        if not jid: continue
        
        global_jid_key = f"{r.instance_name}_{jid}"
        conv_id = None
        
        if global_jid_key in jid_to_conv_id_map:
            conv_id = jid_to_conv_id_map[global_jid_key]
        else:
            if r.sender_name and not r.is_from_me and not jid.endswith('@g.us'):
                for existing_key, existing_conv_id in jid_to_conv_id_map.items():
                    c_data = contacts_map.get(existing_conv_id)
                    if c_data and c_data['child_id'] == f"child-{r.instance_name}" and \
                       c_data['has_real_name'] and c_data['name'] == r.sender_name:
                        conv_id = existing_conv_id
                        break
            
            if not conv_id:
                conv_id = global_jid_key
                
            jid_to_conv_id_map[global_jid_key] = conv_id
            
        if not jid or jid.endswith('@lid'):
            continue
            
        instance_name = r.instance_name
        
        if conv_id not in contacts_map:
            prof = profile_dict.get(jid)
            
            # Find logic for parent and child names
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
                display_name = "WhatsApp Group"
                number_val = f"ID: {raw_n[-4:]}"
            elif jid.endswith('@s.whatsapp.net'):
                display_name = f"+{raw_n}"
                number_val = f"+{raw_n}"
            else:
                display_name = jid
                number_val = "Hidden Contact"
                
            # If the most recent message is from the remote contact, use their name
            has_real_name = False
            if r.sender_name and not r.is_from_me:
                if not jid.endswith('@g.us'):
                    # Truncate long pushnames (like 'Moussa Znita0668896664')
                    display_name = r.sender_name
                    if len(display_name) > 18:
                        display_name = display_name[:15] + "..."
                    has_real_name = True
                    
            # Compute risk score: use profile if available, otherwise derive from message history
            if prof:
                contact_risk_score = prof.risk_score
                contact_risk_level = prof.risk_level.lower()
            else:
                # Fallback: compute from this contact's blocked ratio across all their messages
                contact_results = ModerationResult.objects.filter(sender_jid=jid)
                contact_total = contact_results.count()
                contact_blocked = contact_results.filter(decision__in=['BLOCK', 'ESCALATE', 'WARN', 'REVISE']).count()
                if contact_total > 0:
                    contact_risk_score = round(min(contact_blocked / max(contact_total, 1), 1.0), 2)
                else:
                    contact_risk_score = 0.0
                if contact_risk_score >= 0.5: contact_risk_level = 'critical'
                elif contact_risk_score >= 0.25: contact_risk_level = 'high'
                elif contact_risk_score >= 0.05: contact_risk_level = 'medium'
                else: contact_risk_level = 'low'
                    
            contacts_map[conv_id] = {
                "id": conv_id,
                "raw_jid": jid,
                "name": display_name,
                "number": number_val,
                "child_name": child_name,
                "child_id": "child-" + instance_name,
                "parent_name": parent_name,
                "sender_name": display_name,
                "has_real_name": has_real_name,
                "sender_risk_score": contact_risk_score,
                "risk_level": contact_risk_level,
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
            if not jid.endswith('@g.us'):
                contacts_map[conv_id]["name"] = r.sender_name
                contacts_map[conv_id]["sender_name"] = r.sender_name
                contacts_map[conv_id]["has_real_name"] = True
                
        # Upgrade number if we get a real whatsapp number instead of @lid
        if jid.endswith('@s.whatsapp.net') and contacts_map[conv_id]["raw_jid"].endswith('@lid'):
            contacts_map[conv_id]["raw_jid"] = jid
            contacts_map[conv_id]["number"] = f"+{jid.split('@')[0]}"
            
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

    # 10. Check Evolution API global status
    evolution_api_online = False
    try:
        import requests
        import os
        api_url = os.getenv('EVOLUTION_API_URL', 'http://localhost:5002')
        # Fast 1.5s timeout ping to check if container is responding
        requests.get(api_url, timeout=1.5)
        evolution_api_online = True
    except Exception:
        evolution_api_online = False

    # Send the "Package" back to Angular
    return Response({
        "stats": {
            "total_messages_today": total_messages,
            "total_alerts_today": total_alerts,
            "total_blocked_today": total_blocked,
            "llm_interventions": llm_interventions,
            "avg_latency_ms": get_avg_latency('agent_1', 42) + get_avg_latency('agent_2', 287) + get_avg_latency('agent_5', 12),
            "evolution_api_online": evolution_api_online,
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
    
    data = []
    for r in results:
        data.append({
            "id": str(r.id),
            "created_at": r.created_at.isoformat(),
            "raw_text": r.raw_text,
            "primary_class": r.primary_class or 'safe',
            "decision": r.decision,
            "severity": SEVERITY_MAP.get(r.decision, 'medium'),
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
    from moderation.models import BehavioralSnapshot
    
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
        
        total_count = results.count()
        blocked_count = results.filter(decision__in=['BLOCK', 'ESCALATE', 'WARN', 'REVISE']).count()
        base_risk, _ = calculate_risk_level(blocked_count)
        
        # Continuous risk score from blocked ratio (not fixed tiers)
        if total_count > 0:
            risk_score = round(min(blocked_count / max(total_count, 1) * 2.5, 1.0), 2)
        else:
            risk_score = 0.0
        
        # Night activity: messages sent between 22:00 and 06:00
        from django.db.models.functions import ExtractHour
        night_results = results.annotate(hour=ExtractHour('created_at')).filter(
            Q(hour__gte=22) | Q(hour__lt=6)
        ).count()
        activite_nocturne = round(night_results / max(total_count, 1), 2)
        
        # Real category breakdown from ModerationResult.primary_class
        cat_counts = results.exclude(primary_class='safe').exclude(primary_class__isnull=True).exclude(primary_class='').values('primary_class').annotate(count=Count('id'))
        category_breakdown = {}
        for cc in cat_counts:
            category_breakdown[cc['primary_class']] = cc['count']
        if not category_breakdown:
            category_breakdown = {"safe": total_count}
        
        # Compute most common category
        most_common_cat = max(category_breakdown, key=category_breakdown.get) if category_breakdown else "N/A"
        
        # Build real risk_trend from incoming contact snapshots
        incoming_jids = list(results.exclude(is_from_me=True).values_list('sender_jid', flat=True).distinct())
        child_snapshots = BehavioralSnapshot.objects.filter(
            profile__user_jid__in=incoming_jids,
            date_snapshot__gte=thirty_days_ago
        ).order_by('date_snapshot').values_list('date_snapshot', 'risk_score_snapshot')
        
        daily_risks = {}
        for d, score in child_snapshots:
            daily_risks[d] = max(daily_risks.get(d, 0), score)
        risk_trend = list(daily_risks.values())[-14:] if daily_risks else [round(risk_score, 2)] * 7
        
        # Populate snapshots from BehavioralSnapshot
        snapshot_list = []
        for snap_date, snap_score in child_snapshots:
            snapshot_list.append({
                "date_snapshot": snap_date.strftime('%b %d'),
                "score_risque_snapshot": round(snap_score, 2),
                "alert_id": None
            })
        # Keep last 14 entries
        snapshot_list = snapshot_list[-14:]
        
        # Real dates
        date_naissance = entity.date_of_birth.isoformat() if is_child and entity.date_of_birth else ""
        
        # Real last_activity from latest ModerationResult
        latest_result = results.order_by('-created_at').first()
        last_activity = latest_result.created_at.isoformat() if latest_result else ""
        
        # Real monitored_since
        if is_child:
            monitored_since = entity.linked_at.isoformat() if entity.linked_at else ""
        else:
            monitored_since = entity.created_at.isoformat() if hasattr(entity, 'created_at') else ""
        
        children_profiles.append({
            "id": c_id,
            "identifier": identifier,
            "whatsapp_number": wa_number,
            "parent_user_id": parent_id,
            "date_naissance": date_naissance,
            "nom_ecole": entity.school_name if is_child else "",
            "niveau_scolaire": entity.school_level if is_child else "",
            "victim_risk_level": base_risk.lower(),
            "victim_risk_score": risk_score,
            "total_incoming": results.exclude(is_from_me=True).count(),
            "total_blocked": blocked_count,
            "total_messages_bloques_envoyes": results.filter(is_from_me=True, decision__in=['BLOCK', 'ESCALATE']).count(),
            "activite_nocturne": activite_nocturne,
            "unique_harassers": len(incoming_jids),
            "escalation_count": results.filter(decision='ESCALATE').count(),
            "most_common_category": most_common_cat,
            "risk_trend": risk_trend,
            "snapshots": snapshot_list,
            "category_breakdown": category_breakdown,
            "last_activity": last_activity,
            "monitored_since": monitored_since
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
        
        # Map instance_names to REAL registered MonitoredChild records
        real_children = MonitoredChild.objects.filter(
            parent__evolution_instance_name__in=instances_talked_to
        )
        related_child_ids = [f"c_{c.parent.evolution_instance_name}" for c in real_children if c.parent and c.parent.evolution_instance_name]
        # Fallback: if no registered children, use instances but cap at 5
        if not related_child_ids:
            related_child_ids = [f"c_{inst}" for inst in instances_talked_to[:5]]
        
        # Build real toxicity_trend from BehavioralSnapshot
        snapshots = BehavioralSnapshot.objects.filter(
            profile=prof,
            date_snapshot__gte=timezone.now().date() - datetime.timedelta(days=14)
        ).order_by('date_snapshot')
        
        toxicity_trend = [round(s.risk_score_snapshot, 2) for s in snapshots] or [round(prof.risk_score, 2)] * 7
        
        # Latest snapshot for archetype & pathway data
        latest_snap = snapshots.last()
        archetype = latest_snap.archetype if latest_snap else 'Normal User'
        grooming_prob = round(latest_snap.grooming_prob, 3) if latest_snap else 0.0
        bully_prob = round(latest_snap.bully_prob, 3) if latest_snap else 0.0
        troll_prob = round(latest_snap.troll_prob, 3) if latest_snap else 0.0
        
        days_known = (timezone.now() - prof.first_seen_at).days if prof.first_seen_at else 0
        is_stranger = days_known < 14

        contact_profiles.append({
            "is_stranger": is_stranger,
            "child_initiated": prof.child_initiated,
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
            "toxicity_trend": toxicity_trend,
            "archetype": archetype,
            "grooming_prob": grooming_prob,
            "bully_prob": bully_prob,
            "troll_prob": troll_prob,
            "last_seen": timezone.now().isoformat(),
            "related_child_ids": related_child_ids
        })

    return Response({
        "children": children_profiles,
        "contacts": contact_profiles
    })

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_settings(request):
    """
    GET /api/v1/admin/settings/
    PUT /api/v1/admin/settings/
    Retrieves or updates the global PlatformSettings (singleton).
    """
    from moderation.models import PlatformSettings
    from moderation.serializers import PlatformSettingsSerializer
    
    settings = PlatformSettings.get_settings()
    
    if request.method == 'GET':
        serializer = PlatformSettingsSerializer(settings)
        return Response(serializer.data)
        
    elif request.method == 'PUT':
        serializer = PlatformSettingsSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_children(request):
    """
    GET /api/v1/admin/children/
    Returns all monitored children with their real IDs for report generation.
    """
    children = MonitoredChild.objects.select_related('parent', 'parent__user').all()
    
    data = []
    for child in children:
        parent_name = ''
        instance_name = ''
        if child.parent:
            parent_name = child.parent.user.get_full_name() or child.parent.user.username
            instance_name = child.parent.evolution_instance_name or ''
        
        data.append({
            "id": str(child.id),
            "full_name": child.full_name,
            "parent_name": parent_name,
            "instance_name": instance_name,
            "whatsapp_number": child.whatsapp_display_number or child.whatsapp_jid or '',
            "is_monitored": child.is_monitored,
        })
    
    # Also include device-only parents (no registered child but have an instance)
    parents_device_only = ParentProfile.objects.exclude(
        evolution_instance_name__isnull=True
    ).exclude(
        evolution_instance_name=''
    ).exclude(
        id__in=[c.parent_id for c in children if c.parent_id]
    )
    
    for p in parents_device_only:
        data.append({
            "id": f"device-{p.evolution_instance_name}",
            "full_name": f"Device: {p.evolution_instance_name}",
            "parent_name": p.user.get_full_name() or p.user.username,
            "instance_name": p.evolution_instance_name,
            "whatsapp_number": "",
            "is_monitored": True,
        })
    
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_analytics(request):
    """
    GET /api/v1/admin/analytics/?range=30D
    Returns historical aggregated metrics for the Analytics Dashboard.
    Results are cached in Redis to prevent heavy DB loads.
    """
    from datetime import timedelta
    from django.db.models import Avg, Case, When, IntegerField
    from django.db.models.functions import TruncDay, ExtractHour, ExtractWeekDay
    from django.core.cache import cache

    range_param = request.query_params.get('range', '30D')
    days = 30 if range_param == '30D' else 7
    
    # Check cache first
    cache_key = f"admin_analytics_v1_{days}d"
    cached_data = cache.get(cache_key)
    if cached_data:
        return Response(cached_data)

    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    # Generate continuous list of dates for labels
    date_labels = [(start_date + timedelta(days=i)).strftime('%b %d') for i in range(days)]
    date_mapping = {label: i for i, label in enumerate(date_labels)}
    
    qs = ModerationResult.objects.filter(created_at__gte=start_date, created_at__lte=end_date)
    
    # 1. Risk Score Evolution (Avg Behavioral Risk per day)
    risk_qs = qs.annotate(day=TruncDay('created_at')).values('day').annotate(
        avg_risk=Avg('behavioral_risk_score')
    ).order_by('day')
    
    risk_scores = [0.0] * days
    for r in risk_qs:
        label = r['day'].strftime('%b %d')
        if label in date_mapping:
            risk_scores[date_mapping[label]] = round(r['avg_risk'] or 0.0, 2)
            
    # 2. Decisions Trend
    decisions_qs = qs.annotate(day=TruncDay('created_at')).values('day', 'decision').annotate(count=Count('id'))
    decisions = {'blocked': [0]*days, 'warned': [0]*days, 'allowed': [0]*days}
    for r in decisions_qs:
        label = r['day'].strftime('%b %d')
        if label in date_mapping:
            idx = date_mapping[label]
            if r['decision'] in ['BLOCK', 'ESCALATE']: decisions['blocked'][idx] += r['count']
            elif r['decision'] in ['WARN', 'REVISE']: decisions['warned'][idx] += r['count']
            elif r['decision'] == 'ALLOW': decisions['allowed'][idx] += r['count']

    # 3. Categories Trend
    categories_qs = qs.exclude(primary_class='safe').annotate(day=TruncDay('created_at')).values('day', 'primary_class').annotate(count=Count('id'))
    categories = {'verbal': [0]*days, 'threat': [0]*days, 'sexual': [0]*days, 'discrimination': [0]*days}
    for r in categories_qs:
        label = r['day'].strftime('%b %d')
        if label in date_mapping:
            idx = date_mapping[label]
            cat = r['primary_class'] or ''
            if 'verbal' in cat or 'insult' in cat: categories['verbal'][idx] += r['count']
            elif 'threat' in cat: categories['threat'][idx] += r['count']
            elif 'sexual' in cat: categories['sexual'][idx] += r['count']
            elif 'discrimination' in cat or 'hate' in cat: categories['discrimination'][idx] += r['count']

    # 4. Pipeline Latency
    latency_qs = qs.annotate(day=TruncDay('created_at')).values('day').annotate(
        avg_lat=Avg('processing_time_ms')
    ).order_by('day')
    latency = [0] * days
    for r in latency_qs:
        label = r['day'].strftime('%b %d')
        if label in date_mapping:
            latency[date_mapping[label]] = int(r['avg_lat'] or 0)

    # 5. Language Stats
    lang_qs = qs.exclude(language__isnull=True).exclude(language='error').values('language').annotate(count=Count('id'))
    lang_dist = [0, 0, 0] # FR, AR, EN
    for r in lang_qs:
        l = r['language'].lower() if r['language'] else ''
        if 'fr' in l: lang_dist[0] += r['count']
        elif 'ar' in l: lang_dist[1] += r['count']
        elif 'en' in l: lang_dist[2] += r['count']

    # 6. Notifications Stats
    alert_qs = SecurityAlert.objects.filter(sent_at__gte=start_date, sent_at__lte=end_date).values('alert_type').annotate(count=Count('id'))
    notif_dist = [0, 0, 0, 0] # SMS, Email, Push, Call
    for r in alert_qs:
        t = r['alert_type']
        if t == 'sms': notif_dist[0] += r['count']
        elif t == 'email': notif_dist[1] += r['count']
        elif t == 'push': notif_dist[2] += r['count']
        elif t == 'call': notif_dist[3] += r['count']

    # 7. Confidence Score Distribution
    conf_buckets = [0, 0, 0, 0, 0]
    for r in qs.exclude(confidence_score__isnull=True).values('confidence_score'):
        score = r['confidence_score']
        if score < 0.4: conf_buckets[0] += 1
        elif score < 0.6: conf_buckets[1] += 1
        elif score < 0.75: conf_buckets[2] += 1
        elif score < 0.9: conf_buckets[3] += 1
        else: conf_buckets[4] += 1

    # 8. Agent 3 Activation Rate
    llm_qs = qs.annotate(day=TruncDay('created_at')).values('day').annotate(
        total=Count('id'),
        triggered=Count(Case(When(llm_triggered=True, then=1), output_field=IntegerField()))
    )
    agent3_act = [0.0] * days
    for r in llm_qs:
        label = r['day'].strftime('%b %d')
        if label in date_mapping and r['total'] > 0:
            agent3_act[date_mapping[label]] = round((r['triggered'] / r['total']) * 100, 1)

    # 9. False Positives Trend
    fp_qs = qs.filter(original_ai_decision__in=['BLOCK', 'ESCALATE', 'WARN', 'REVISE'], human_decision='ALLOW').annotate(day=TruncDay('created_at')).values('day').annotate(count=Count('id'))
    fp_trend = [0.0] * days
    
    total_qs = qs.annotate(day=TruncDay('created_at')).values('day').annotate(total=Count('id'))
    total_map = {r['day'].strftime('%b %d'): r['total'] for r in total_qs}
    
    for r in fp_qs:
        label = r['day'].strftime('%b %d')
        if label in date_mapping:
            total = total_map.get(label, 0)
            if total > 0:
                fp_trend[date_mapping[label]] = round((r['count'] / total) * 100, 2)

    # 10. Review Queue Decisions
    review_qs = qs.filter(human_reviewed=True).values('human_decision').annotate(count=Count('id'))
    review_decisions = [0, 0] # Confirmed Block, Reversed to Allow
    for r in review_qs:
        if r['human_decision'] in ['BLOCK', 'ESCALATE']: review_decisions[0] += r['count']
        elif r['human_decision'] == 'ALLOW': review_decisions[1] += r['count']

    # 11. Heatmap (Day of Week vs Hour)
    heatmap = [[0 for _ in range(24)] for _ in range(7)]
    heat_qs = qs.annotate(
        hour=ExtractHour('created_at'),
        weekday=ExtractWeekDay('created_at')
    ).values('hour', 'weekday').annotate(count=Count('id'))
    
    for r in heat_qs:
        hour = r['hour']
        dj_weekday = r['weekday'] 
        if dj_weekday is not None and hour is not None:
            # Map Sunday(1)->6, Monday(2)->0, ...
            mapped_day = (dj_weekday + 5) % 7
            heatmap[mapped_day][hour] += r['count']
            
    # Tables
    top_harassers = UserBehaviorProfile.objects.order_by('-total_blocked_messages_sent')[:5]
    top_harassers_data = []
    for h in top_harassers:
        top_harassers_data.append({
            "contact": h.user_jid,
            "name": h.user_jid.split('@')[0],
            "threatLevel": "high" if h.risk_level in ['HIGH', 'CRITICAL'] else "medium",
            "messagesBlocked": h.total_blocked_messages_sent,
            "platforms": "WhatsApp",
            "status": "Active"
        })
        
    per_child_risk = []
    children = MonitoredChild.objects.all()[:5]
    score_map = {'CRITICAL': 0.95, 'HIGH': 0.75, 'MEDIUM': 0.45, 'LOW': 0.15}
    for c in children:
        risk_level = c.get_risk_level().upper()
        per_child_risk.append({
            "id": str(c.id),
            "name": c.full_name,
            "grade": c.school_level or "Primaire",
            "currentScore": score_map.get(risk_level, 0.15),
            "trend": "+2%", # Mocking trend
            "alerts": SecurityAlert.objects.filter(moderation_result__sender_jid=c.whatsapp_jid).count()
        })

    # Summary stats for the top stat cards
    total_messages_in_range = qs.count()
    avg_risk_in_range = qs.aggregate(avg=Avg('behavioral_risk_score'))['avg'] or 0.0

    # False positive rate: human overrides that reversed a block/warn to allow
    total_reviewed = qs.filter(human_reviewed=True).count()
    total_false_positives = qs.filter(
        original_ai_decision__in=['BLOCK', 'ESCALATE', 'WARN', 'REVISE'],
        human_decision='ALLOW'
    ).count()
    false_positive_rate = round((total_false_positives / max(total_reviewed, 1)) * 100, 1)

    avg_latency_in_range = qs.aggregate(avg=Avg('processing_time_ms'))['avg'] or 0

    # Average review resolution time (from flagged_for_review to human_reviewed)
    from django.db.models import F
    reviewed_with_times = qs.filter(
        human_reviewed=True, human_reviewed_at__isnull=False, created_at__isnull=False
    ).annotate(resolution_secs=F('human_reviewed_at') - F('created_at'))
    if reviewed_with_times.exists():
        from datetime import timedelta as td
        total_secs = sum(
            (r.human_reviewed_at - r.created_at).total_seconds()
            for r in reviewed_with_times[:100]
            if r.human_reviewed_at and r.created_at
        )
        avg_secs = total_secs / reviewed_with_times.count()
        if avg_secs < 60:
            avg_resolution_str = f"{int(avg_secs)}s"
        elif avg_secs < 3600:
            avg_resolution_str = f"{int(avg_secs // 60)}m {int(avg_secs % 60)}s"
        else:
            avg_resolution_str = f"{int(avg_secs // 3600)}h {int((avg_secs % 3600) // 60)}m"
    else:
        avg_resolution_str = "N/A"

    response_data = {
        "labels": date_labels,
        "summary": {
            "totalMessages": total_messages_in_range,
            "avgRisk": round(avg_risk_in_range, 2),
            "falsePositiveRate": false_positive_rate,
            "avgLatency": int(avg_latency_in_range),
        },
        "riskScores": risk_scores,
        "decisions": decisions,
        "categories": categories,
        "latency": latency,
        "languageDistribution": lang_dist,
        "notificationStats": notif_dist,
        "confidenceDistribution": {
            "labels": ['0.0-0.4', '0.4-0.6', '0.6-0.75', '0.75-0.9', '0.9-1.0'],
            "data": conf_buckets
        },
        "agent3Activation": agent3_act,
        "falsePositives": fp_trend,
        "reviewQueue": {
            "avgResolutionTime": avg_resolution_str,
            "decisions": review_decisions
        },
        "peakActivity": heatmap,
        "topHarassers": top_harassers_data,
        "perChildRisk": per_child_risk
    }
    
    # Cache for 2 hours (7200 seconds)
    cache.set(cache_key, response_data, 7200)

    return Response(response_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_channels(request):
    """
    GET /api/v1/admin/channels/
    Infrastructure monitoring dashboard: queries actual Evolution API instances
    and maps them back to ParentProfile owners and their MonitoredChild records.
    Admins observe and force-logout — they do NOT create instances here.
    Instance creation happens via the Parent WhatsApp Setup page.
    """
    import datetime
    
    evo_status = "Online"
    evo_version = "v2.1.2"
    evo_instances_api = []
    
    try:
        from moderation.evolution_api import get_all_instances
        evo_instances_api = get_all_instances()
        if not isinstance(evo_instances_api, list):
            evo_instances_api = []
    except Exception:
        evo_status = "Offline"
    
    # Build a map of all ParentProfiles that have an Evolution API instance
    parent_instance_map = {}
    for p in ParentProfile.objects.exclude(
        evolution_instance_name__isnull=True
    ).exclude(
        evolution_instance_name=''
    ).select_related('user').prefetch_related('children'):
        parent_instance_map[p.evolution_instance_name] = p
    
    instances = []
    
    for evo_raw in evo_instances_api:
        evo_inst = evo_raw.get("instance", evo_raw)
        instance_name = (
            evo_inst.get("instanceName")
            or evo_raw.get("instanceName")
            or evo_raw.get("name")
            or ""
        )
        if not instance_name:
            continue
        
        # --- Connection status ---
        conn_status = evo_inst.get("status", evo_inst.get("connectionStatus", "")).lower()
        if conn_status == "open":
            status = "Connected"
        elif conn_status == "connecting":
            status = "Pending QR Scan"
        else:
            status = "Disconnected"
        
        # --- Owner JID (the phone number linked to this session) ---
        owner_jid = evo_inst.get("ownerJid", "")
        owner_number = owner_jid.split("@")[0] if owner_jid else ""
        
        # --- Map to parent ---
        parent_profile = parent_instance_map.get(instance_name)
        parent_name = ""
        parent_email = ""
        children_info = []
        
        if parent_profile:
            parent_name = parent_profile.user.get_full_name() or parent_profile.user.username
            parent_email = parent_profile.user.email or parent_profile.user.notification_email or ""
            
            for child in parent_profile.children.filter(is_monitored=True):
                children_info.append({
                    "id": str(child.id),
                    "name": child.full_name,
                    "whatsappNumber": child.whatsapp_display_number or child.whatsapp_jid or "",
                })
        else:
            # Instance exists in Evolution API but no ParentProfile owns it
            # Could be an orphan or manually created instance
            parent_name = "Unregistered"
        
        # --- Message count from this instance ---
        intercepted = ModerationResult.objects.filter(instance_name=instance_name).count()
        
        # --- Last activity ---
        last_result = ModerationResult.objects.filter(
            instance_name=instance_name
        ).order_by('-created_at').first()
        
        if last_result:
            delta = timezone.now() - last_result.created_at
            if delta.total_seconds() < 60:
                last_active = "Just now"
            elif delta.total_seconds() < 3600:
                last_active = f"{int(delta.total_seconds() // 60)}m ago"
            elif delta.total_seconds() < 86400:
                last_active = f"{int(delta.total_seconds() // 3600)}h ago"
            else:
                last_active = f"{delta.days}d ago"
        elif status == "Connected":
            last_active = "Active (no messages yet)"
        else:
            last_active = "Never"
        
        instances.append({
            "id": instance_name,
            "channelType": "whatsapp",
            "instanceName": instance_name,
            "ownerNumber": owner_number,
            "parentName": parent_name,
            "parentEmail": parent_email,
            "children": children_info,
            "connectionType": "Evolution API",
            "status": status,
            "lastActive": last_active,
            "interceptedMessages": intercepted,
        })
    
    # Also surface parents whose instance is NOT in Evolution API (session died / was deleted)
    active_instance_names = {inst["instanceName"] for inst in instances}
    for inst_name, parent_profile in parent_instance_map.items():
        if inst_name not in active_instance_names:
            children_info = []
            for child in parent_profile.children.filter(is_monitored=True):
                children_info.append({
                    "id": str(child.id),
                    "name": child.full_name,
                    "whatsappNumber": child.whatsapp_display_number or child.whatsapp_jid or "",
                })
            
            intercepted = ModerationResult.objects.filter(instance_name=inst_name).count()
            
            instances.append({
                "id": inst_name,
                "channelType": "whatsapp",
                "instanceName": inst_name,
                "ownerNumber": "",
                "parentName": parent_profile.user.get_full_name() or parent_profile.user.username,
                "parentEmail": parent_profile.user.email or "",
                "children": children_info,
                "connectionType": "Evolution API",
                "status": "Disconnected",
                "lastActive": "Session lost",
                "interceptedMessages": intercepted,
            })
    
    server_status = {
        "serverUrl": "Evolution API",
        "status": evo_status,
        "version": evo_version,
        "activeInstances": len([i for i in instances if i["status"] == "Connected"]),
        "totalInstances": len(instances),
        "maxInstances": 10,
        "webhook": "Connected" if evo_status == "Online" else "Disconnected",
        "warning": "Uses WhatsApp Web protocol (Baileys). Parents pair their child's device from the Parent Dashboard."
    }
    
    return Response({
        "serverStatus": server_status,
        "instances": instances
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_channels_disconnect(request, instance_id):
    """
    DELETE /api/v1/admin/channels/<instance_id>/
    Emergency force-logout: kills a WhatsApp session from the admin panel.
    The instance_id here is the Evolution API instance name directly.
    """
    from moderation.evolution_api import delete_whatsapp_instance
    
    delete_whatsapp_instance(instance_id)
    
    return Response({"status": "deleted"})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def test_llm_connection(request):
    """POST /api/v1/admin/test-llm/ — Verify LLM provider is reachable."""
    import time, os
    from moderation.models import PlatformSettings
    settings = PlatformSettings.get_settings()
    provider = settings.active_llm_provider
    model = settings.active_llm_model

    start = time.time()
    try:
        if provider == 'groq':
            from groq import Groq
            client = Groq(api_key=os.getenv('GROQ_API_KEY'))
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Reply with OK"}],
                max_tokens=5
            )
            latency_ms = int((time.time() - start) * 1000)
            return Response({"ok": True, "message": f"Connected — {latency_ms}ms response time", "model": model})
        else:
            return Response({"ok": False, "message": f"Provider '{provider}' not configured on this server"})
    except Exception as e:
        return Response({"ok": False, "message": f"Connection failed: {str(e)[:100]}"})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def simulate_message(request):
    """POST /api/v1/admin/simulate/ — Run a message through the AI pipeline without persisting."""
    import time
    text = request.data.get('text', '').strip()
    language = request.data.get('language', 'auto')
    if not text:
        return Response({"error": "No text provided"}, status=400)

    start = time.time()
    try:
        from ml_pipeline.graph import aegis_graph

        initial_state = {
            "raw_text": text,
            "sender_jid": "simulation@test",
            "sender_phone_jid": "simulation@test",
            "instance_name": "__simulation__",
            "message_key_id": None,
            "push_name": "Simulation",
            "is_from_me": False,
            "start_time_ms": int(start * 1000),
            "dry_run": True,
        }

        final_state = aegis_graph.invoke(initial_state)
        latency_ms = int((time.time() - start) * 1000)

        # Compute per-agent deltas (individual durations, not cumulative)
        t12 = final_state.get("agent_1_2_latency_ms") or 0
        t3_cum = final_state.get("agent_3_latency_ms") or 0
        t4_cum = final_state.get("agent_4_latency_ms") or 0
        t5_cum = final_state.get("agent_5_latency_ms") or 0

        delta_12 = int(t12)
        delta_3 = max(0, int(t3_cum - t12)) if t3_cum > 0 else 0
        delta_4 = max(0, int(t4_cum - max(t3_cum, t12)))
        delta_5 = max(0, int(t5_cum - t4_cum)) if t4_cum > 0 else max(0, int(t5_cum))

        return Response({
            "toxicity_score": round(final_state.get("m1_score", 0.0), 4),
            "primary_class": final_state.get("primary_class", "safe"),
            "confidence": final_state.get("m2_confidence"),
            "llm_triggered": final_state.get("llm_triggered", False),
            "llm_explanation": final_state.get("llm_explanation", ""),
            "behavioral_risk_score": round(final_state.get("risk_score", 0.0), 4),
            "final_score": round(final_state.get("m1_score", 0.0), 4),
            "decision": final_state.get("decision", "ALLOW"),
            "language": final_state.get("detected_language", language),
            "explanation": final_state.get("llm_explanation", "Pipeline analysis complete."),
            "latency_ms": latency_ms,
            "agent_latencies": {
                "agent_1_2": delta_12,
                "agent_3": delta_3,
                "agent_4": delta_4,
                "agent_5": delta_5,
            },
            "needs_audit": final_state.get("needs_audit", False),
            "escalation_risk": round(final_state.get("escalation_risk", 0.0), 4),
            "ml_corrected": final_state.get("ml_corrected", False),
        })
    except Exception as e:
        logger.error(f"Simulation failed: {e}")
        return Response({"error": f"Pipeline error: {str(e)[:200]}"}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def agent_latencies(request):
    """GET /api/v1/admin/agent-latencies/ — Live agent latencies from Redis."""
    from moderation.views.webhook import get_avg_latency
    latencies = {}
    for i in range(1, 6):
        val = get_avg_latency(f'agent_{i}', None)
        latencies[f"agent_{i}"] = int(val) if val is not None else None
    return Response(latencies)
