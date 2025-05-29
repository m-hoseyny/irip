from rest_framework import viewsets, permissions, status, generics, mixins
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from django.contrib.auth import get_user_model
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .serializers import (
    UserSerializer, UserCreateSerializer, 
    UserUpdateSerializer, PasswordChangeSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer
)
from .tokens import email_verification_token, password_reset_token
from .utils import send_verification_email, send_password_reset_email

User = get_user_model()


class UserViewSet(viewsets.GenericViewSet, 
               mixins.CreateModelMixin,
               mixins.UpdateModelMixin):
    """
    API endpoint for users.
    Supports Create, Retrieve, Update, List but NOT Delete operations.
    """
    queryset = User.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        elif self.action in ['retrieve', 'update', 'partial_update', 'change_password']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return User.objects.all()
        return User.objects.filter(id=user.id)
    
    @action(detail=True, methods=['post'], serializer_class=PasswordChangeSerializer)
    def change_password(self, request, pk=None):
        user = self.get_object()
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            # Check old password
            if not user.check_password(serializer.validated_data['old_password']):
                return Response({"old_password": ["Wrong password."]}, 
                                status=status.HTTP_400_BAD_REQUEST)
            
            # Set new password
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({"message": "Password updated successfully"}, 
                            status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
    def perform_create(self, serializer):
        """Override create to send verification email"""
        import logging
        logger = logging.getLogger(__name__)
        
        user = serializer.save()
        success, message = send_verification_email(user, self.request)
        
        if success:
            logger.info(f"Verification email sent during user creation: {message}")
        else:
            logger.error(f"Failed to send verification email during user creation: {message}")
            
        return user
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def resend_verification(self, request, pk=None):
        """Resend verification email"""
        import logging
        logger = logging.getLogger(__name__)
        
        user = self.get_object()
        
        # Check if already verified
        if user.is_verified:
            return Response(
                {"detail": "Email already verified."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Send verification email
        success, message = send_verification_email(user, request)
        
        if success:
            logger.info(f"API resend verification successful: {message}")
            return Response(
                {"detail": "Verification email sent.", "message": message},
                status=status.HTTP_200_OK
            )
        else:
            logger.error(f"API resend verification failed: {message}")
            return Response(
                {"detail": "Failed to send verification email.", "error": message},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    # Security verification is handled by admin only


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def verify_email(request, uidb64, token):
    """Verify email address using token"""
    try:
        # Decode user ID
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = get_object_or_404(User, pk=uid)
        
        # Check token validity
        if email_verification_token.check_token(user, token):
            # Mark email as verified
            user.is_verified = True
            
            # Update KYC status to email verified
            if user.kyc_status == User.KYC_NOT_VERIFIED:
                user.kyc_status = User.KYC_EMAIL_VERIFIED
            
            user.save()
            
            return Response(
                {"detail": "Email verified successfully."},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"detail": "Invalid or expired verification link."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return Response(
            {"detail": "Invalid verification link."},
            status=status.HTTP_400_BAD_REQUEST
        )


@swagger_auto_schema(
    method='post',
    request_body=PasswordResetRequestSerializer,
    responses={
        status.HTTP_200_OK: openapi.Response(
            description="Password reset email sent if the email exists in the system",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'detail': openapi.Schema(
                        type=openapi.TYPE_STRING,
                        example="Password reset email sent if the email exists in our system."
                    )
                }
            )
        ),
        status.HTTP_400_BAD_REQUEST: openapi.Response(
            description="Invalid input",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'email': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_STRING),
                        example=["Enter a valid email address."]
                    )
                }
            )
        )
    },
    operation_description="Send a password reset link to the email address if it exists in the system."
)
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def password_reset_request(request):
    """Send a password reset link to the email address if it exists in the system."""
    
    serializer = PasswordResetRequestSerializer(data=request.data)
    
    if serializer.is_valid():
        email = serializer.validated_data['email']
        
        # Find user by email
        try:
            user = User.objects.get(email=email)
            
            # Send password reset email
            success, message = send_password_reset_email(user, request)
            
            if success:
                return Response(
                    {"detail": "Password reset email sent if the email exists in our system."},
                    status=status.HTTP_200_OK
                )
            else:
                # Log the error but don't expose it to the user for security
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send password reset email: {message}")
                
                # Return success anyway to avoid email enumeration
                return Response(
                    {"detail": "Password reset email sent if the email exists in our system."},
                    status=status.HTTP_200_OK
                )
                
        except User.DoesNotExist:
            # Return success anyway to avoid email enumeration
            return Response(
                {"detail": "Password reset email sent if the email exists in our system."},
                status=status.HTTP_200_OK
            )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    request_body=PasswordResetConfirmSerializer,
    manual_parameters=[
        openapi.Parameter(
            name='uidb64',
            in_=openapi.IN_PATH,
            description='Base64 encoded user ID',
            type=openapi.TYPE_STRING,
            required=True
        ),
        openapi.Parameter(
            name='token',
            in_=openapi.IN_PATH,
            description='Password reset token',
            type=openapi.TYPE_STRING,
            required=True
        ),
    ],
    responses={
        status.HTTP_200_OK: openapi.Response(
            description="Password reset successful",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'detail': openapi.Schema(
                        type=openapi.TYPE_STRING,
                        example="Password has been reset successfully."
                    )
                }
            )
        ),
        status.HTTP_400_BAD_REQUEST: openapi.Response(
            description="Invalid input or token",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'detail': openapi.Schema(
                        type=openapi.TYPE_STRING,
                        example="Invalid or expired password reset link."
                    ),
                    'new_password': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_STRING),
                        example=["Password fields didn't match."]
                    )
                }
            )
        )
    },
    operation_description="Validates the reset token and sets a new password for the user account."
)
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def password_reset_confirm(request, uidb64, token):
    """Validates the reset token and sets a new password for the user account."""
    
    try:
        # Decode user ID
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = get_object_or_404(User, pk=uid)
        
        # Check if token is valid
        if not password_reset_token.check_token(user, token):
            return Response(
                {"detail": "Invalid or expired password reset link."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate new password
        serializer = PasswordResetConfirmSerializer(data=request.data)
        
        if serializer.is_valid():
            # Set new password
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            
            return Response(
                {"detail": "Password has been reset successfully."},
                status=status.HTTP_200_OK
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return Response(
            {"detail": "Invalid password reset link."},
            status=status.HTTP_400_BAD_REQUEST
        )
