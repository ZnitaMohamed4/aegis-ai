from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.contrib.auth.password_validation import validate_password

from moderation.models import AegisUser, ParentProfile, MonitoredChild


class AegisUserSerializer(serializers.ModelSerializer):
    """Serializer for user details."""
    monitoring_mode = serializers.SerializerMethodField()
    trusted_contact_name = serializers.SerializerMethodField()
    trusted_contact_phone = serializers.SerializerMethodField()

    class Meta:
        model = AegisUser
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'role', 
                  'language_preference', 'phone_number', 'auto_protection_enabled', 
                  'notification_email', 'monitoring_mode', 'trusted_contact_name', 'trusted_contact_phone')
        read_only_fields = ('id', 'role')

    def get_monitoring_mode(self, obj):
        if obj.role == AegisUser.Role.PARENT and hasattr(obj, 'parent_profile'):
            return obj.parent_profile.monitoring_mode
        return 'child'

    def get_trusted_contact_name(self, obj):
        if obj.role == AegisUser.Role.PARENT and hasattr(obj, 'parent_profile'):
            return obj.parent_profile.trusted_contact_name
        return ''

    def get_trusted_contact_phone(self, obj):
        if obj.role == AegisUser.Role.PARENT and hasattr(obj, 'parent_profile'):
            return obj.parent_profile.trusted_contact_phone
        return ''


class ParentProfileSerializer(serializers.ModelSerializer):
    user = AegisUserSerializer(read_only=True)

    class Meta:
        model = ParentProfile
        fields = '__all__'


class MonitoredChildSerializer(serializers.ModelSerializer):
    risk_level = serializers.SerializerMethodField()

    class Meta:
        model = MonitoredChild
        fields = '__all__'

    def get_risk_level(self, obj):
        return obj.get_risk_level()


class ParentRegisterSerializer(serializers.ModelSerializer):
    """Serializer to securely register a new Parent."""
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=AegisUser.objects.all())]
    )
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = AegisUser
        fields = ('username', 'email', 'password', 'password_confirm', 'first_name', 'last_name', 'phone_number')

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        # Remove password_confirm from data
        validated_data.pop('password_confirm')
        
        # Create user (role defaults to PARENT)
        user = AegisUser.objects.create(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone_number=validated_data.get('phone_number', ''),
            role=AegisUser.Role.PARENT
        )
        user.set_password(validated_data['password'])  # Hash the password
        user.save()
        # Profile is created automatically via signal here -> ParentProfile
        return user
