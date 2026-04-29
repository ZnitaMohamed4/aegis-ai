import os, sys, django
sys.path.append("/home/muhammed/Desktop/aegis-ai/aegis-backend")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aegis.settings')
django.setup()
from moderation.models import UserBehaviorProfile, ModerationResult
p = UserBehaviorProfile.objects.filter(user_jid__contains="212786814288").first()
if p:
    print("DB unique_targets_count:", p.unique_targets_count)
    res = ModerationResult.objects.filter(sender_jid=p.user_jid)
    print("Instance names in ModResult:", res.values_list('instance_name', flat=True).distinct())
