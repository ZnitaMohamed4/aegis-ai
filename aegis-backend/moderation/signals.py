"""
Signals for the moderation app.
Auto-creates a ParentProfile whenever an AegisUser with role='parent' is saved.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import AegisUser, ParentProfile


@receiver(post_save, sender=AegisUser)
def create_parent_profile(sender, instance, created, **kwargs):
    """
    Automatically create a ParentProfile when a parent user is created.
    Also handles the case where an existing user's role is changed to 'parent'.
    """
    if instance.role == AegisUser.Role.PARENT:
        ParentProfile.objects.get_or_create(user=instance)
