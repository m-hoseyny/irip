from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, permissions, authentication
from rest_framework.decorators import action, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import VPNAccount
from subscription.models import Subscription
from django.utils.translation import gettext_lazy as _
from .serializers import VPNAccountSerializer, VPNAccountConfigSerializer
import logging

logger = logging.getLogger(__name__)


class VPNAccountViewSet(viewsets.ModelViewSet):
    """ViewSet for managing VPN accounts"""
    serializer_class = VPNAccountSerializer
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get_queryset(self):
        """Return VPN accounts for the authenticated user"""
        # Ensure user is authenticated before filtering
        if not self.request.user.is_authenticated:
            # logger.warning(f"Unauthenticated user attempting to access VPNAccountViewSet")
            return VPNAccount.objects.none()
        
        try:
            # Add explicit type check and logging
            logger.debug(f"User type: {type(self.request.user)}, User ID: {self.request.user.id}")
            return VPNAccount.objects.filter(user=self.request.user)
        except Exception as e:
            logger.error(f"Error in VPNAccountViewSet.get_queryset: {str(e)}")
            return VPNAccount.objects.none()
    
    def get_serializer_class(self):
        """Return appropriate serializer class based on the action"""
        if self.action == 'config':
            return VPNAccountConfigSerializer
        return VPNAccountSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a new VPN account for an active subscription"""
        # Ensure user is authenticated
        if not request.user.is_authenticated:
            logger.warning("Unauthenticated user attempting to create VPN account")
            return Response(
                {'error': _('Authentication required')},
                status=status.HTTP_401_UNAUTHORIZED
            )
            
        # Log user information for debugging
        logger.debug(f"User creating VPN account: {request.user.id} ({request.user.email})")
        
        # Check if subscription_id is provided
        subscription_id = request.data.get('subscription_id')
        if not subscription_id:
            return Response(
                {'error': _('Subscription ID is required')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get the subscription and verify it belongs to the user
        try:
            subscription = Subscription.objects.get(
                id=subscription_id,
                user=request.user,
                status__in=['active', 'trialing']
            )
        except Subscription.DoesNotExist:
            return Response(
                {'error': _('Active subscription not found')},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if a VPN account already exists for this subscription
        existing_account = VPNAccount.objects.filter(subscription=subscription).first()
        if existing_account:
            return Response(
                {'error': _('VPN account already exists for this subscription'),
                 'account_id': existing_account.account_id},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create the VPN account
        vpn_account = VPNAccount.create_account_for_subscription(subscription)
        
        if vpn_account:
            # Return the account details
            return Response({
                'success': True,
                'message': _('VPN account created successfully'),
                'account': {
                    'id': vpn_account.id,
                    'account_id': vpn_account.account_id,
                    'email': vpn_account.email,
                    'protocol': vpn_account.protocol,
                    'status': vpn_account.status,
                    'server_ip': vpn_account.server_ip,
                    'port': vpn_account.port,
                    'created_at': vpn_account.created_at
                }
            }, status=status.HTTP_201_CREATED)
        else:
            return Response(
                {'error': _('Failed to create VPN account')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def config(self, request, pk=None):
        """Get the configuration file for a VPN account"""
        vpn_account = self.get_object()
        
        if not vpn_account.config_file:
            return Response(
                {'error': _('Configuration file not available')},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response({
            'config_file': vpn_account.config_file,
            'protocol': vpn_account.protocol
        })
    
    @action(detail=True, methods=['post'])
    def refresh(self, request, pk=None):
        """Refresh usage statistics for a VPN account"""
        vpn_account = self.get_object()
        success = vpn_account.update_usage_stats()
        
        if success:
            return Response({
                'success': True,
                'data_usage_up': vpn_account.data_usage_up,
                'data_usage_down': vpn_account.data_usage_down,
                'updated_at': vpn_account.updated_at
            })
        else:
            return Response(
                {'error': _('Failed to update usage statistics')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a VPN account"""
        vpn_account = self.get_object()
        
        if vpn_account.status != VPNAccount.STATUS_ACTIVE:
            return Response(
                {'error': _('Account is not active')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        success = vpn_account.delete_account()
        
        if success:
            return Response({
                'success': True,
                'message': _('VPN account deactivated successfully')
            })
        else:
            return Response(
                {'error': _('Failed to deactivate VPN account')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
