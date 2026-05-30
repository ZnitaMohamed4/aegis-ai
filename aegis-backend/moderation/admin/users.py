from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from moderation.models import AegisUser, ParentProfile, MonitoredChild


class ParentProfileInline(admin.StackedInline):
    model = ParentProfile
    can_delete = False
    verbose_name_plural = "Parent Profile"
    fk_name = "user"
    extra = 0


@admin.register(AegisUser)
class AegisUserAdmin(UserAdmin):
    """Custom admin for AegisUser — extends Django's built-in UserAdmin."""
    list_display = ['username', 'email', 'first_name', 'last_name', 'role_badge',
                    'is_active', 'is_staff', 'created_at']
    list_filter = ['role', 'is_active', 'is_staff', 'is_superuser', 'language_preference']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'phone_number']
    ordering = ['-created_at']
    inlines = [ParentProfileInline]

    # Add our custom fields to the existing UserAdmin fieldsets
    fieldsets = UserAdmin.fieldsets + (
        ('AEGIS Settings', {
            'fields': ('role', 'language_preference', 'phone_number',
                       'auto_protection_enabled', 'notification_email'),
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('AEGIS Settings', {
            'fields': ('role', 'language_preference', 'phone_number'),
        }),
    )

    @admin.display(description='Role')
    def role_badge(self, obj):
        colors = {'admin': '#e74c3c', 'parent': '#3498db'}
        bg = colors.get(obj.role, '#95a5a6')
        return format_html(
            '<span style="background:{}; color:white; padding:3px 10px; '
            'border-radius:12px; font-size:11px; font-weight:bold;">{}</span>',
            bg, obj.get_role_display()
        )


@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'alert_threshold', 'evolution_instance_name',
                    'evolution_connected', 'receive_sms_alerts', 'created_at']
    list_filter = ['evolution_connected', 'receive_sms_alerts', 'receive_email_alerts']
    search_fields = ['user__username', 'user__email', 'evolution_instance_name']
    raw_id_fields = ['user']


@admin.register(MonitoredChild)
class MonitoredChildAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'parent', 'whatsapp_jid', 'school_name',
                    'school_level', 'is_monitored', 'linked_at']
    list_filter = ['is_monitored', 'school_level']
    search_fields = ['full_name', 'whatsapp_jid', 'whatsapp_display_number',
                     'parent__user__username']
    raw_id_fields = ['parent']
    readonly_fields = ['linked_at']
