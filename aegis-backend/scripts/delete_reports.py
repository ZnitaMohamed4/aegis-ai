import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aegis.settings')
django.setup()

from moderation.models import Report

reports = Report.objects.order_by('-created_at')
if reports.count() > 1:
    last_report = reports.first()
    reports_to_delete = reports.exclude(id=last_report.id)
    count = reports_to_delete.count()
    reports_to_delete.delete()
    print(f"Deleted {count} reports. Kept report ID: {last_report.id}")
else:
    print(f"Only {reports.count()} reports found. Nothing to delete.")
