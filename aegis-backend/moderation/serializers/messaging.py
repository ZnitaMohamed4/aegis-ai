from rest_framework import serializers
from moderation.models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = '__all__'


class ConversationSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    blocked_count = serializers.SerializerMethodField()
    total_messages = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = '__all__'

    def get_last_message(self, obj):
        msg = obj.get_last_message()
        return MessageSerializer(msg).data if msg else None

    def get_blocked_count(self, obj):
        return obj.get_blocked_count()

    def get_total_messages(self, obj):
        return obj.messages.count()
