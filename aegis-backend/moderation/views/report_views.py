import requests
import os
import base64
import json
from datetime import timedelta, datetime
from django.core.files.base import ContentFile
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count
from ..models import Report, MonitoredChild, AegisUser, ParentProfile, ModerationResult
from ..serializers import ReportSerializer
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.urls import reverse

# Note: Using localhost as requested. This can be moved to Django settings in production.
N8N_WEBHOOK_URL = 'http://localhost:5678/webhook/generate-report'


def _to_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_prefixed_stats(data):
    """Extract stats when posted as form-style keys like stats[total_messages]."""
    extracted = {}
    for key, val in data.items():
        if key.startswith('stats[') and key.endswith(']'):
            extracted[key[6:-1]] = val
    return extracted


def _normalize_stats(raw):
    """Normalize stats keys from n8n payload variations to frontend contract."""
    if not isinstance(raw, dict):
        return {}

    return {
        'total_messages': _to_int(raw.get('total_messages', raw.get('total_messages_scanned', 0))),
        'total_blocked': _to_int(raw.get('total_blocked', raw.get('blocked_messages', raw.get('blocked', 0)))),
        'unique_harassers': _to_int(raw.get('unique_harassers', raw.get('unique_threat_contacts', 0))),
        'escalations': _to_int(raw.get('escalations', raw.get('escalated_messages', 0))),
        'dominant_category': raw.get('dominant_category', raw.get('top_category', '')) or '',
        'risk_score_start': _to_float(raw.get('risk_score_start', 0.0)),
        'risk_score_end': _to_float(raw.get('risk_score_end', 0.0)),
    }


def _compute_fallback_stats(report):
    """Compute report stats directly from DB when callback stats are missing/malformed."""
    parent_profile = getattr(report.requested_by, 'parent_profile', None)
    instance_name = getattr(parent_profile, 'evolution_instance_name', None)
    if not instance_name:
        return {}

    p_start = report.period_start
    if isinstance(p_start, str):
        p_start = datetime.strptime(p_start, '%Y-%m-%d').date()
        
    p_end = report.period_end
    if isinstance(p_end, str):
        p_end = datetime.strptime(p_end, '%Y-%m-%d').date()

    base_qs = ModerationResult.objects.filter(
        instance_name=instance_name,
        created_at__date__gte=p_start,
        created_at__date__lte=p_end,
    )

    total_messages = base_qs.count()
    if total_messages == 0:
        return {}

    total_blocked = base_qs.filter(decision__in=['BLOCK', 'ESCALATE']).count()
    escalations = base_qs.filter(decision='ESCALATE').count()
    unique_harassers = base_qs.filter(is_from_me=False).exclude(decision='ALLOW').values('sender_jid').distinct().count()
    flagged_messages = base_qs.exclude(decision='ALLOW').count()

    top_category = (
        base_qs.exclude(decision='ALLOW')
        .exclude(primary_class__isnull=True)
        .exclude(primary_class='')
        .exclude(primary_class='safe')
        .values('primary_class')
        .annotate(c=Count('id'))
        .order_by('-c')
        .first()
    )

    prev_start = p_start - timedelta(days=7)
    prev_end = p_start - timedelta(days=1)
    prev_qs = ModerationResult.objects.filter(
        instance_name=instance_name,
        created_at__date__gte=prev_start,
        created_at__date__lte=prev_end,
    )
    prev_total = prev_qs.count()
    prev_flagged = prev_qs.exclude(decision='ALLOW').count()

    risk_score_start = round(prev_flagged / prev_total, 2) if prev_total else 0.0
    risk_score_end = round(flagged_messages / total_messages, 2) if total_messages else 0.0

    return {
        'total_messages': total_messages,
        'total_blocked': total_blocked,
        'unique_harassers': unique_harassers,
        'escalations': escalations,
        'dominant_category': (top_category or {}).get('primary_class', ''),
        'risk_score_start': risk_score_start,
        'risk_score_end': risk_score_end,
    }


def generate_summary_direct(report):
    """Generates a text summary using Groq LLM directly."""
    stats = _compute_fallback_stats(report)
    report.stats_json = stats
    
    child_name = report.child.full_name if report.child else "the monitored children"
    period = f"{report.period_start} to {report.period_end}"
    
    prompt = f"""You are AEGIS, an AI child safety monitoring system. 
Please generate a brief, reassuring, yet professional summary of the child's activity for the parent.
Child: {child_name}
Period: {period}
Stats:
- Total Messages: {stats.get('total_messages', 0)}
- Blocked Messages: {stats.get('total_blocked', 0)}
- Unique Harassers: {stats.get('unique_harassers', 0)}
- Escalations: {stats.get('escalations', 0)}
- Dominant Threat Category: {stats.get('dominant_category', 'None')}

CRITICAL INSTRUCTIONS:
1. You MUST write exactly ONE short paragraph (maximum 3 sentences).
2. DO NOT use any bullet points, lists, or markdown formatting.
3. Address the parent directly in a professional and reassuring tone."""

    api_key = os.environ.get('GROQ_API_KEY')
    model = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
    narrative = "Activity summary has been generated."

    if api_key:
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.5,
                    "max_tokens": 150
                },
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                narrative = data['choices'][0]['message']['content'].strip()
            else:
                narrative = f"Could not generate AI summary. Status: {response.status_code}"
        except Exception as e:
            narrative = "Could not reach AI service for summary."
    
    report.ai_narrative = narrative
    report.status = Report.Status.READY
    report.completed_at = timezone.now()
    report.save()
    
    channel_layer = get_channel_layer()
    if channel_layer:
        room_group_name = f"user_{report.requested_by.id}"
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'notify',
                'event': 'REPORT_READY',
                'report_id': str(report.id),
                'report_status': report.status
            }
        )
        
    return Response({
        'report_id': str(report.id),
        'status': report.status
    }, status=200)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_report_list(request):
    """Fetch reports for the authenticated parent."""
    # Ensure user is a parent
    if not request.user.is_parent():
        return Response({'detail': 'Not a parent.'}, status=403)

    # Auto-clean stale reports that were left in GENERATING state.
    stale_cutoff = timezone.now() - timedelta(minutes=3)
    Report.objects.filter(
        requested_by=request.user,
        status=Report.Status.GENERATING,
        created_at__lt=stale_cutoff
    ).update(
        status=Report.Status.FAILED,
        ai_narrative='Generation timed out waiting for n8n callback.',
        completed_at=timezone.now()
    )
    
    reports = Report.objects.filter(requested_by=request.user)
    
    # Filter by child if provided
    child_id = request.query_params.get('child_id')
    if child_id:
        reports = reports.filter(child_id=child_id)
        
    return Response(ReportSerializer(reports, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_report_list(request):
    """Fetch all reports for an admin."""
    if not request.user.is_admin():
        return Response({'detail': 'Not an admin.'}, status=403)
        
    reports = Report.objects.all()
    return Response(ReportSerializer(reports, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_report(request):
    """
    Trigger the n8n webhook to generate a new report.
    Expects:
    - child_id (nullable for admin intelligence brief)
    - period_start (YYYY-MM-DD)
    - period_end (YYYY-MM-DD)
    - report_type (summary, full, legal, intelligence)
    - delivery_channel (email, whatsapp, both, dashboard)
    """
    user = request.user
    
    # Extract data from request
    child_id = request.data.get('child_id')
    period_start = request.data.get('period_start')
    period_end = request.data.get('period_end')
    report_type = request.data.get('report_type', 'summary')
    delivery_channel = request.data.get('delivery_channel', 'dashboard')
    
    # Validate child for parent
    child = None
    if child_id:
        if user.is_parent():
            child = get_object_or_404(MonitoredChild, id=child_id, parent__user=user)
        else:
            child = get_object_or_404(MonitoredChild, id=child_id)
    
    # Create the Report record in DB
    report = Report.objects.create(
        requested_by=user,
        child=child,
        report_type=report_type,
        period_start=period_start,
        period_end=period_end,
        status=Report.Status.GENERATING,
        delivery_channel=delivery_channel
    )
    
    # Prepare delivery context
    parent_profile = getattr(user, 'parent_profile', None)
    
    webhook_payload = {
        'report_id': str(report.id),
        'period_start': period_start,
        'period_end': period_end,
        'report_type': report_type,
        'delivery_channel': delivery_channel,
        
        # User details
        'parent_name': user.get_full_name() or user.username,
        'parent_email': user.notification_email or user.email,
        'parent_phone': user.phone_number,
        'whatsapp_instance': parent_profile.evolution_instance_name if parent_profile else '',
        
        # Child details
        'child_id': str(child.id) if child else '',
        'child_name': child.full_name if child else 'All Children',
        'monitored_number': child.whatsapp_display_number if child else '',
        'child_jid': child.whatsapp_jid if child else '',
        
        # Callback URL for n8n
        'callback_url': request.build_absolute_uri(reverse('report-complete-webhook', args=[report.id]))
    }
    
    # Trigger n8n
    if report_type == 'summary':
        return generate_summary_direct(report)

    try:
        requests.post(N8N_WEBHOOK_URL, json=webhook_payload, timeout=8)
    except requests.Timeout:
        # n8n may still process asynchronously and call callback later.
        report.ai_narrative = 'Trigger timed out, awaiting asynchronous callback from n8n.'
        report.save(update_fields=['ai_narrative'])
        return Response({
            'report_id': str(report.id),
            'status': report.status,
            'warning': 'n8n trigger timeout; generation may still complete asynchronously.'
        }, status=202)
    except requests.RequestException as e:
        # We don't fail the request immediately; n8n might be slow or we might implement retries.
        # But for this prototype, if connection fails, mark it failed.
        report.status = Report.Status.FAILED
        report.ai_narrative = f"Failed to trigger generation: {str(e)}"
        report.completed_at = timezone.now()
        report.save()
        return Response({'detail': 'Failed to trigger n8n.', 'error': str(e)}, status=503)
    
    return Response({
        'report_id': str(report.id),
        'status': report.status
    }, status=202)


@api_view(['POST'])
def report_complete_webhook(request, report_id):
    """
    Called by n8n when the report is ready.
    Expects JSON payload with:
    - status ('ready' or 'failed')
    - pdf_base64 (if ready)
    - ai_narrative
    - stats (dict)
    """
    report = get_object_or_404(Report, id=report_id)
    
    status_val = str(request.data.get('status', 'ready')).strip().lower()

    # Do not allow a late failed callback to override an already READY report.
    if report.status == Report.Status.READY and status_val in ('failed', 'error'):
        return Response({'status': 'ignored', 'detail': 'Report already finalized as ready.'})

    # If report already failed, ignore late success callback unless you explicitly want retry semantics.
    if report.status == Report.Status.FAILED and status_val in ('ready', 'success'):
        return Response({'status': 'ignored', 'detail': 'Report already finalized as failed.'})

    if status_val == 'failed':
        report.status = Report.Status.FAILED
        report.ai_narrative = (
            request.data.get('error')
            or request.data.get('reason')
            or request.data.get('message')
            or 'Unknown error during generation.'
        )
    else:
        report.status = Report.Status.READY
        report.ai_narrative = request.data.get('ai_narrative', '')
        raw_stats = request.data.get('stats', {})

        # n8n can send stats either as JSON object or as string.
        # Handle string payloads defensively so frontend stats do not fall back to zeros.
        if isinstance(raw_stats, str):
            raw_stats = raw_stats.strip()
            if raw_stats.startswith('='):
                raw_stats = raw_stats[1:].strip()

            if raw_stats == '[object Object]':
                parsed_stats = {}
            else:
                try:
                    parsed_stats = json.loads(raw_stats)
                    if isinstance(parsed_stats, str):
                        parsed_stats = json.loads(parsed_stats)
                except json.JSONDecodeError:
                    parsed_stats = {}
        elif isinstance(raw_stats, dict):
            parsed_stats = raw_stats
        else:
            parsed_stats = {}

        if not parsed_stats:
            parsed_stats = _extract_prefixed_stats(request.data)

        normalized_stats = _normalize_stats(parsed_stats)
        if not normalized_stats or all(
            normalized_stats.get(key, 0) == 0 for key in ['total_messages', 'total_blocked', 'unique_harassers', 'escalations']
        ):
            fallback_stats = _compute_fallback_stats(report)
            if fallback_stats:
                normalized_stats = fallback_stats

        report.stats_json = normalized_stats
        
        # Save PDF from base64 or direct file upload
        pdf_b64 = request.data.get('pdf_base64')
        pdf_file = request.FILES.get('pdf_file')
        
        if pdf_b64:
            pdf_data = base64.b64decode(pdf_b64)
            filename = f"report_{report.id}.pdf"
            report.pdf_file.save(filename, ContentFile(pdf_data), save=False)
        elif pdf_file:
            filename = f"report_{report.id}.pdf"
            report.pdf_file.save(filename, pdf_file, save=False)
            
    report.completed_at = timezone.now()
    report.save()
    
    # Notify via WebSocket
    channel_layer = get_channel_layer()
    if channel_layer:
        # Determine room group based on user ID
        room_group_name = f"user_{report.requested_by.id}"
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'notify',
                'event': 'REPORT_READY',
                'report_id': str(report.id),
                'report_status': report.status
            }
        )
        
    return Response({'status': 'success'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_report(request, report_id):
    """Returns the generated PDF URL for a report."""
    report = get_object_or_404(Report, id=report_id)
    
    # Ensure permission
    if not request.user.is_admin() and report.requested_by != request.user:
        return Response({'detail': 'Not authorized.'}, status=403)
        
    if not report.pdf_file:
        return Response({'detail': 'No PDF available yet.'}, status=404)
        
    return Response({
        'download_url': request.build_absolute_uri(report.pdf_file.url)
    })
