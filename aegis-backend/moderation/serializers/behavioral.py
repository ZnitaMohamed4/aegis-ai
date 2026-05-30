from rest_framework import serializers
from moderation.models import UserBehaviorProfile, BehavioralSnapshot


class UserBehaviorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserBehaviorProfile
        fields = '__all__'


class BehavioralSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = BehavioralSnapshot
        fields = '__all__'
