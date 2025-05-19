from rest_framework import serializers
from .models import StripeProduct, StripePrice, Subscription, PaymentReceipt
from vpn_account.models import VPNAccount
from vpn_account.serializers import VPNAccountSerializer


class StripeProductSerializer(serializers.ModelSerializer):
    """Serializer for StripeProduct model"""
    class Meta:
        model = StripeProduct
        fields = [
            'id', 'name', 'description', 'verification_level', 
            'active', 'created_at', 'updated_at'
        ]
        read_only_fields = fields


class StripePriceSerializer(serializers.ModelSerializer):
    """Serializer for StripePrice model"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_description = serializers.CharField(source='product.description', read_only=True)
    product_verification_level = serializers.CharField(source='product.verification_level', read_only=True)
    formatted_price = serializers.CharField(read_only=True)
    billing_interval = serializers.CharField(source='get_recurring_interval_display', read_only=True)
    
    class Meta:
        model = StripePrice
        fields = [
            'id', 'product', 'product_name', 'product_description', 'product_verification_level', 'price_amount', 'currency',
            'formatted_price', 'recurring_interval', 'billing_interval',
            'active', 'created_at', 'updated_at'
        ]
        read_only_fields = fields


# Using the VPNAccountSerializer from vpn_account app


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for Subscription model"""
    product_name = serializers.CharField(source='price.product.name', read_only=True)
    price_formatted = serializers.CharField(source='price.formatted_price', read_only=True)
    billing_interval = serializers.CharField(source='price.get_recurring_interval_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    days_remaining = serializers.IntegerField(source='days_until_expiration', read_only=True)
    vpn_accounts = VPNAccountSerializer(many=True, read_only=True)
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'user', 'price', 'product_name', 'price_formatted',
            'billing_interval', 'status', 'status_display', 'days_remaining',
            'current_period_start', 'current_period_end',
            'cancel_at_period_end', 'canceled_at',
            'created_at', 'updated_at', 'vpn_accounts'
        ]
        read_only_fields = fields


class PaymentReceiptSerializer(serializers.ModelSerializer):
    """Serializer for PaymentReceipt model"""
    user_email = serializers.CharField(source='user.email', read_only=True)
    subscription_id = serializers.IntegerField(source='subscription.id', read_only=True)
    product_name = serializers.CharField(source='subscription.price.product.name', read_only=True)
    amount_formatted = serializers.CharField(source='formatted_amount', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = PaymentReceipt
        fields = [
            'id', 'user', 'user_email', 'subscription', 'subscription_id', 'product_name',
            'amount_paid', 'amount_formatted', 'currency', 'status', 'status_display',
            'stripe_invoice_id', 'stripe_charge_id', 'invoice_pdf', 'invoice_url',
            'period_start', 'period_end', 'payment_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
