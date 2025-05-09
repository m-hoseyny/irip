from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib import messages

from .models import VerificationPhoto


class VerificationPhotoAdmin(admin.ModelAdmin):
    list_display = ('user', 'status_colored', 'photo_preview', 'uploaded_at', 'updated_at', 'verification_actions')
    list_filter = ('status', 'uploaded_at', 'updated_at')
    search_fields = ('user__username', 'user__email', 'notes')
    readonly_fields = ('uploaded_at', 'updated_at', 'photo_full')
    fieldsets = (
        (None, {
            'fields': ('user', 'photo', 'photo_full', 'status')
        }),
        (_('Admin Information'), {
            'fields': ('notes', 'uploaded_at', 'updated_at')
        }),
    )
    actions = ['approve_photos', 'reject_photos']
    
    def status_colored(self, obj):
        """Display status with color coding"""
        colors = {
            VerificationPhoto.STATUS_PENDING: 'orange',
            VerificationPhoto.STATUS_VERIFIED: 'green',
            VerificationPhoto.STATUS_REJECTED: 'red',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'black'),
            obj.get_status_display()
        )
    status_colored.short_description = _('Status')
    
    def photo_preview(self, obj):
        """Display a thumbnail of the photo"""
        if obj.photo:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" width="50" height="50" style="object-fit: cover;" /></a>',
                obj.photo.url, obj.photo.url
            )
        return "-"
    photo_preview.short_description = _('Photo')
    
    def photo_full(self, obj):
        """Display the full photo in the detail view"""
        if obj.photo:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" width="400" style="max-width: 100%;" /></a>',
                obj.photo.url, obj.photo.url
            )
        return "-"
    photo_full.short_description = _('Photo Preview')
    
    def verification_actions(self, obj):
        """Display verification action buttons"""
        if obj.status == VerificationPhoto.STATUS_PENDING:
            return format_html(
                '<a class="button" href="{}" style="background-color: #28a745; color: white; margin-right: 5px;">Approve</a> '
                '<a class="button" href="{}" style="background-color: #dc3545; color: white;">Reject</a>',
                reverse('admin:approve-photo', args=[obj.pk]),
                reverse('admin:reject-photo', args=[obj.pk])
            )
        elif obj.status == VerificationPhoto.STATUS_VERIFIED:
            return format_html('<span style="color: green;">✓ Approved</span>')
        else:  # REJECTED
            return format_html('<span style="color: red;">✗ Rejected</span>')
    verification_actions.short_description = _('Actions')
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/approve/',
                self.admin_site.admin_view(self.approve_photo_view),
                name='approve-photo',
            ),
            path(
                '<path:object_id>/reject/',
                self.admin_site.admin_view(self.reject_photo_view),
                name='reject-photo',
            ),
        ]
        return custom_urls + urls
    
    def approve_photo_view(self, request, object_id):
        """Admin view to approve a verification photo"""
        photo = self.get_object(request, object_id)
        photo.status = VerificationPhoto.STATUS_VERIFIED
        photo.save()
        self.message_user(
            request, 
            f'Verification photo for {photo.user.email} has been approved. User KYC status updated to Security Verified.', 
            messages.SUCCESS
        )
        return HttpResponseRedirect(reverse('admin:file_management_verificationphoto_changelist'))
    
    def reject_photo_view(self, request, object_id):
        """Admin view to reject a verification photo"""
        photo = self.get_object(request, object_id)
        photo.status = VerificationPhoto.STATUS_REJECTED
        photo.save()
        self.message_user(
            request, 
            f'Verification photo for {photo.user.email} has been rejected. User will need to upload a new photo.', 
            messages.WARNING
        )
        return HttpResponseRedirect(reverse('admin:file_management_verificationphoto_changelist'))
    
    def approve_photos(self, request, queryset):
        """Admin action to approve multiple verification photos"""
        updated = 0
        for photo in queryset:
            if photo.status != VerificationPhoto.STATUS_VERIFIED:
                photo.status = VerificationPhoto.STATUS_VERIFIED
                photo.save()
                updated += 1
        self.message_user(request, f'Approved {updated} verification photos', messages.SUCCESS)
    approve_photos.short_description = _('Approve selected photos')
    
    def reject_photos(self, request, queryset):
        """Admin action to reject multiple verification photos"""
        updated = 0
        for photo in queryset:
            if photo.status != VerificationPhoto.STATUS_REJECTED:
                photo.status = VerificationPhoto.STATUS_REJECTED
                photo.save()
                updated += 1
        self.message_user(request, f'Rejected {updated} verification photos', messages.WARNING)
    reject_photos.short_description = _('Reject selected photos')


admin.site.register(VerificationPhoto, VerificationPhotoAdmin)
