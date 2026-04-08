import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aegis.settings')
django.setup()

from moderation.models import UserBehaviorProfile
profiles = UserBehaviorProfile.objects.all()
print("PROFILES IN DB:")
for p in profiles:
    print(f"- {p.user_jid} | Sent: {p.total_messages_sent} | Blocked: {p.total_blocked_messages} | Risk: {p.risk_score}")
