from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.conf import settings
from .tokens import email_verification_token


def send_verification_email(user, request=None):
    """
    Send an email verification link to the user.
    """
    # Create verification token
    token = email_verification_token.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    
    # Build verification URL
    domain = request.get_host() if request else settings.SITE_DOMAIN
    protocol = 'https' if request and request.is_secure() else 'http'
    verification_url = f"{protocol}://{domain}/api/v1/user/verify-email/{uid}/{token}/"
    
    # Prepare email content
    subject = "Verify your email address"
    email_template = """
    Hello {name},
    
    Thank you for registering with IRIP VPN. Please verify your email address by clicking the link below:
    
    {verification_url}
    
    This link will expire in 24 hours.
    
    If you did not register for an account, please ignore this email.
    
    Best regards,
    The IRIP Team
    """.format(
        name=user.get_full_name() or user.username,
        verification_url=verification_url
    )
    
    # Send email
    email = EmailMessage(
        subject=subject,
        body=email_template,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email]
    )
    
    return email.send()
