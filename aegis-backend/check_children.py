import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from moderation.models import MonitoredChild

print("--- MONITORED CHILDREN ---")
for c in MonitoredChild.objects.all():
    print(f"Child: {c.full_name}, JID: {c.whatsapp_jid}, Parent ID: {c.parent_id}, is_monitored: {c.is_monitored}")
