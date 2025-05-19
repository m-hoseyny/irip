import stripe
import logging
from django.conf import settings
from django.contrib.auth import get_user_model
from .models import StripeCustomer, Subscription, StripePrice
from datetime import datetime
from user.models import User

logger = logging.getLogger(__name__)

# Initialize Stripe with the API key
stripe.api_key = settings.STRIPE_SECRET_KEY


def is_eligible_for_product(user, product):
    """
    Check if a user is eligible for a product based on their verification level.
    
    Args:
        user: The user to check
        product: The StripeProduct to check eligibility for
        
    Returns:
        bool: True if the user is eligible, False otherwise
    """
    if not user or not product:
        return False
        
    if product.verification_level == 'security_verified':
        return user.kyc_status == User.KYC_SECURITY_VERIFIED
    elif product.verification_level == 'email_verified':
        return user.kyc_status in [User.KYC_EMAIL_VERIFIED, User.KYC_SECURITY_VERIFIED]
        
    return False


def get_or_create_stripe_customer(user):
    """
    Get or create a Stripe customer for a user.
    
    Args:
        user: The user to get or create a Stripe customer for
        
    Returns:
        StripeCustomer: The Stripe customer object
    """
    try:
        # Check if the user already has a Stripe customer
        stripe_customer = StripeCustomer.objects.filter(user=user).first()
        
        if stripe_customer:
            # Verify the customer still exists in Stripe
            try:
                stripe.Customer.retrieve(stripe_customer.stripe_customer_id)
                return stripe_customer
            except stripe.error.InvalidRequestError:
                # Customer doesn't exist in Stripe anymore, create a new one
                stripe_customer.delete()
        
        # Create a new Stripe customer
        customer = stripe.Customer.create(
            email=user.email,
            name=user.get_full_name() or user.username,
            metadata={
                'user_id': str(user.id),
                'username': user.username,
            }
        )
        
        # Save the customer ID to the database
        stripe_customer = StripeCustomer.objects.create(
            user=user,
            stripe_customer_id=customer.id
        )
        
        return stripe_customer
    
    except Exception as e:
        logger.error(f"Error creating Stripe customer for user {user.email}: {str(e)}")
        raise


def create_checkout_session(user, price_id, success_url, cancel_url):
    """
    Create a Stripe checkout session for a subscription.
    
    Args:
        user: The user creating the subscription
        price_id: The ID of the StripePrice to subscribe to
        success_url: URL to redirect to after successful checkout
        cancel_url: URL to redirect to if checkout is canceled
        
    Returns:
        dict: The created checkout session
    """
    try:
        price = StripePrice.objects.get(id=price_id)
        
        # Check if the user is eligible for this product
        if not is_eligible_for_product(user, price.product):
            raise ValueError(f"User {user.email} is not eligible for product {price.product.name}")
        
        # Get or create the Stripe customer
        stripe_customer = get_or_create_stripe_customer(user)
        
        # Create the checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=stripe_customer.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': price.stripe_price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'user_id': str(user.id),
                'price_id': str(price.id),
            }
        )
        
        return checkout_session
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        raise


def handle_checkout_completed(session):
    """
    Handle a completed checkout session.
    
    Args:
        session: The Stripe checkout session object
    """
    try:
        # Get the subscription from Stripe
        subscription = stripe.Subscription.retrieve(session.subscription)
        
        # Get user ID and price ID from metadata
        user_id = session.metadata.get('user_id')
        price_id = session.metadata.get('price_id')
        
        if not user_id or not price_id:
            logger.error(f"Missing metadata in checkout session {session.id}")
            return
        
        # Get the user and price
        User = get_user_model()
        user = User.objects.get(id=user_id)
        price = StripePrice.objects.get(id=price_id)
        
        # Create or update the subscription
        db_subscription, created = Subscription.objects.update_or_create(
            stripe_subscription_id=subscription.id,
            defaults={
                'user': user,
                'stripe_customer_id': session.customer,
                'price': price,
                'status': subscription.status,
                'current_period_start': datetime.fromtimestamp(subscription.current_period_start),
                'current_period_end': datetime.fromtimestamp(subscription.current_period_end),
                'cancel_at_period_end': subscription.cancel_at_period_end,
                'canceled_at': datetime.fromtimestamp(subscription.canceled_at) if subscription.canceled_at else None,
            }
        )
        
        logger.info(f"Subscription created/updated for user {user.email}")
        
        # Create VPN account for the subscription if it's active
        if db_subscription.status in ['active', 'trialing']:
            # Import here to avoid circular imports
            from vpn_account.models import VPNAccount
            
            # Check if a VPN account already exists for this subscription
            existing_account = VPNAccount.objects.filter(subscription=db_subscription).first()
            
            if not existing_account:
                # Create a new VPN account
                vpn_account = VPNAccount.create_account_for_subscription(db_subscription)
                if vpn_account:
                    logger.info(f"VPN account created for subscription {db_subscription.id}")
                else:
                    logger.error(f"Failed to create VPN account for subscription {db_subscription.id}")
        
    except Exception as e:
        logger.error(f"Error handling checkout completed: {str(e)}")


def handle_subscription_updated(subscription_object):
    """
    Handle a subscription updated event.
    
    Args:
        subscription_object: The Stripe subscription object
    """
    try:
        # Get the subscription from the database
        subscription = Subscription.objects.filter(
            stripe_subscription_id=subscription_object.id
        ).first()
        
        if not subscription:
            logger.error(f"Subscription not found: {subscription_object.id}")
            return
        
        # Get the previous status before updating
        previous_status = subscription.status
        
        # Update the subscription
        subscription.status = subscription_object.status
        subscription.current_period_start = datetime.fromtimestamp(subscription_object.current_period_start)
        subscription.current_period_end = datetime.fromtimestamp(subscription_object.current_period_end)
        subscription.cancel_at_period_end = subscription_object.cancel_at_period_end
        subscription.canceled_at = datetime.fromtimestamp(subscription_object.canceled_at) if subscription_object.canceled_at else None
        subscription.save()
        
        logger.info(f"Subscription updated for user {subscription.user.email}")
        
        # Handle VPN account status changes based on subscription status changes
        try:
            # Import here to avoid circular imports
            from vpn_account.models import VPNAccount
            
            # If subscription was not active but is now active, create a VPN account if needed
            if previous_status not in ['active', 'trialing'] and subscription.status in ['active', 'trialing']:
                # Check if a VPN account already exists for this subscription
                existing_account = VPNAccount.objects.filter(subscription=subscription).first()
                
                if not existing_account:
                    # Create a new VPN account
                    vpn_account = VPNAccount.create_account_for_subscription(subscription)
                    if vpn_account:
                        logger.info(f"VPN account created for reactivated subscription {subscription.id}")
                    else:
                        logger.error(f"Failed to create VPN account for reactivated subscription {subscription.id}")
            
            # If subscription was active but is now inactive, deactivate any VPN accounts
            elif previous_status in ['active', 'trialing'] and subscription.status not in ['active', 'trialing']:
                # Find all VPN accounts associated with this subscription
                vpn_accounts = VPNAccount.objects.filter(subscription=subscription, status=VPNAccount.STATUS_ACTIVE)
                
                for vpn_account in vpn_accounts:
                    # Call the delete_account method to remove from 3x-ui and update status
                    success = vpn_account.delete_account()
                    if success:
                        logger.info(f"VPN account {vpn_account.id} deactivated for inactive subscription {subscription.id}")
                    else:
                        logger.error(f"Failed to deactivate VPN account {vpn_account.id} for inactive subscription {subscription.id}")
                        
                    # Even if the API call fails, mark the account as suspended
                    vpn_account.status = VPNAccount.STATUS_SUSPENDED
                    vpn_account.save(update_fields=['status', 'updated_at'])
                    
        except Exception as e:
            logger.error(f"Error handling VPN accounts for subscription update {subscription.id}: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error handling subscription updated: {str(e)}")


def handle_subscription_deleted(subscription_object):
    """
    Handle a subscription deleted event.
    
    Args:
        subscription_object: The Stripe subscription object
    """
    try:
        # Get the subscription from the database
        subscription = Subscription.objects.filter(
            stripe_subscription_id=subscription_object.id
        ).first()
        
        if not subscription:
            logger.error(f"Subscription not found: {subscription_object.id}")
            return
        
        # Update the subscription status
        subscription.status = 'canceled'
        subscription.canceled_at = datetime.now()
        subscription.save()
        
        logger.info(f"Subscription canceled for user {subscription.user.email}")
        
        # Deactivate associated VPN accounts
        try:
            # Import here to avoid circular imports
            from vpn_account.models import VPNAccount
            
            # Find all VPN accounts associated with this subscription
            vpn_accounts = VPNAccount.objects.filter(subscription=subscription)
            
            for vpn_account in vpn_accounts:
                # Call the delete_account method to remove from 3x-ui and update status
                if vpn_account.status == VPNAccount.STATUS_ACTIVE:
                    success = vpn_account.delete_account()
                    if success:
                        logger.info(f"VPN account {vpn_account.id} deactivated for canceled subscription {subscription.id}")
                    else:
                        logger.error(f"Failed to deactivate VPN account {vpn_account.id} for canceled subscription {subscription.id}")
                        
                    # Even if the API call fails, mark the account as expired
                    vpn_account.status = VPNAccount.STATUS_EXPIRED
                    vpn_account.save(update_fields=['status', 'updated_at'])
            
        except Exception as e:
            logger.error(f"Error deactivating VPN accounts for subscription {subscription.id}: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error handling subscription deleted: {str(e)}")


def handle_invoice_event(invoice):
    """
    Handle invoice created or updated events.
    
    Args:
        invoice: The Stripe invoice object
    """
    from .models import PaymentReceipt
    
    try:
        # Find the subscription for this invoice
        subscription = None
        if invoice.subscription:
            subscription = Subscription.objects.filter(
                stripe_subscription_id=invoice.subscription
            ).first()
            
            if not subscription:
                logger.warning(f"Subscription not found for invoice: {invoice.id}")
                return
        else:
            logger.warning(f"Invoice {invoice.id} has no subscription")
            return
        
        # Get the user from the subscription
        user = subscription.user
        
        # Create or update the receipt
        receipt, created = PaymentReceipt.objects.update_or_create(
            stripe_invoice_id=invoice.id,
            defaults={
                'user': user,
                'subscription': subscription,
                'amount_paid': invoice.amount_due,
                'currency': invoice.currency,
                'status': invoice.status,
                'invoice_pdf': invoice.invoice_pdf or '',
                'invoice_url': invoice.hosted_invoice_url or '',
                'period_start': datetime.fromtimestamp(invoice.period_start),
                'period_end': datetime.fromtimestamp(invoice.period_end),
                'payment_date': None,  # Will be updated when paid
                'stripe_charge_id': invoice.charge or '',
            }
        )
        
        if created:
            logger.info(f"Created receipt for invoice {invoice.id} for user {user.email}")
        else:
            logger.info(f"Updated receipt for invoice {invoice.id} for user {user.email}")
            
    except Exception as e:
        logger.error(f"Error handling invoice event: {str(e)}")


def handle_invoice_paid(invoice):
    """
    Handle invoice paid event.
    
    Args:
        invoice: The Stripe invoice object
    """
    from .models import PaymentReceipt
    
    try:
        # Find the receipt for this invoice
        receipt = PaymentReceipt.objects.filter(stripe_invoice_id=invoice.id).first()
        
        if not receipt:
            # Create the receipt if it doesn't exist
            handle_invoice_event(invoice)
            receipt = PaymentReceipt.objects.filter(stripe_invoice_id=invoice.id).first()
            
            if not receipt:
                logger.error(f"Failed to create receipt for paid invoice: {invoice.id}")
                return
        
        # Update the receipt with payment information
        receipt.status = 'paid'
        receipt.payment_date = datetime.fromtimestamp(invoice.status_transitions.paid_at)
        receipt.amount_paid = invoice.amount_paid
        receipt.stripe_charge_id = invoice.charge or ''
        receipt.save()
        
        logger.info(f"Updated receipt {receipt.id} as paid for user {receipt.user.email}")
        
    except Exception as e:
        logger.error(f"Error handling invoice paid event: {str(e)}")


def handle_invoice_payment_failed(invoice):
    """
    Handle invoice payment failed event.
    
    Args:
        invoice: The Stripe invoice object
    """
    from .models import PaymentReceipt
    
    try:
        # Find the receipt for this invoice
        receipt = PaymentReceipt.objects.filter(stripe_invoice_id=invoice.id).first()
        
        if not receipt:
            # Create the receipt if it doesn't exist
            handle_invoice_event(invoice)
            receipt = PaymentReceipt.objects.filter(stripe_invoice_id=invoice.id).first()
            
            if not receipt:
                logger.error(f"Failed to create receipt for failed invoice: {invoice.id}")
                return
        
        # Update the receipt with failed status
        receipt.status = invoice.status  # Will be 'open' or 'uncollectible'
        receipt.save()
        
        logger.info(f"Updated receipt {receipt.id} as payment failed for user {receipt.user.email}")
        
    except Exception as e:
        logger.error(f"Error handling invoice payment failed event: {str(e)}")


def sync_stripe_products():
    """
    Sync products from Stripe to the local database.
    
    Note: This does not automatically create products in Stripe.
    It only syncs existing Stripe products into the local database.
    """
    from .models import StripeProduct, StripePrice
    
    try:
        # Get all active products from Stripe
        stripe_products = stripe.Product.list(active=True)
        
        for product in stripe_products.data:
            # Create or update the product
            db_product, created = StripeProduct.objects.update_or_create(
                stripe_product_id=product.id,
                defaults={
                    'name': product.name,
                    'description': product.description or '',
                    'active': product.active,
                    # Note: verification_level must be set manually
                }
            )
            
            if created:
                logger.info(f"Created new product from Stripe: {db_product.name}")
            
            # Get all prices for this product
            stripe_prices = stripe.Price.list(product=product.id, active=True)
            
            for price in stripe_prices.data:
                if not price.recurring:
                    continue  # Skip non-recurring prices
                
                # Create or update the price
                db_price, price_created = StripePrice.objects.update_or_create(
                    stripe_price_id=price.id,
                    defaults={
                        'product': db_product,
                        'price_amount': price.unit_amount,
                        'currency': price.currency,
                        'recurring_interval': price.recurring.interval,
                        'active': price.active,
                    }
                )
                
                if price_created:
                    logger.info(f"Created new price from Stripe: {db_price}")
                    
        return True, "Products and prices synced successfully"
        
    except Exception as e:
        logger.error(f"Error syncing Stripe products: {str(e)}")
        return False, str(e)


def cancel_subscription(subscription_id):
    """
    Cancel a subscription at the end of the current period.
    
    Args:
        subscription_id: The ID of the subscription to cancel
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get the subscription from the database
        subscription = Subscription.objects.get(id=subscription_id)
        
        # Cancel the subscription in Stripe
        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=True
        )
        
        # Update the subscription in the database
        subscription.cancel_at_period_end = True
        subscription.save()
        
        logger.info(f"Subscription {subscription_id} canceled at period end")
        return True, "Subscription will be canceled at the end of the current billing period"
        
    except Subscription.DoesNotExist:
        logger.error(f"Subscription not found: {subscription_id}")
        return False, "Subscription not found"
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error canceling subscription: {str(e)}")
        return False, f"Stripe error: {str(e)}"
    except Exception as e:
        logger.error(f"Error canceling subscription: {str(e)}")
        return False, f"Error: {str(e)}"
