#!/usr/bin/env python
import os
import sys

# Django setup
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from moderation.models import ModerationResult, Message, ChatSession, ChatMessage
from django.utils import timezone
import datetime

def main():
    print("\n" + "=" * 60)
    print("  🗑️ AEGIS 'Today' Messages Cleanup")
    print("=" * 60)

    # Get start of today (midnight)
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

    mod_results = ModerationResult.objects.filter(created_at__gte=today_start)
    messages = Message.objects.filter(sent_at__gte=today_start)
    
    mod_count = mod_results.count()
    msg_count = messages.count()

    print(f"\n  📊 Found records created TODAY (since {today_start.strftime('%Y-%m-%d %H:%M:%S')}):")
    print(f"     ModerationResults: {mod_count}")
    print(f"     Messages:          {msg_count}")

    if mod_count == 0 and msg_count == 0:
        print("\n  ✅ No messages from today to delete.")
        return

    print(f"\n  ⚠️  This will permanently DELETE {mod_count} ModerationResults and {msg_count} Messages created today.")
    
    confirm = input(f"\n  Type 'DELETE' to confirm: ")
    if confirm.strip() != "DELETE":
        print("  ❌ Aborted.")
        return

    deleted_msgs, _ = messages.delete()
    deleted_mods, _ = mod_results.delete()

    print(f"\n  ✅ Deleted {deleted_msgs} Messages.")
    print(f"  ✅ Deleted {deleted_mods} ModerationResults.")

    print("\n" + "=" * 60)
    print("  ✅ CLEANUP COMPLETE")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
