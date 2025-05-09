from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.conf import settings
from .tokens import email_verification_token


import logging
import traceback
from smtplib import SMTPException

logger = logging.getLogger(__name__)

def send_verification_email(user, request=None):
    """
    Send an email verification link to the user.
    Returns a tuple (success, message) where success is a boolean and message contains details.
    """
    try:
        # Log email settings for debugging
        logger.info(f"Email settings: Backend={settings.EMAIL_BACKEND}, Host={settings.EMAIL_HOST}, Port={settings.EMAIL_PORT}")
        logger.info(f"Sending verification email to {user.email}")
        
        # Create verification token
        token = email_verification_token.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        # Build verification URL
        domain = request.get_host() if request else settings.SITE_DOMAIN
        protocol = 'https' if request and request.is_secure() else 'http'
        verification_url = f"{protocol}://{domain}/api/v1/user/verify-email/{uid}/{token}/"
        
        logger.info(f"Verification URL: {verification_url}")
        
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
        
        status = email.send(fail_silently=False)
        
        if status:
            logger.info(f"Successfully sent verification email to {user.email}")
            return True, f"Verification email sent to {user.email}"
        else:
            logger.error(f"Failed to send verification email to {user.email}")
            return False, f"Failed to send email. Email server returned status: {status}"
    
    except SMTPException as e:
        error_msg = f"SMTP Error: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return False, error_msg
    
    except Exception as e:
        error_msg = f"Unexpected error sending email: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return False, error_msg
