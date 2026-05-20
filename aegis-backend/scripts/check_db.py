import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from moderation.models import AegisUser, ParentProfile, MonitoredChild

print("--- USERS ---")
for u in AegisUser.objects.all():
    print(f"User: {u.username}, Role: {u.role}, is_superuser: {u.is_superuser}, has_profile: {hasattr(u, 'parent_profile')}")

print("\n--- PARENT PROFILES ---")
for p in ParentProfile.objects.all():
    children = p.children.all()
    print(f"Profile: {p.user.username}, Children: {[(c.full_name, c.is_monitored) for c in children]}")
