from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver


class VerificationPhoto(models.Model):
    """
    Model for storing user verification photos.
    Users upload photos of themselves with their ID for verification.
    Admins review these photos and update the status accordingly.
    """
    # Status choices
    STATUS_PENDING = 'pending'
    STATUS_VERIFIED = 'verified'
    STATUS_REJECTED = 'rejected'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, _('Pending')),
        (STATUS_VERIFIED, _('Verified')),
        (STATUS_REJECTED, _('Rejected')),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='verification_photos',
        verbose_name=_('User')
    )
    photo = models.ImageField(
        upload_to='verification_photos/%Y/%m/',
        verbose_name=_('Verification Photo'),
        help_text=_('Photo of user with ID for verification')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name=_('Status')
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Admin Notes'),
        help_text=_('Notes from admin regarding verification')
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Uploaded At'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Updated At'))
    
    class Meta:
        verbose_name = _('Verification Photo')
        verbose_name_plural = _('Verification Photos')
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_status_display()} - {self.uploaded_at.strftime('%Y-%m-%d')}"


@receiver(post_save, sender=VerificationPhoto)
def update_user_kyc_status(sender, instance, **kwargs):
    """
    Update user's KYC status when verification photo status changes.
    If photo is verified, set user's KYC status to security_verified.
    """
    from user.models import User  # Import here to avoid circular imports
    
    if instance.status == VerificationPhoto.STATUS_VERIFIED:
        # Update user's KYC status to security_verified
        user = instance.user
        user.is_verified = True
        user.kyc_status = User.KYC_SECURITY_VERIFIED
        user.save()
