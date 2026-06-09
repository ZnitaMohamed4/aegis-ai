"""
moderation/models — Domain-split model package.

Re-exports all models so existing imports continue to work:
    from moderation.models import AegisUser, ModerationResult, ...

Split from the original 997-line models.py during backend reorganization.
"""

# Package 1: User Management
from .users import AegisUser, ParentProfile, MonitoredChild

# Package 2: Messaging
from .messaging import Conversation, Message

# Package 3: Moderation
from .moderation import HarassmentCategory, ModerationResult

# Package 4: Behavioral Analysis
from .behavioral import UserBehaviorProfile, BehavioralSnapshot

# Package 5: Alerts & Notifications
from .alerts import SecurityAlert, Notification

# Package 6: Chatbot & Bot Memory
from .chatbot import ChatSession, ChatMessage, BotConversation

# Package 7–9: Platform (BlockedContact, Report, PlatformSettings, SelfModerationEvent, FailedMessage)
from .platform import BlockedContact, Report, PlatformSettings, SelfModerationEvent, FailedMessage

# Package 10: Knowledge Base
from .knowledge import IndexedDocument

__all__ = [
    'AegisUser', 'ParentProfile', 'MonitoredChild',
    'Conversation', 'Message',
    'HarassmentCategory', 'ModerationResult',
    'UserBehaviorProfile', 'BehavioralSnapshot',
    'SecurityAlert', 'Notification',
    'ChatSession', 'ChatMessage', 'BotConversation',
    'BlockedContact', 'Report', 'PlatformSettings', 'SelfModerationEvent',
    'FailedMessage',
    'IndexedDocument',
]
