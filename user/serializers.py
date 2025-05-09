from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework.validators import UniqueValidator

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the User model.
    Used for retrieving user information.
    """
    kyc_status_display = serializers.CharField(source='get_kyc_status_display', read_only=True)
    verification_photo_status = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'is_verified', 'kyc_status', 'kyc_status_display',
                  'phone_number', 'address', 'profile_picture', 'date_of_birth', 'social_security_number',
                  'verification_photo_status')
        read_only_fields = ('id', 'is_verified', 'kyc_status', 'kyc_status_display', 'verification_photo_status')
    
    def get_verification_photo_status(self, obj):
        """Get the status of the user's verification photo"""
        from file_management.models import VerificationPhoto
        
        # Get the latest verification photo for the user
        latest_photo = VerificationPhoto.objects.filter(user=obj).order_by('-uploaded_at').first()
        
        if not latest_photo:
            return {
                "has_submitted": False,
                "status": None,
                "message": "No verification photo submitted yet."
            }
        
        # Return status information
        status_messages = {
            VerificationPhoto.STATUS_PENDING: "Your verification photo is pending review.",
            VerificationPhoto.STATUS_VERIFIED: "Your verification photo has been approved.",
            VerificationPhoto.STATUS_REJECTED: "Your verification photo was rejected. Please upload a new photo."
        }
        
        return {
            "has_submitted": True,
            "status": latest_photo.status,
            "status_display": latest_photo.get_status_display(),
            "message": status_messages.get(latest_photo.status),
            "uploaded_at": latest_photo.uploaded_at,
            "updated_at": latest_photo.updated_at,
            "notes": latest_photo.notes if latest_photo.notes else None
        }


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new user.
    Includes password validation and confirmation.
    """
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'password_confirm',
                  'first_name', 'last_name', 'phone_number', 'address', 'date_of_birth', 'social_security_number')
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True}
        }

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password_confirm'):
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            password=validated_data['password']
        )

        # Add optional fields if provided
        if 'phone_number' in validated_data:
            user.phone_number = validated_data['phone_number']
        if 'address' in validated_data:
            user.address = validated_data['address']
        if 'date_of_birth' in validated_data:
            user.date_of_birth = validated_data['date_of_birth']
        if 'social_security_number' in validated_data:
            user.social_security_number = validated_data['social_security_number']
        
        user.save()
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user information.
    """
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'phone_number', 'address', 'date_of_birth', 'profile_picture', 'social_security_number')


class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for changing user password.
    """
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "Password fields didn't match."})
        return attrs
