import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


# ╔══════════════════════════════════════════════════════════════╗
# ║  UML PACKAGE 1 — USER MANAGEMENT                           ║
# ║  Utilisateur, ProfilParent, UtilisateurMineur               ║
# ╚══════════════════════════════════════════════════════════════╝

class AegisUser(AbstractUser):
    """
    UML: Utilisateur (abstract base) + UtilisateurAdulte
    Custom user model for AEGIS. Replaces Django's default User.
    Roles: 'admin' (platform operator) or 'parent' (child guardian)
    Children are NOT users — they are MonitoredChild data entities.
    """
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Administrator'
        PARENT = 'parent', 'Parent / Guardian'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PARENT)
    language_preference = models.CharField(max_length=5, default='fr',
        help_text="UI language: fr, ar, en")
    phone_number = models.CharField(max_length=20, blank=True, default='',
        help_text="Primary phone for notifications")

    # UtilisateurAdulte fields (applicable to all users)
    auto_protection_enabled = models.BooleanField(default=False,
        help_text="Adult self-protection mode (monitors own messages)")
    notification_email = models.CharField(max_length=255, blank=True, default='',
        help_text="Separate email for alert notifications")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AEGIS User"
        verbose_name_plural = "AEGIS Users"

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"

    def is_admin(self):
        return self.role == self.Role.ADMIN

    def is_parent(self):
        return self.role == self.Role.PARENT

    def get_dashboard_url(self):
        return '/admin' if self.is_admin() else '/parent'


class ParentProfile(models.Model):
    """
    UML: ProfilParent
    Extended settings for parent users — alert preferences, Evolution API linkage.
    One parent can monitor multiple children.
    """
    class MonitoringMode(models.TextChoices):
        CHILD = 'child', 'Child Protection'
        ADULT = 'adult', 'Adult Self-Moderation'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(AegisUser, on_delete=models.CASCADE, related_name='parent_profile')

    monitoring_mode = models.CharField(
        max_length=20,
        choices=MonitoringMode.choices,
        default=MonitoringMode.CHILD,
        help_text="Operating mode: 'child' = protect a minor, 'adult' = self-moderation"
    )

    trusted_contact_phone = models.CharField(
        max_length=20, blank=True, default='',
        help_text="Optional trusted contact for adult self-moderation critical alerts"
    )
    trusted_contact_name = models.CharField(
        max_length=100, blank=True, default='',
        help_text="Name of the trusted contact"
    )

    # Alert preferences
    alert_threshold = models.FloatField(default=0.65,
        help_text="Minimum score to trigger a parent alert (0.0 - 1.0)")
    receive_sms_alerts = models.BooleanField(default=True)
    receive_email_alerts = models.BooleanField(default=True)
    receive_push_alerts = models.BooleanField(default=True)
    receive_call_on_critical = models.BooleanField(default=True,
        help_text="Automatic phone call for CRITICAL severity alerts")

    # Evolution API connection (WhatsApp bridge)
    evolution_instance_name = models.CharField(max_length=255, null=True, blank=True,
        help_text="Evolution API instance name for this parent's WhatsApp bridge")
    evolution_connected = models.BooleanField(default=False,
        help_text="Whether the Evolution API instance is currently connected")
    evolution_connected_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Parent Profile"

    def __str__(self):
        return f"Parent: {self.user.get_full_name() or self.user.username}"

    def get_monitored_children(self):
        return self.children.filter(is_monitored=True)

    def get_pending_alerts(self):
        from .alerts import SecurityAlert
        child_jids = self.children.values_list('whatsapp_jid', flat=True)
        return SecurityAlert.objects.filter(
            moderation_result__sender_jid__in=child_jids,
            is_read=False
        )


class MonitoredChild(models.Model):
    """
    UML: UtilisateurMineur
    A child monitored through a parent's WhatsApp bridge.
    NOT a Django user — children never authenticate.
    """
    class Grade(models.TextChoices):
        PRIMAIRE = 'primaire', 'Primaire'
        COLLEGE = 'college', 'Collège'
        LYCEE = 'lycee', 'Lycée'
        UNIVERSITE = 'universite', 'Université'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent = models.ForeignKey(ParentProfile, on_delete=models.CASCADE, related_name='children')

    # Basic info
    full_name = models.CharField(max_length=255, help_text="Child's display name")
    date_of_birth = models.DateField(null=True, blank=True)
    school_name = models.CharField(max_length=255, blank=True, default='')
    school_level = models.CharField(max_length=20, choices=Grade.choices, blank=True, default='')

    # WhatsApp linkage
    whatsapp_jid = models.CharField(max_length=255, unique=True,
        help_text="WhatsApp JID (e.g., 212612345678@s.whatsapp.net)")
    whatsapp_display_number = models.CharField(max_length=30, blank=True, default='',
        help_text="Formatted display number (e.g., +212 6XX XXX X01)")

    # Monitoring state
    is_monitored = models.BooleanField(default=True)
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Monitored Child"
        verbose_name_plural = "Monitored Children"

    def __str__(self):
        return f"{self.full_name} ({self.whatsapp_display_number or self.whatsapp_jid})"

    def get_risk_level(self):
        """Get risk level based on the number of blocked messages sent to this child's instance."""
        from .moderation import ModerationResult
        from django.utils import timezone
        import datetime
        
        # We can look up all blocked messages associated with this child's parent instance
        # over the last 30 days.
        try:
            thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
            instance_name = self.parent.evolution_instance_name
            if not instance_name:
                return 'LOW'
                
            blocked_count = ModerationResult.objects.filter(
                instance_name=instance_name,
                decision__in=['BLOCK', 'ESCALATE', 'WARN', 'REVISE'],
                created_at__gte=thirty_days_ago
            ).count()
            
            if blocked_count >= 10:
                return 'CRITICAL'
            elif blocked_count >= 5:
                return 'HIGH'
            elif blocked_count >= 1:
                return 'MEDIUM'
            return 'LOW'
        except Exception:
            return 'LOW'
