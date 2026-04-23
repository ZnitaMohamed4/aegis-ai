from django.core.management.base import BaseCommand
from moderation.models import UserBehaviorProfile, BehavioralSnapshot, ModerationResult
from django.db import transaction

class Command(BaseCommand):
    help = "Wipe all UserBehaviorProfiles and BehavioralSnapshots to reset Agent 4's memory for the Bayesian Migration."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip the confirmation prompt',
        )
        parser.add_argument(
            '--with-results',
            action='store_true',
            help='Also clear all past ModerationResults (CAUTION: wipes history)',
        )

    def handle(self, *args, **options):
        if not options['force']:
            confirm = input("This will PERMANENTLY delete all behavioral profiles and snapshots. Are you sure? (y/N): ")
            if confirm.lower() != 'y':
                self.stdout.write(self.style.WARNING("Aborted."))
                return

        with transaction.atomic():
            # 1. Clear Snapshots first (Foreign Key dependency)
            snapshot_count = BehavioralSnapshot.objects.count()
            BehavioralSnapshot.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f"Successfully deleted {snapshot_count} BehavioralSnapshots."))

            # 2. Clear Profiles
            profile_count = UserBehaviorProfile.objects.count()
            UserBehaviorProfile.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f"Successfully deleted {profile_count} UserBehaviorProfiles."))

            # 3. Optional: Clear Moderation Results
            if options['with_results']:
                results_count = ModerationResult.objects.count()
                ModerationResult.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f"Successfully deleted {results_count} ModerationResults."))

        self.stdout.write(self.style.SUCCESS("Agent 4 memory has been fully reset. Ready for Bayesian Network profiling."))
