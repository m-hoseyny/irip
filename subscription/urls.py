from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'subscription'

# Create a router for DRF viewsets
router = DefaultRouter()
router.register(r'subscriptions', views.SubscriptionViewSet, basename='subscription')
router.register(r'products', views.StripeProductViewSet, basename='product')
router.register(r'prices', views.StripePriceViewSet, basename='price')
router.register(r'receipts', views.PaymentReceiptViewSet, basename='receipt')

# URL patterns for the subscription app - API endpoints only
urlpatterns = [
    # API endpoints
    path('', include(router.urls)),
    path('webhook/', views.stripe_webhook, name='webhook'),
    
    # Admin actions
    path('subscription/<int:subscription_id>/cancel-admin/', views.admin_cancel_subscription, name='admin-cancel-subscription'),
]
