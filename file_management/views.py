from rest_framework import viewsets, permissions, status, mixins
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404

from .models import VerificationPhoto
from .serializers import VerificationPhotoSerializer, VerificationPhotoUploadSerializer
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi


class VerificationPhotoViewSet(mixins.CreateModelMixin,
                              mixins.RetrieveModelMixin,
                              mixins.ListModelMixin,
                              viewsets.GenericViewSet):
    """
    API endpoint for verification photos.
    Allows users to upload photos for verification and check verification status.
    """
    serializer_class = VerificationPhotoSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        # Check if user is authenticated before filtering
        if self.request.user and self.request.user.is_authenticated:
            return VerificationPhoto.objects.filter(user=self.request.user)
        return VerificationPhoto.objects.none()  # Return empty queryset for anonymous users
    
    def get_serializer_class(self):
        if self.action == 'create' or self.action == 'upload':
            return VerificationPhotoUploadSerializer
        return VerificationPhotoSerializer
    
    def perform_create(self, serializer):
        """Set the user when creating a verification photo"""
        serializer.save(user=self.request.user, status=VerificationPhoto.STATUS_PENDING)
    
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                name="photo",
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True,
                description="Upload a photo of yourself holding your ID card. Both your face and ID should be clearly visible."
            )
        ],
        responses={
            status.HTTP_201_CREATED: VerificationPhotoSerializer,
            status.HTTP_400_BAD_REQUEST: 'Bad request',
            status.HTTP_401_UNAUTHORIZED: 'Authentication required'
        },
        consumes=['multipart/form-data']
    )
    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload(self, request):
        """
        Upload a new verification photo for identity verification.
        
        This endpoint allows users to upload a photo of themselves with their ID for verification.
        The photo will be reviewed by an administrator and either approved or rejected.
        
        * If approved, the user's KYC status will be updated to 'security_verified'.
        * If rejected, the user will need to upload a new photo.
        
        Only one pending or verified photo is allowed at a time.
        
        Parameters:
        - photo: Image file (JPG, PNG) of the user with their ID
        """
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED
            )
            
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Check if user already has a pending or verified photo
            existing_photos = VerificationPhoto.objects.filter(
                user=request.user, 
                status__in=[VerificationPhoto.STATUS_PENDING, VerificationPhoto.STATUS_VERIFIED]
            )
            
            if existing_photos.filter(status=VerificationPhoto.STATUS_VERIFIED).exists():
                return Response(
                    {"detail": "You already have a verified photo. No need to upload another one."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if existing_photos.filter(status=VerificationPhoto.STATUS_PENDING).exists():
                return Response(
                    {"detail": "You already have a pending verification photo. Please wait for admin review."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create new verification photo
            self.perform_create(serializer)
            return Response(
                {"detail": "Verification photo uploaded successfully. Please wait for admin review."},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @swagger_auto_schema(
        responses={
            status.HTTP_200_OK: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'has_submitted': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='Whether the user has submitted a verification photo'),
                    'status': openapi.Schema(type=openapi.TYPE_STRING, description='Current status of the verification photo (pending/verified/rejected)'),
                    'status_display': openapi.Schema(type=openapi.TYPE_STRING, description='Human-readable status'),
                    'message': openapi.Schema(type=openapi.TYPE_STRING, description='User-friendly message about the status'),
                    'uploaded_at': openapi.Schema(type=openapi.TYPE_STRING, format='date-time', description='When the photo was uploaded'),
                    'updated_at': openapi.Schema(type=openapi.TYPE_STRING, format='date-time', description='When the status was last updated'),
                    'notes': openapi.Schema(type=openapi.TYPE_STRING, description='Admin notes (if any, usually for rejections)')
                }
            ),
            status.HTTP_401_UNAUTHORIZED: 'Authentication required'
        }
    )
    @action(detail=False, methods=['get'])
    def status(self, request):
        """
        Get the user's verification photo status.
        
        This endpoint returns the status of the user's most recent verification photo submission.
        Possible status values are:
        * pending: Photo is awaiting admin review
        * verified: Photo has been approved by an admin
        * rejected: Photo has been rejected by an admin
        
        If the photo is rejected, the response will include admin notes explaining why.
        
        Returns:
        - has_submitted: Whether the user has submitted a verification photo
        - status: Current status of the verification photo (pending/verified/rejected)
        - status_display: Human-readable status
        - message: User-friendly message about the status
        - uploaded_at: When the photo was uploaded
        - updated_at: When the status was last updated
        - notes: Admin notes (if any, usually for rejections)
        """
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED
            )
            
        # Get the latest verification photo for the user
        latest_photo = VerificationPhoto.objects.filter(user=request.user).order_by('-uploaded_at').first()
        
        if not latest_photo:
            return Response({
                "has_submitted": False,
                "status": None,
                "message": "No verification photo submitted yet."
            })
        
        # Return status information
        status_messages = {
            VerificationPhoto.STATUS_PENDING: "Your verification photo is pending review.",
            VerificationPhoto.STATUS_VERIFIED: "Your verification photo has been approved.",
            VerificationPhoto.STATUS_REJECTED: "Your verification photo was rejected. Please upload a new photo."
        }
        
        return Response({
            "has_submitted": True,
            "status": latest_photo.status,
            "status_display": latest_photo.get_status_display(),
            "message": status_messages.get(latest_photo.status),
            "uploaded_at": latest_photo.uploaded_at,
            "updated_at": latest_photo.updated_at,
            "notes": latest_photo.notes
        })
