import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aegis.settings')
django.setup()

from moderation.models import ModerationResult

jids = ModerationResult.objects.values_list('sender_jid', flat=True).distinct()
for j in jids:
    print(j)
