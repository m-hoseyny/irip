from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.html import mark_safe
from django.conf import settings
import os
import uuid

# Create your models here.

class FAQ(models.Model):
    """Model for storing Frequently Asked Questions"""
    question = models.CharField(_('Question'), max_length=255)
    answer = models.TextField(_('Answer'))
    order = models.PositiveIntegerField(_('Display Order'), default=0, help_text=_('Order in which this FAQ is displayed'))
    is_active = models.BooleanField(_('Is Active'), default=True)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        verbose_name = _('FAQ')
        verbose_name_plural = _('FAQs')
        ordering = ['order', 'created_at']
    
    def __str__(self):
        return self.question


class Tutorial(models.Model):
    """Model for storing Tutorials with HTML content"""
    name = models.CharField(_('Name'), max_length=255)
    body = models.TextField(_('Content'), help_text=_('HTML content for the tutorial'))
    order = models.PositiveIntegerField(_('Display Order'), default=0, help_text=_('Order in which this tutorial is displayed'))
    is_active = models.BooleanField(_('Is Active'), default=True)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        verbose_name = _('Tutorial')
        verbose_name_plural = _('Tutorials')
        ordering = ['order', 'created_at']
    
    def __str__(self):
        return self.name
        
    def rendered_body(self):
        """Returns the HTML content rendered safely"""
        return mark_safe(self.body)


def ticket_attachment_path(instance, filename):
    # Generate a UUID for the filename to avoid collisions
    ext = filename.split('.')[-1]
    new_filename = f"{uuid.uuid4()}.{ext}"
    # Return the upload path
    return os.path.join('ticket_attachments', str(instance.ticket.id), new_filename)


class Ticket(models.Model):
    """Model for storing customer support tickets"""
    STATUS_CHOICES = (
        ('new', _('New')),
        ('in_progress', _('In Progress')),
        ('waiting_for_customer', _('Waiting for Customer')),
        ('resolved', _('Resolved')),
        ('closed', _('Closed')),
    )
    
    PRIORITY_CHOICES = (
        ('low', _('Low')),
        ('medium', _('Medium')),
        ('high', _('High')),
        ('urgent', _('Urgent')),
    )
    
    # If the user is authenticated, link to user model, otherwise store email
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                             null=True, blank=True, related_name='tickets')
    email = models.EmailField(_('Email'))
    phone_number = models.CharField(_('Phone Number'), max_length=20, blank=True)
    subject = models.CharField(_('Subject'), max_length=255)
    body = models.TextField(_('Message'))
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='new')
    priority = models.CharField(_('Priority'), max_length=10, choices=PRIORITY_CHOICES, default='medium')
    is_read_by_admin = models.BooleanField(_('Read by Admin'), default=False)
    is_read_by_user = models.BooleanField(_('Read by User'), default=True)  # User created it, so they've read it
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        verbose_name = _('Ticket')
        verbose_name_plural = _('Tickets')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"#{self.id} - {self.subject}"
    
    @property
    def latest_reply(self):
        """Returns the latest reply to this ticket"""
        return self.replies.order_by('-created_at').first()


class TicketReply(models.Model):
    """Model for storing replies to tickets"""
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='replies')
    # If the user is authenticated, link to user model
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                             null=True, blank=True, related_name='ticket_replies')
    is_from_admin = models.BooleanField(_('From Admin'), default=False)
    message = models.TextField(_('Message'))
    is_read_by_admin = models.BooleanField(_('Read by Admin'), default=False)
    is_read_by_user = models.BooleanField(_('Read by User'), default=False)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        verbose_name = _('Ticket Reply')
        verbose_name_plural = _('Ticket Replies')
        ordering = ['created_at']
    
    def __str__(self):
        return f"Reply to {self.ticket} by {'Admin' if self.is_from_admin else 'User'}"
    
    def save(self, *args, **kwargs):
        # Update ticket status when a reply is added
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            ticket = self.ticket
            if self.is_from_admin:
                # Admin replied, mark as waiting for customer and unread by user
                ticket.status = 'waiting_for_customer'
                ticket.is_read_by_user = False
                ticket.is_read_by_admin = True
            else:
                # User replied, mark as new and unread by admin
                ticket.status = 'new'
                ticket.is_read_by_admin = False
                ticket.is_read_by_user = True
            ticket.save()


class TicketAttachment(models.Model):
    """Model for storing file attachments for tickets"""
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='attachments')
    reply = models.ForeignKey(TicketReply, on_delete=models.CASCADE, related_name='attachments', null=True, blank=True)
    file = models.FileField(_('File'), upload_to=ticket_attachment_path)
    file_name = models.CharField(_('File Name'), max_length=255)
    file_size = models.PositiveIntegerField(_('File Size'), help_text=_('Size in bytes'))
    content_type = models.CharField(_('Content Type'), max_length=100, blank=True)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Ticket Attachment')
        verbose_name_plural = _('Ticket Attachments')
    
    def __str__(self):
        return self.file_name
    
    def save(self, *args, **kwargs):
        if not self.file_name and self.file:
            self.file_name = os.path.basename(self.file.name)
        if not self.file_size and self.file:
            self.file_size = self.file.size
        super().save(*args, **kwargs)
