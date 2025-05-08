from rest_framework import viewsets, permissions, status, generics, mixins
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from django.contrib.auth import get_user_model
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.shortcuts import get_object_or_404
from .serializers import (
    UserSerializer, UserCreateSerializer, 
    UserUpdateSerializer, PasswordChangeSerializer
)
from .tokens import email_verification_token
from .utils import send_verification_email

User = get_user_model()


class UserViewSet(viewsets.GenericViewSet, 
               mixins.CreateModelMixin,
               mixins.RetrieveModelMixin,
               mixins.UpdateModelMixin,
               mixins.ListModelMixin):
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
        return [permissions.IsAdminUser()]
    
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
        user = serializer.save()
        send_verification_email(user, self.request)
        return user
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def resend_verification(self, request, pk=None):
        """Resend verification email"""
        user = self.get_object()
        
        # Check if already verified
        if user.is_verified:
            return Response(
                {"detail": "Email already verified."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Send verification email
        send_verification_email(user, request)
        
        return Response(
            {"detail": "Verification email sent."},
            status=status.HTTP_200_OK
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
