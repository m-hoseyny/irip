from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError


class User(AbstractUser):
    """
    Custom User model that extends Django's AbstractUser.
    Uses email as the username field and adds additional fields needed for VPN account management.
    """
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    # AbstractUser already has an email field, but we need to ensure it's unique
    # This is done by setting unique=True in the Meta class constraints
    
    # KYC Status choices
    KYC_NOT_VERIFIED = 'not_verified'
    KYC_EMAIL_VERIFIED = 'email_verified'
    KYC_SECURITY_VERIFIED = 'security_verified'
    
    KYC_STATUS_CHOICES = [
        (KYC_NOT_VERIFIED, _('Not Verified')),
        (KYC_EMAIL_VERIFIED, _('Email Verified')),
        (KYC_SECURITY_VERIFIED, _('Security Verified')),
    ]
    
    kyc_status = models.CharField(
        _('KYC Status'),
        max_length=20,
        choices=KYC_STATUS_CHOICES,
        default=KYC_NOT_VERIFIED,
        help_text=_('Know Your Customer verification status')
    )
    
    is_verified = models.BooleanField(
        _('verified'),
        default=False,
        help_text=_('Designates whether this user has verified their account.')
    )
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    social_security_number = models.CharField(max_length=30, blank=True, null=True, help_text=_('Social Security Number or equivalent ID'))
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        constraints = [
            models.UniqueConstraint(fields=['email'], name='unique_email')
        ]
    
    def __str__(self):
        return self.username
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username
    
    def save(self, *args, **kwargs):
        # Update KYC status based on verification status
        if self.social_security_number and self.is_verified:
            self.kyc_status = self.KYC_SECURITY_VERIFIED
        elif self.is_verified and self.kyc_status == self.KYC_NOT_VERIFIED:
            self.kyc_status = self.KYC_EMAIL_VERIFIED
            
        super().save(*args, **kwargs)
    
    def update_kyc_status(self):
        """Update KYC status based on current verification state"""
        if self.social_security_number and self.is_verified:
            self.kyc_status = self.KYC_SECURITY_VERIFIED
        elif self.is_verified:
            self.kyc_status = self.KYC_EMAIL_VERIFIED
        else:
            self.kyc_status = self.KYC_NOT_VERIFIED
        
        self.save(update_fields=['kyc_status'])
