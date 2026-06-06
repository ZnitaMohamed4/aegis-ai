from django.contrib import admin

# Import all domain admins to register them
from .users import AegisUserAdmin, ParentProfileAdmin, MonitoredChildAdmin
from .messaging import ConversationAdmin, MessageAdmin
from .moderation import HarassmentCategoryAdmin, ModerationResultAdmin
from .behavioral import UserBehaviorProfileAdmin, BehavioralSnapshotAdmin
from .alerts import SecurityAlertAdmin
from .chatbot import ChatSessionAdmin, ChatMessageAdmin
from .platform import FailedMessageAdmin

# ── Admin Site Customization ──
admin.site.site_header = "🛡️ AEGIS AI — Administration"
admin.site.site_title = "AEGIS Admin"
admin.site.index_title = "Moderation & Monitoring Platform"

__all__ = [
    'AegisUserAdmin', 'ParentProfileAdmin', 'MonitoredChildAdmin',
    'ConversationAdmin', 'MessageAdmin',
    'HarassmentCategoryAdmin', 'ModerationResultAdmin',
    'UserBehaviorProfileAdmin', 'BehavioralSnapshotAdmin',
    'SecurityAlertAdmin',
    'ChatSessionAdmin', 'ChatMessageAdmin',
    'FailedMessageAdmin',
]
