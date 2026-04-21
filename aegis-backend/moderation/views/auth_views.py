"""
Authentication and WhatsApp setup endpoints for AEGIS.

Extracted from views.py during Phase 2 audit refactoring (2026-04-21).
"""
import logging
import time

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from moderation.models import AegisUser
from moderation.serializers import ParentRegisterSerializer, AegisUserSerializer
from moderation.permissions import IsAdminUser
from moderation.evolution_api import (
    create_whatsapp_instance, get_qr_code, check_connection_status, get_instance_details
)
from moderation.services.formatters import format_phone_number

logger = logging.getLogger(__name__)

# AUTH API ENDPOINTS
# ------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([AllowAny])
def register_parent(request):
    """Endpoint for a parent to create a new account."""
    serializer = ParentRegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({
            "message": "User created successfully",
            "user": AegisUserSerializer(user).data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    """Returns details of the currently logged-in user."""
    serializer = AegisUserSerializer(request.user)
    return Response(serializer.data)

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



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generate_whatsapp_qr(request):
    """
    Returns the Base64 QR code for a parent to link their child's WhatsApp.
    """
    user = request.user
    if not user.is_parent():
        return Response({"error": "Only parents can link WhatsApp"}, status=status.HTTP_403_FORBIDDEN)
        
    profile = user.parent_profile
    instance_name = profile.evolution_instance_name
    
    # 1. If parent doesn't have an instance allocated yet, create one!
    if not instance_name:
        instance_name = f"aegis_parent_{user.id.hex[:8]}"
        profile.evolution_instance_name = instance_name
        profile.save(update_fields=['evolution_instance_name'])
        
        # Tell WhatsApp Engine to prepare this instance
        create_whatsapp_instance(instance_name)
        time.sleep(2) # Give Evolution API a brief moment to initialize the QR
        
    # 2. Fetch the QR Code Image
    qr_data = get_qr_code(instance_name)
    
    # If the instance doesn't exist in Evolution API (404), re-create it!
    if isinstance(qr_data, dict) and (qr_data.get('status') == 404 or 'not exist' in str(qr_data.get('response', ''))):
        logger.info(f"[AEGIS] Instance {instance_name} missing from engine. Re-creating...")
        create_whatsapp_instance(instance_name)
        time.sleep(3)
        qr_data = get_qr_code(instance_name)
    
    if not qr_data or (isinstance(qr_data, dict) and qr_data.get('status') == 404):
        return Response({"error": "Failed to communicate with WhatsApp Engine. Ensure Evolution API is healthy."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    return Response(qr_data)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_whatsapp_status(request):
    """
    Checks if the parent's WhatsApp instance is connected.
    """
    from moderation.evolution_api import check_connection_status, get_instance_details
    user = request.user
    profile = user.parent_profile
    instance_name = profile.evolution_instance_name
    
    if not instance_name:
        return Response({"status": "not_created"})
        
    status_data = check_connection_status(instance_name)
    
    # Evolution API v2 returns { "instance": { "state": "open" } } 
    # but sometimes it's direct.
    state = "unknown"
    if status_data:
        # Check various common response keys
        state = status_data.get('instance', {}).get('state', status_data.get('state', 'unknown'))
        
    is_connected = state == "open"
    connected_number = None
    
    if is_connected:
        details = get_instance_details(instance_name)
        if details:
            owner_jid = details.get('ownerJid')
            if owner_jid:
                # Format "212709731128@s.whatsapp.net" -> "+212 709731128"
                raw_num = owner_jid.split('@')[0]
                if len(raw_num) > 4:
                    connected_number = f"+{raw_num[:3]} {raw_num[3:]}"
                else:
                    connected_number = f"+{raw_num}"
    
    return Response({
        "instance": instance_name,
        "state": state,
        "connected": is_connected,
        "number": connected_number
    })
