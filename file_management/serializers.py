from rest_framework import serializers
from .models import VerificationPhoto


class VerificationPhotoSerializer(serializers.ModelSerializer):
    """
    Serializer for VerificationPhoto model.
    Used for retrieving verification photo information.
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = VerificationPhoto
        fields = ('id', 'photo', 'status', 'status_display', 'notes', 'uploaded_at', 'updated_at')
        read_only_fields = ('id', 'status', 'status_display', 'notes', 'uploaded_at', 'updated_at')


class VerificationPhotoUploadSerializer(serializers.ModelSerializer):
    """
    Serializer for uploading a new verification photo.
    """
    photo = serializers.ImageField(
        help_text="Upload a photo of yourself holding your ID card. Both your face and ID should be clearly visible.",
        required=True
    )
    
    class Meta:
        model = VerificationPhoto
        fields = ('photo',)
