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

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def current_user(request):
    """Returns or updates details of the currently logged-in user."""
    if request.method == 'GET':
        serializer = AegisUserSerializer(request.user)
        return Response(serializer.data)
    elif request.method == 'PUT':
        # If a password change is requested, validate current_password first
        if 'password' in request.data:
            current_password = request.data.get('current_password', '')
            if not current_password:
                return Response(
                    {"error": "current_password is required to change your password."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not request.user.check_password(current_password):
                return Response(
                    {"error": "Current password is incorrect."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Set the new password properly (hashed)
            request.user.set_password(request.data['password'])
            request.user.save(update_fields=['password'])
            # Remove password from data so the serializer doesn't try to set it again
            mutable_data = request.data.copy()
            mutable_data.pop('password', None)
            mutable_data.pop('current_password', None)
            if not mutable_data:
                return Response(AegisUserSerializer(request.user).data)
            serializer = AegisUserSerializer(request.user, data=mutable_data, partial=True)
        else:
            serializer = AegisUserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            
            # Handle ParentProfile fields
            if request.user.is_parent() and hasattr(request.user, 'parent_profile'):
                profile = request.user.parent_profile
                updated = False
                if 'monitoring_mode' in request.data:
                    mode = request.data['monitoring_mode']
                    if mode in ('child', 'adult'):
                        profile.monitoring_mode = mode
                        updated = True
                if 'trusted_contact_name' in request.data:
                    profile.trusted_contact_name = request.data['trusted_contact_name']
                    updated = True
                if 'trusted_contact_phone' in request.data:
                    profile.trusted_contact_phone = request.data['trusted_contact_phone']
                    updated = True
                if updated:
                    profile.save()
            
            # Ensure the serializer fetches the updated profile
            request.user.refresh_from_db()
            return Response(AegisUserSerializer(request.user).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
