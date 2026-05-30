from django.contrib import admin
from moderation.models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ['sender_jid', 'content', 'is_blocked', 'sent_at']
    readonly_fields = ['sent_at']
    show_change_link = True


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'contact_jid', 'child', 'platform',
                    'is_active', 'message_count', 'created_at']
    list_filter = ['platform', 'is_active']
    search_fields = ['contact_jid', 'contact_name', 'child__full_name']
    raw_id_fields = ['child']
    inlines = [MessageInline]

    @admin.display(description='Messages')
    def message_count(self, obj):
        return obj.messages.count()


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['short_content', 'sender_jid', 'is_blocked',
                    'language', 'platform', 'sent_at']
    list_filter = ['is_blocked', 'language', 'platform']
    search_fields = ['content', 'sender_jid', 'platform_message_id']
    raw_id_fields = ['conversation', 'moderation_result']
    readonly_fields = ['sent_at']

    @admin.display(description='Content')
    def short_content(self, obj):
        return obj.content[:80] + '...' if len(obj.content) > 80 else obj.content
