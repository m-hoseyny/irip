from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """
    Custom User model that extends Django's AbstractUser.
    Adds additional fields needed for VPN account management.
    """
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
    
    def __str__(self):
        return self.username
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username
