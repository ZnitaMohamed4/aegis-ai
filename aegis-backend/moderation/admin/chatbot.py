from django.contrib import admin
from moderation.models import ChatSession, ChatMessage


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ['sent_at']


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'user', 'language', 'is_active',
                    'message_count', 'started_at', 'ended_at']
    list_filter = ['language', 'is_active']
    search_fields = ['user__username']
    raw_id_fields = ['user']
    inlines = [ChatMessageInline]

    @admin.display(description='Messages')
    def message_count(self, obj):
        return obj.messages.count()


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['short_content', 'role', 'session', 'sent_at']
    list_filter = ['role']
    search_fields = ['content']
    raw_id_fields = ['session']
    readonly_fields = ['sent_at']

    @admin.display(description='Content')
    def short_content(self, obj):
        return obj.content[:80] + '...' if len(obj.content) > 80 else obj.content
