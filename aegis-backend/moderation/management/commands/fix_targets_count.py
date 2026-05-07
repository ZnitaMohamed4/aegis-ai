"""
Management command: Recalculate unique_targets_count for all UserBehaviorProfile records.

Fixes the bug where unique_targets_count counted distinct instance_name strings
instead of actual MonitoredChild records. This inflated numbers (e.g., 41 instead of 1)
and corrupted the Bayesian Network's TargetBreadth evidence.

Usage:
    python manage.py fix_targets_count
    python manage.py fix_targets_count --dry-run   # Preview without saving

SAFE: This command does NOT delete any messages or moderation results.
It only updates the unique_targets_count field on UserBehaviorProfile records.
"""
from django.core.management.base import BaseCommand
from moderation.models import UserBehaviorProfile, ModerationResult, MonitoredChild


class Command(BaseCommand):
    help = "Recalculate unique_targets_count using real MonitoredChild records (fixes inflation bug)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without saving to the database',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        profiles = UserBehaviorProfile.objects.all()
        total = profiles.count()
        fixed = 0

        self.stdout.write(f"\n{'[DRY RUN] ' if dry_run else ''}Recalculating unique_targets_count for {total} profiles...\n")

        for profile in profiles:
            old_value = profile.unique_targets_count

            # Get distinct instance_names this sender has talked to
            sender_instances = set(
                ModerationResult.objects.filter(sender_jid=profile.user_jid)
                .values_list('instance_name', flat=True).distinct()
            )

            # Map to real MonitoredChild records
            real_children_count = MonitoredChild.objects.filter(
                parent__evolution_instance_name__in=sender_instances
            ).count()

            new_value = real_children_count if real_children_count > 0 else min(len(sender_instances), 5)

            if old_value != new_value:
                fixed += 1
                self.stdout.write(
                    f"  {profile.user_jid}: {old_value} → {new_value}"
                    f"  (instances={len(sender_instances)}, real_children={real_children_count})"
                )
                if not dry_run:
                    profile.unique_targets_count = new_value
                    profile.save(update_fields=['unique_targets_count'])

        action = "would be fixed" if dry_run else "fixed"
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Done! {fixed}/{total} profiles {action}."
            f"\n   No messages were deleted. Only unique_targets_count was updated."
        ))
