"""
moderation/serializers — Domain-split serializers package.

Re-exports all serializers so existing imports continue to work:
    from moderation.serializers import AegisUserSerializer, ModerationResultSerializer, ...

Split from the original 216-line serializers.py during backend reorganization.
"""

# Package 1: Users
from .users import AegisUserSerializer, ParentProfileSerializer, MonitoredChildSerializer, ParentRegisterSerializer

# Package 2: Messaging
from .messaging import MessageSerializer, ConversationSerializer

# Package 3: Moderation
from .moderation import HarassmentCategorySerializer, ModerationResultSerializer

# Package 4: Behavioral Analysis
from .behavioral import UserBehaviorProfileSerializer, BehavioralSnapshotSerializer

# Package 5: Alerts & Notifications
from .alerts import SecurityAlertSerializer

# Package 6: Chatbot
from .chatbot import ChatMessageSerializer, ChatSessionSerializer

# Package 8: Reports
from .reports import ReportSerializer

# Package 9: Platform Configuration
from .platform import PlatformSettingsSerializer

__all__ = [
    'AegisUserSerializer', 'ParentProfileSerializer', 'MonitoredChildSerializer', 'ParentRegisterSerializer',
    'MessageSerializer', 'ConversationSerializer',
    'HarassmentCategorySerializer', 'ModerationResultSerializer',
    'UserBehaviorProfileSerializer', 'BehavioralSnapshotSerializer',
    'SecurityAlertSerializer',
    'ChatMessageSerializer', 'ChatSessionSerializer',
    'ReportSerializer',
    'PlatformSettingsSerializer',
]
