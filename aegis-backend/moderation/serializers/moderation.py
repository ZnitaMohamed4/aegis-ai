from rest_framework import serializers
from moderation.models import HarassmentCategory, ModerationResult


class HarassmentCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = HarassmentCategory
        fields = '__all__'


class ModerationResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModerationResult
        fields = '__all__'
