import uuid
from django.db import models
from django.utils import timezone


# ╔══════════════════════════════════════════════════════════════╗
# ║  UML PACKAGE 4 — BEHAVIORAL ANALYSIS                       ║
# ║  UserBehaviorProfile, BehavioralSnapshot                    ║
# ╚══════════════════════════════════════════════════════════════╝

class UserBehaviorProfile(models.Model):
    """
    UML Package 4: ProfilComportementalUtilisateur
    Tracks risk level for each unique sender over time.
    Enhanced with UML fields for harasser profiling.
    """
    class RiskLevel(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        CRITICAL = 'CRITICAL', 'Critical'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_jid = models.CharField(max_length=255, unique=True)

    # UML-aligned counters
    total_messages_sent = models.IntegerField(default=0)
    total_blocked_messages_sent = models.IntegerField(default=0,
        help_text="Messages sent by this user that were blocked")
    total_blocked_messages_received = models.IntegerField(default=0,
        help_text="Blocked messages received by this user (victim metric)")
    block_ratio = models.FloatField(default=0.0,
        help_text="Ratio of blocked to total messages (0.0 - 1.0)")
    average_toxicity_score = models.FloatField(default=0.0)
    escalation_count = models.IntegerField(default=0,
        help_text="Number of ESCALATE decisions for this user")
    night_activity_ratio = models.FloatField(default=0.0,
        help_text="Ratio of messages sent between 22h-06h")
    unique_targets_count = models.IntegerField(default=0,
        help_text="Number of different people this user has harassed (harasser profiling)")
    repeated_harassers_count = models.IntegerField(default=0,
        help_text="Number of distinct harassers who targeted this user 3+ times (victim profiling)")

    # --- Tier 2 Features (Digital Twin Extended) ---
    message_frequency_1h = models.FloatField(default=0.0, help_text="Messages in last hour")
    avg_message_length = models.FloatField(default=0.0, help_text="Typical message length")
    first_seen_at = models.DateTimeField(default=timezone.now, null=True, help_text="Account age (can be backdated via WhatsApp history)")
    child_initiated = models.BooleanField(default=False, help_text="True if the child sent the very first message in the relationship")
    shared_groups_count = models.IntegerField(default=0, help_text="Number of shared WhatsApp groups (synced by background task)")
    shared_groups_metadata = models.JSONField(default=list, blank=True,
        help_text="Group details: [{group_jid, group_name, created_at, participant_count}, ...]")
    burst_count_24h = models.IntegerField(default=0, help_text="Number of burst episodes in 24h (5+ msgs in 10 mins)")
    max_toxicity_24h = models.FloatField(default=0.0, help_text="Worst toxicity score today")
    upward_corrections_total = models.IntegerField(default=0, help_text="Times Agent 3 escalated ML decision")
    downward_corrections_total = models.IntegerField(default=0, help_text="Times Agent 3 de-escalated ML decision")
    llm_triggers_total = models.IntegerField(default=0, help_text="Total times Agent 3 was triggered")

    # Risk assessment
    risk_score = models.FloatField(default=0.0)
    risk_level = models.CharField(max_length=20, choices=RiskLevel.choices, default=RiskLevel.LOW)

    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Behavior Profile"

    def __str__(self):
        return f"{self.user_jid} - Risk: {self.risk_level}"


class BehavioralSnapshot(models.Model):
    """
    UML: SnapshotComportemental
    Daily snapshot of a user's behavioral metrics for historical tracking.
    Enhanced with Bayesian Network pathway probabilities.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(UserBehaviorProfile, on_delete=models.CASCADE,
        related_name='snapshots')

    date_snapshot = models.DateField(help_text="Date this snapshot was taken")
    message_count = models.IntegerField(default=0)
    blocked_count = models.IntegerField(default=0)
    risk_score_snapshot = models.FloatField(default=0.0)
    peak_risk_score = models.FloatField(default=0.0, help_text="Highest risk score observed today")
    peak_risk_time = models.DateTimeField(null=True, blank=True, help_text="When the peak occurred")
    snapshot_count = models.IntegerField(default=0, help_text="Number of updates today")

    # Bayesian Network output — populated by Agent 4 after BN inference
    risk_level = models.CharField(max_length=20, default='LOW',
        help_text="BN-inferred risk level (LOW/MEDIUM/HIGH/CRITICAL)")
    archetype = models.CharField(max_length=40, default='Normal User',
        help_text="BN archetype classification (Normal User, Groomer Pattern, Bully Pattern, Troll Pattern)")
    grooming_prob = models.FloatField(default=0.0, help_text="P(GroomingRisk=HIGH) from Bayesian inference")
    bully_prob = models.FloatField(default=0.0, help_text="P(BullyRisk=HIGH) from Bayesian inference")
    troll_prob = models.FloatField(default=0.0, help_text="P(TrollRisk=HIGH) from Bayesian inference")

    # Link to triggering alert
    alert_id = models.CharField(max_length=50, null=True, blank=True,
        help_text="SecurityAlert ID that triggered this snapshot update")

    class Meta:
        verbose_name = "Behavioral Snapshot"
        unique_together = [('profile', 'date_snapshot')]
        ordering = ['-date_snapshot']

    def __str__(self):
        return f"{self.profile.user_jid} @ {self.date_snapshot} ({self.archetype}, risk: {self.risk_score_snapshot:.2f})"
