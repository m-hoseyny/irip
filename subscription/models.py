from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import stripe
from datetime import datetime


class StripeProduct(models.Model):
    """Represents a product in Stripe"""
    name = models.CharField(_('Name'), max_length=100)
    stripe_product_id = models.CharField(_('Stripe Product ID'), max_length=100, unique=True)
    description = models.TextField(_('Description'), blank=True)
    active = models.BooleanField(_('Active'), default=True)
    
    # The required verification level to subscribe to this product
    VERIFICATION_LEVEL_CHOICES = [
        ('email_verified', _('Email Verified')),
        ('security_verified', _('Security Verified')),
    ]
    verification_level = models.CharField(
        _('Required Verification Level'),
        max_length=20,
        choices=VERIFICATION_LEVEL_CHOICES,
        default='email_verified',
        help_text=_('The verification level required to subscribe to this product')
    )
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        verbose_name = _('Stripe Product')
        verbose_name_plural = _('Stripe Products')
    
    def __str__(self):
        return self.name


class StripePrice(models.Model):
    """Represents a price for a product in Stripe"""
    product = models.ForeignKey(
        StripeProduct, 
        on_delete=models.CASCADE, 
        related_name='prices',
        verbose_name=_('Product')
    )
    
    stripe_price_id = models.CharField(_('Stripe Price ID'), max_length=100, unique=True)
    
    INTERVAL_CHOICES = [
        ('month', _('Monthly')),
        ('year', _('Yearly')),
    ]
    recurring_interval = models.CharField(
        _('Billing Interval'),
        max_length=10,
        choices=INTERVAL_CHOICES,
        default='month'
    )
    
    # Price stored in cents (e.g., $10.99 = 1099)
    price_amount = models.IntegerField(_('Price Amount (in cents)'))
    currency = models.CharField(_('Currency'), max_length=3, default='USD')
    active = models.BooleanField(_('Active'), default=True)
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        verbose_name = _('Stripe Price')
        verbose_name_plural = _('Stripe Prices')
    
    def __str__(self):
        return f"{self.product.name} - {self.get_recurring_interval_display()} (${self.price_amount/100} {self.currency})"
    
    @property
    def formatted_price(self):
        """Return formatted price with currency"""
        return f"${self.price_amount/100:.2f} {self.currency}"


class Subscription(models.Model):
    """Represents a user's subscription"""
    STATUS_CHOICES = [
        ('active', _('Active')),
        ('past_due', _('Past Due')),
        ('canceled', _('Canceled')),
        ('incomplete', _('Incomplete')),
        ('incomplete_expired', _('Incomplete Expired')),
        ('trialing', _('Trialing')),
        ('unpaid', _('Unpaid')),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='subscriptions',
        verbose_name=_('User')
    )
    
    stripe_subscription_id = models.CharField(_('Stripe Subscription ID'), max_length=100, unique=True)
    stripe_customer_id = models.CharField(_('Stripe Customer ID'), max_length=100)
    
    price = models.ForeignKey(
        StripePrice, 
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name=_('Price')
    )
    
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='incomplete')
    current_period_start = models.DateTimeField(_('Current Period Start'))
    current_period_end = models.DateTimeField(_('Current Period End'))
    
    cancel_at_period_end = models.BooleanField(_('Cancel at Period End'), default=False)
    canceled_at = models.DateTimeField(_('Canceled At'), null=True, blank=True)
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        verbose_name = _('Subscription')
        verbose_name_plural = _('Subscriptions')
    
    def __str__(self):
        return f"{self.user.email} - {self.price.product.name if self.price else 'Unknown'}"
    
    @property
    def is_active(self):
        """Return True if subscription is active"""
        return self.status == 'active' and not self.cancel_at_period_end
    
    @property
    def days_until_expiration(self):
        """Return days until subscription expires"""
        if not self.current_period_end:
            return 0
        
        now = datetime.now(self.current_period_end.tzinfo)
        if now > self.current_period_end:
            return 0
            
        delta = self.current_period_end - now
        return delta.days


class StripeCustomer(models.Model):
    """Maps users to Stripe customers"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='stripe_customer',
        verbose_name=_('User')
    )
    stripe_customer_id = models.CharField(_('Stripe Customer ID'), max_length=100, unique=True)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        verbose_name = _('Stripe Customer')
        verbose_name_plural = _('Stripe Customers')
    
    def __str__(self):
        return f"{self.user.email} - {self.stripe_customer_id}"


class PaymentReceipt(models.Model):
    """Stores payment receipt information for subscriptions"""
    STATUS_CHOICES = [
        ('paid', _('Paid')),
        ('open', _('Open')),
        ('void', _('Void')),
        ('uncollectible', _('Uncollectible')),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='receipts',
        verbose_name=_('User')
    )
    
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='receipts',
        verbose_name=_('Subscription')
    )
    
    stripe_invoice_id = models.CharField(_('Stripe Invoice ID'), max_length=100, unique=True)
    stripe_charge_id = models.CharField(_('Stripe Charge ID'), max_length=100, blank=True)
    
    amount_paid = models.IntegerField(_('Amount Paid (in cents)'))
    currency = models.CharField(_('Currency'), max_length=3, default='USD')
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='open')
    
    invoice_pdf = models.URLField(_('Invoice PDF URL'), blank=True)
    invoice_url = models.URLField(_('Invoice URL'), blank=True)
    
    period_start = models.DateTimeField(_('Period Start'))
    period_end = models.DateTimeField(_('Period End'))
    payment_date = models.DateTimeField(_('Payment Date'), null=True, blank=True)
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        verbose_name = _('Payment Receipt')
        verbose_name_plural = _('Payment Receipts')
        ordering = ['-payment_date', '-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.formatted_amount} - {self.payment_date or 'Unpaid'}"
    
    @property
    def formatted_amount(self):
        """Return formatted amount with currency"""
        return f"${self.amount_paid/100:.2f} {self.currency}"
    
    @property
    def is_paid(self):
        """Return True if the receipt is paid"""
        return self.status == 'paid'
