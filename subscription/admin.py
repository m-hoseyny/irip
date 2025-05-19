from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from .models import StripeProduct, StripePrice, Subscription, StripeCustomer, PaymentReceipt


@admin.register(StripeProduct)
class StripeProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'verification_level', 'stripe_product_id', 'active')
    list_filter = ('active', 'verification_level')
    search_fields = ('name', 'stripe_product_id')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'verification_level', 'active')
        }),
        (_('Stripe Information'), {
            'fields': ('stripe_product_id',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(StripePrice)
class StripePriceAdmin(admin.ModelAdmin):
    list_display = ('product', 'formatted_amount', 'recurring_interval', 'stripe_price_id', 'active')
    list_filter = ('active', 'recurring_interval', 'product')
    search_fields = ('stripe_price_id', 'product__name')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('product', 'price_amount', 'currency', 'recurring_interval', 'active')
        }),
        (_('Stripe Information'), {
            'fields': ('stripe_price_id',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def formatted_amount(self, obj):
        return obj.formatted_price
    formatted_amount.short_description = _('Price')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'price_info', 'status_colored', 'current_period_end', 'days_remaining', 'admin_actions')
    list_filter = ('status', 'price__product', 'cancel_at_period_end')
    search_fields = ('user__email', 'user__username', 'stripe_subscription_id')
    readonly_fields = (
        'user', 'stripe_subscription_id', 'stripe_customer_id', 'price', 
        'status', 'current_period_start', 'current_period_end', 
        'cancel_at_period_end', 'canceled_at', 'created_at', 'updated_at'
    )
    actions = ['cancel_subscriptions', 'recreate_vpn_accounts']
    fieldsets = (
        (None, {
            'fields': ('user', 'price', 'status')
        }),
        (_('Subscription Details'), {
            'fields': ('current_period_start', 'current_period_end', 'cancel_at_period_end', 'canceled_at')
        }),
        (_('Stripe Information'), {
            'fields': ('stripe_subscription_id', 'stripe_customer_id')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def cancel_subscriptions(self, request, queryset):
        """Admin action to cancel multiple subscriptions at once"""
        from .utils import cancel_subscription
        
        canceled_count = 0
        error_count = 0
        
        for subscription in queryset:
            if subscription.status == 'active' and not subscription.cancel_at_period_end:
                success, message = cancel_subscription(subscription.id)
                if success:
                    canceled_count += 1
                else:
                    error_count += 1
                    self.message_user(request, f"Error canceling {subscription.user.email}'s subscription: {message}", level='ERROR')
        
        if canceled_count > 0:
            self.message_user(request, f"Successfully marked {canceled_count} subscription(s) for cancellation at the end of their billing period.")
        
        if canceled_count == 0 and error_count == 0:
            self.message_user(request, "No active subscriptions were selected for cancellation.", level='WARNING')
    
    cancel_subscriptions.short_description = _('Cancel selected subscriptions at period end')
    
    def recreate_vpn_accounts(self, request, queryset):
        """Admin action to recreate VPN accounts for subscriptions that don't have one"""
        from vpn_account.models import VPNAccount
        
        created_count = 0
        error_count = 0
        skipped_count = 0
        
        for subscription in queryset:
            # Only process active or trialing subscriptions
            if subscription.status not in ['active', 'trialing']:
                skipped_count += 1
                continue
                
            # Check if the subscription already has a VPN account
            existing_accounts = VPNAccount.objects.filter(subscription=subscription).count()
            if existing_accounts > 0:
                skipped_count += 1
                continue
                
            # Create a new VPN account for this subscription
            try:
                vpn_account = VPNAccount.create_account_for_subscription(subscription)
                if vpn_account:
                    created_count += 1
                else:
                    error_count += 1
            except Exception as e:
                self.message_user(
                    request, 
                    _(f'Error creating VPN account for subscription {subscription.id}: {str(e)}'),
                    level='error'
                )
                error_count += 1
        
        if created_count > 0:
            self.message_user(request, _(f'{created_count} VPN account(s) successfully created.'))
        if skipped_count > 0:
            self.message_user(request, _(f'{skipped_count} subscription(s) skipped (inactive or already have VPN accounts).'), level='warning')
        if error_count > 0:
            self.message_user(request, _(f'Failed to create {error_count} VPN account(s).'), level='error')
    
    recreate_vpn_accounts.short_description = _('Recreate missing VPN accounts')
    
    def price_info(self, obj):
        if not obj.price:
            return "-"
        return f"{obj.price.product.name} - {obj.price.formatted_price}/{obj.price.get_recurring_interval_display()}"
    price_info.short_description = _('Plan')
    
    def status_colored(self, obj):
        colors = {
            'active': 'green',
            'past_due': 'orange',
            'canceled': 'red',
            'incomplete': 'gray',
            'incomplete_expired': 'gray',
            'trialing': 'blue',
            'unpaid': 'red',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'black'),
            obj.get_status_display()
        )
    status_colored.short_description = _('Status')
    
    def days_remaining(self, obj):
        days = obj.days_until_expiration
        if days == 0:
            return format_html('<span style="color: red; font-weight: bold;">Expired</span>')
        
        text_color = 'green' if days > 7 else 'orange' if days > 3 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} days</span>',
            text_color,
            days
        )
    days_remaining.short_description = _('Days Remaining')
    
    def admin_actions(self, obj):
        """Display admin action buttons"""
        buttons = []
        
        # Status indicator for canceled subscriptions
        if obj.cancel_at_period_end:
            buttons.append(
                format_html(
                    '<span style="color: orange; margin-right: 10px;">Cancels on {}</span>', 
                    obj.current_period_end.strftime('%Y-%m-%d')
                )
            )
        
        # Cancel button - only for active subscriptions that aren't already canceled
        if obj.status == 'active' and not obj.cancel_at_period_end:
            cancel_url = f"../../../subscription/subscription/{obj.id}/cancel-admin/"
            buttons.append(
                format_html(
                    '<a class="button" href="{}" style="background-color: #dc3545; color: white;" '
                    'onclick="return confirm(\'Are you sure you want to cancel this subscription? '
                    'It will remain active until the end of the billing period.\');">'
                    '<i class="fas fa-times-circle"></i> Cancel</a>',
                    cancel_url
                )
            )
        
        # If no buttons, return a dash
        if not buttons:
            return format_html('<span style="color: gray;">-</span>')
            
        # Return all buttons joined together
        return format_html('&nbsp;'.join(buttons))
    
    admin_actions.short_description = _('Actions')


@admin.register(StripeCustomer)
class StripeCustomerAdmin(admin.ModelAdmin):
    list_display = ('user', 'stripe_customer_id', 'created_at')
    search_fields = ('user__email', 'user__username', 'stripe_customer_id')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('user', 'stripe_customer_id')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(PaymentReceipt)
class PaymentReceiptAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount_display', 'status_colored', 'subscription', 'payment_date', 'invoice_links')
    list_filter = ('status', 'currency', 'payment_date')
    search_fields = ('user__email', 'user__username', 'stripe_invoice_id', 'stripe_charge_id')
    readonly_fields = (
        'user', 'subscription', 'stripe_invoice_id', 'stripe_charge_id',
        'amount_paid', 'currency', 'status', 'invoice_pdf', 'invoice_url',
        'period_start', 'period_end', 'payment_date', 'created_at', 'updated_at'
    )
    fieldsets = (
        (None, {
            'fields': ('user', 'subscription', 'status')
        }),
        (_('Payment Details'), {
            'fields': ('amount_paid', 'currency', 'payment_date')
        }),
        (_('Period'), {
            'fields': ('period_start', 'period_end')
        }),
        (_('Stripe Information'), {
            'fields': ('stripe_invoice_id', 'stripe_charge_id', 'invoice_pdf', 'invoice_url')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def amount_display(self, obj):
        return obj.formatted_amount
    amount_display.short_description = _('Amount')
    
    def status_colored(self, obj):
        colors = {
            'paid': 'green',
            'open': 'orange',
            'void': 'red',
            'uncollectible': 'red',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'black'),
            obj.get_status_display()
        )
    status_colored.short_description = _('Status')
    
    def invoice_links(self, obj):
        links = []
        if obj.invoice_pdf:
            links.append(format_html(
                '<a href="{}" target="_blank" style="margin-right: 10px;">PDF</a>',
                obj.invoice_pdf
            ))
        if obj.invoice_url:
            links.append(format_html(
                '<a href="{}" target="_blank">View in Stripe</a>',
                obj.invoice_url
            ))
        
        if not links:
            return '-'
        
        return format_html('&nbsp;|&nbsp;'.join(links))
    invoice_links.short_description = _('Invoices')
