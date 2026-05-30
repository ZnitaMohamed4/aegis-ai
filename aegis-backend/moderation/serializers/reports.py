from rest_framework import serializers
from moderation.models import Report


class ReportSerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source='child.full_name', read_only=True, default='All Children')
    requested_by = serializers.SerializerMethodField()

    def get_requested_by(self, obj):
        user = obj.requested_by
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        return full_name or user.username or str(user.id)
    
    class Meta:
        model = Report
        fields = '__all__'
