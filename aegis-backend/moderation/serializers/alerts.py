from rest_framework import serializers
from moderation.models import SecurityAlert


class SecurityAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityAlert
        fields = '__all__'
