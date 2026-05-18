#!/usr/bin/env python
"""
AEGIS Profile Reset Script
============================
Resets all UserBehaviorProfile records (zero counters, LOW risk)
and deletes all BehavioralSnapshot records.

Preserves: Conversation, Message, ModerationResult (untouched).

Usage:
    cd aegis-backend
    DJANGO_SETTINGS_MODULE=config.settings python scripts/reset_profiles.py
"""

import os
import sys

# Django setup
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from moderation.models import UserBehaviorProfile, BehavioralSnapshot


def main():
    print("\n" + "=" * 60)
    print("  🔄 AEGIS Profile Reset")
    print("=" * 60)

    profile_count = UserBehaviorProfile.objects.count()
    snapshot_count = BehavioralSnapshot.objects.count()

    print(f"\n  📊 Current state:")
    print(f"     UserBehaviorProfile records: {profile_count}")
    print(f"     BehavioralSnapshot records:  {snapshot_count}")

    if profile_count == 0 and snapshot_count == 0:
        print("\n  ✅ Nothing to reset — database is already clean.")
        return

    print(f"\n  ⚠️  This will:")
    print(f"     1. Reset ALL {profile_count} UserBehaviorProfile records to zero/LOW")
    print(f"     2. DELETE ALL {snapshot_count} BehavioralSnapshot records")
    print(f"     3. Keep Conversations, Messages, ModerationResults UNTOUCHED")

    confirm = input(f"\n  Type 'RESET' to confirm: ")
    if confirm.strip() != "RESET":
        print("  ❌ Aborted.")
        return

    # Reset all profiles
    print(f"\n  🔄 Resetting {profile_count} profiles...")
    UserBehaviorProfile.objects.all().update(
        total_messages_sent=0,
        total_blocked_messages_sent=0,
        total_blocked_messages_received=0,
        block_ratio=0.0,
        average_toxicity_score=0.0,
        escalation_count=0,
        night_activity_ratio=0.0,
        unique_targets_count=0,
        repeated_harassers_count=0,
        message_frequency_1h=0.0,
        avg_message_length=0.0,
        burst_count_24h=0,
        max_toxicity_24h=0.0,
        upward_corrections_total=0,
        downward_corrections_total=0,
        llm_triggers_total=0,
        risk_score=0.0,
        risk_level='LOW',
        # Keep first_seen_at and child_initiated — these are factual, not computed
        # Keep shared_groups_count — factual
    )
    print(f"  ✅ Reset {profile_count} profiles to zero/LOW")

    # Delete all snapshots
    print(f"  🗑️  Deleting {snapshot_count} behavioral snapshots...")
    deleted, _ = BehavioralSnapshot.objects.all().delete()
    print(f"  ✅ Deleted {deleted} snapshots")

    print("\n" + "=" * 60)
    print("  ✅ RESET COMPLETE")
    print("     Profiles: zeroed out, risk = LOW")
    print("     Snapshots: deleted")
    print("     Conversations, Messages, ModerationResults: UNTOUCHED")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
