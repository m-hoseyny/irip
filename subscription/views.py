import logging
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

import stripe
import json

from .models import StripeProduct, StripePrice, Subscription, StripeCustomer, PaymentReceipt
from .utils import (
    create_checkout_session,
    handle_checkout_completed,
    handle_subscription_updated,
    handle_subscription_deleted,
    handle_invoice_event,
    handle_invoice_paid,
    handle_invoice_payment_failed,
    cancel_subscription,
    is_eligible_for_product,
    sync_stripe_products
)
from .serializers import (
    StripeProductSerializer,
    StripePriceSerializer,
    SubscriptionSerializer,
    PaymentReceiptSerializer
)

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """API viewset for user subscriptions"""
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Check if this is a schema generation request
        if getattr(self, 'swagger_fake_view', False):
            # Return empty queryset for schema generation
            return Subscription.objects.none()
        
        # Normal request with authenticated user
        return Subscription.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a subscription at the end of the current period"""
        # Check if this is a schema generation request
        if getattr(self, 'swagger_fake_view', False):
            return Response({"message": "Subscription will be canceled at the end of the current billing period"})
            
        subscription = self.get_object()
        
        # Make sure the subscription belongs to the user
        if subscription.user != request.user:
            return Response(
                {"error": "You do not have permission to cancel this subscription"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Cancel the subscription
        success, message = cancel_subscription(subscription.id)
        
        if success:
            return Response({"message": message})
        else:
            return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)


class StripeProductViewSet(viewsets.ReadOnlyModelViewSet):
    """API viewset for Stripe products"""
    serializer_class = StripeProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = StripeProduct.objects.filter(active=True)
    
    def list(self, request, *args, **kwargs):
        """List all active products (no eligibility filtering)"""
        # Check if this is a schema generation request
        if getattr(self, 'swagger_fake_view', False):
            # Return standard response for schema generation
            return super().list(request, *args, **kwargs)

        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)



class StripePriceViewSet(viewsets.ReadOnlyModelViewSet):
    """API viewset for Stripe prices"""
    serializer_class = StripePriceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # For schema generation, return an empty queryset
        if getattr(self, 'swagger_fake_view', False):
            return StripePrice.objects.none()
            
        return StripePrice.objects.filter(active=True)
    
    @swagger_auto_schema(
        method='post',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'success_url': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='URL to redirect to after successful checkout',
                    example='https://yourdomain.com/success/'
                ),
                'cancel_url': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='URL to redirect to if checkout is canceled',
                    example='https://yourdomain.com/cancel/'
                ),
            },
            required=[],  # Both are optional, as there are defaults in settings
        ),
        responses={
            200: openapi.Response(
                description="Stripe Checkout session created",
                examples={
                    "application/json": {"id": "cs_test_123", "url": "https://checkout.stripe.com/pay/cs_test_123"}
                }
            ),
            403: 'Not eligible for this product',
            400: 'Invalid request or Stripe error',
        }
    )
    @action(detail=True, methods=['post'])
    def checkout(self, request, pk=None):
        """Create a checkout session for a price"""
        # Check if this is a schema generation request
        if getattr(self, 'swagger_fake_view', False):
            return Response({"id": "schema_generation", "url": "https://example.com/checkout"})
            
        price = self.get_object()
        user = request.user
        
        # Check if the user is eligible for this product
        if not is_eligible_for_product(user, price.product):
            return Response(
                {"error": "You are not eligible for this product. Please complete the required verification."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            success_url = request.data.get('success_url', settings.STRIPE_SUCCESS_URL)
            cancel_url = request.data.get('cancel_url', settings.STRIPE_CANCEL_URL)
            
            # Create checkout session
            session = create_checkout_session(
                user=user,
                price_id=price.id,
                success_url=success_url,
                cancel_url=cancel_url
            )
            
            return Response({"id": session.id, "url": session.url})
            
        except Exception as e:
            logger.error(f"Error creating checkout session: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class CheckoutVerificationViewSet(viewsets.ViewSet):
    """API viewset for verifying checkout sessions"""
    permission_classes = [permissions.IsAuthenticated]
    
    # Define the session_id parameter for Swagger documentation
    session_id_param = openapi.Parameter(
        'session_id',
        openapi.IN_QUERY,
        description="Stripe Checkout Session ID to verify",
        type=openapi.TYPE_STRING,
        required=True
    )
    
    # Define the response schema
    response_schema = openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'session_status': openapi.Schema(type=openapi.TYPE_STRING, description="Status of the checkout session (e.g., 'complete', 'open')"),
            'payment_status': openapi.Schema(type=openapi.TYPE_STRING, description="Status of the payment (e.g., 'paid', 'unpaid')"),
            'subscription': openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'status': openapi.Schema(type=openapi.TYPE_STRING),
                    'current_period_end': openapi.Schema(type=openapi.TYPE_STRING, format='date-time'),
                    'product_name': openapi.Schema(type=openapi.TYPE_STRING),
                    'price_formatted': openapi.Schema(type=openapi.TYPE_STRING),
                }
            )
        }
    )
    
    @swagger_auto_schema(
        method='get',
        manual_parameters=[session_id_param],
        responses={200: response_schema}
    )
    @action(detail=False, methods=['get'])
    def verify(self, request):
        """Verify a checkout session and return subscription status
        
        Provide the session_id as a query parameter in the URL.
        
        Example:
        GET /api/v1/subscription/checkout/verify/?session_id=cs_test_a1b2c3...
        """
        # Get session_id from query parameters
        session_id = request.query_params.get('session_id')
        
        if not session_id:
            return Response(
                {"error": "session_id is required as a query parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Retrieve the checkout session from Stripe
            checkout_session = stripe.checkout.Session.retrieve(
                session_id,
                expand=['subscription']
            )
            
            # Check if the session belongs to the current user
            stripe_customer = StripeCustomer.objects.filter(user=request.user).first()
            if not stripe_customer or stripe_customer.stripe_customer_id != checkout_session.customer:
                return Response(
                    {"error": "This checkout session does not belong to you"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get subscription information
            subscription_data = None
            subscription_id = checkout_session.get('subscription')
            
            if subscription_id:
                # Check if we have this subscription in our database
                subscription = Subscription.objects.filter(
                    stripe_subscription_id=subscription_id
                ).first()
                
                if subscription:
                    serializer = SubscriptionSerializer(subscription)
                    subscription_data = serializer.data
                else:
                    # If webhook hasn't processed it yet, get basic info from Stripe
                    subscription_obj = checkout_session.subscription
                    subscription_data = {
                        'status': subscription_obj.status,
                        'current_period_end': datetime.fromtimestamp(subscription_obj.current_period_end).isoformat(),
                        'stripe_subscription_id': subscription_obj.id
                    }
            
            # Return the session status and subscription info
            return Response({
                'session_status': checkout_session.status,
                'payment_status': checkout_session.payment_status,
                'subscription': subscription_data
            })
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error verifying checkout: {str(e)}")
            return Response(
                {"error": f"Stripe error: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error verifying checkout: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            return Response({"id": "schema_generation", "url": "https://example.com/checkout"})
            
        price = self.get_object()
        user = request.user
        
        # Check if the user is eligible for this product
        if not is_eligible_for_product(user, price.product):
            return Response(
                {"error": "You are not eligible for this product. Please complete the required verification."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            success_url = request.data.get('success_url', settings.STRIPE_SUCCESS_URL)
            cancel_url = request.data.get('cancel_url', settings.STRIPE_CANCEL_URL)
            
            # Create checkout session
            session = create_checkout_session(
                user=user,
                price_id=price.id,
                success_url=success_url,
                cancel_url=cancel_url
            )
            
            return Response({"id": session.id, "url": session.url})
            
        except Exception as e:
            logger.error(f"Error creating checkout session: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Webhook handler for Stripe events"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        logger.error(f"Invalid Stripe webhook payload: {str(e)}")
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logger.error(f"Invalid Stripe webhook signature: {str(e)}")
        return JsonResponse({'error': 'Invalid signature'}, status=400)
    
    # Handle the event
    try:
        if event.type == 'checkout.session.completed':
            session = event.data.object
            logger.info(f"Checkout session completed: {session.id}")
            handle_checkout_completed(session)
            
        elif event.type == 'customer.subscription.updated':
            subscription = event.data.object
            logger.info(f"Subscription updated: {subscription.id}")
            handle_subscription_updated(subscription)
            
        elif event.type == 'customer.subscription.deleted':
            subscription = event.data.object
            logger.info(f"Subscription deleted: {subscription.id}")
            handle_subscription_deleted(subscription)
            
        # Handle invoice events to store receipts
        elif event.type == 'invoice.created' or event.type == 'invoice.updated':
            invoice = event.data.object
            logger.info(f"Invoice {event.type}: {invoice.id}")
            handle_invoice_event(invoice)
            
        # Handle invoice payment events
        elif event.type == 'invoice.paid':
            invoice = event.data.object
            logger.info(f"Invoice paid: {invoice.id}")
            handle_invoice_paid(invoice)
            
        # Handle invoice payment failure
        elif event.type == 'invoice.payment_failed':
            invoice = event.data.object
            logger.info(f"Invoice payment failed: {invoice.id}")
            handle_invoice_payment_failed(invoice)
            
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Error handling Stripe webhook: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


# Admin views
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages as django_messages

@staff_member_required
def admin_cancel_subscription(request, subscription_id):
    """Admin view to cancel a subscription"""
    from .utils import cancel_subscription
    
    # Get the subscription
    subscription = get_object_or_404(Subscription, id=subscription_id)
    
    # Check if already canceled or not active
    if subscription.cancel_at_period_end:
        django_messages.warning(request, f"Subscription for {subscription.user.email} is already scheduled for cancellation.")
        return redirect('admin:subscription_subscription_changelist')
        
    if subscription.status != 'active':
        django_messages.warning(request, f"Cannot cancel subscription for {subscription.user.email} as it is not active.")
        return redirect('admin:subscription_subscription_changelist')
    
    # Cancel the subscription
    success, message = cancel_subscription(subscription.id)
    
    if success:
        django_messages.success(request, f"Successfully canceled subscription for {subscription.user.email}. {message}")
    else:
        django_messages.error(request, f"Error canceling subscription for {subscription.user.email}: {message}")
    
    return redirect('admin:subscription_subscription_changelist')


# No dashboard views needed, focusing only on API endpoints


class PaymentReceiptViewSet(viewsets.ReadOnlyModelViewSet):
    """API viewset for payment receipts"""
    serializer_class = PaymentReceiptSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # For schema generation, return an empty queryset
        if getattr(self, 'swagger_fake_view', False):
            return PaymentReceipt.objects.none()
        
        # Return only receipts for the authenticated user
        return PaymentReceipt.objects.filter(user=self.request.user)
