from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib import messages

from .models import User


class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'address', 'date_of_birth', 'profile_picture', 'social_security_number')}),
        (_('Verification'), {
            'fields': ('is_verified', 'kyc_status'),
            'description': _('Manage user verification status. Email verification can be done by the user, but security verification requires admin approval.')
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'kyc_status_colored', 'is_verified', 'has_social_security', 'is_staff', 'verification_actions')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'is_verified', 'kyc_status', 'groups')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone_number')
    readonly_fields = ('kyc_status',)
    actions = ['verify_email', 'verify_security', 'reset_verification']
    
    def kyc_status_colored(self, obj):
        """Display KYC status with color coding"""
        colors = {
            User.KYC_NOT_VERIFIED: 'red',
            User.KYC_EMAIL_VERIFIED: 'orange',
            User.KYC_SECURITY_VERIFIED: 'green',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.kyc_status, 'black'),
            obj.get_kyc_status_display()
        )
    kyc_status_colored.short_description = _('KYC Status')
    
    def has_social_security(self, obj):
        """Check if user has provided social security number"""
        return bool(obj.social_security_number)
    has_social_security.boolean = True
    has_social_security.short_description = _('Has SSN')
    
    def verification_actions(self, obj):
        """Display verification action buttons"""
        if obj.kyc_status == User.KYC_SECURITY_VERIFIED:
            return format_html('<span style="color: green;">✓ Fully Verified</span>')
        elif obj.kyc_status == User.KYC_EMAIL_VERIFIED:
            return format_html(
                '<a class="button" href="{}" style="background-color: #28a745; color: white;">Verify Security</a>',
                reverse('admin:verify-security', args=[obj.pk])
            )
        else:
            return format_html(
                '<a class="button" href="{}" style="background-color: #ffc107; color: black;">Verify Email</a>',
                reverse('admin:verify-email', args=[obj.pk])
            )
    verification_actions.short_description = _('Actions')
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/verify-email/',
                self.admin_site.admin_view(self.verify_email_view),
                name='verify-email',
            ),
            path(
                '<path:object_id>/verify-security/',
                self.admin_site.admin_view(self.verify_security_view),
                name='verify-security',
            ),
        ]
        return custom_urls + urls
    
    def verify_email_view(self, request, object_id):
        """Admin view to verify user's email"""
        user = self.get_object(request, object_id)
        user.is_verified = True
        user.update_kyc_status()
        user.save()
        self.message_user(request, f'Email verified for {user.email}', messages.SUCCESS)
        return HttpResponseRedirect(reverse('admin:user_user_changelist'))
    
    def verify_security_view(self, request, object_id):
        """Admin view to verify user's security information"""
        user = self.get_object(request, object_id)
        if not user.social_security_number:
            self.message_user(request, f'Cannot verify security: No social security number provided for {user.email}', messages.ERROR)
        else:
            user.kyc_status = User.KYC_SECURITY_VERIFIED
            user.save()
            self.message_user(request, f'Security verified for {user.email}', messages.SUCCESS)
        return HttpResponseRedirect(reverse('admin:user_user_changelist'))
    
    def verify_email(self, request, queryset):
        """Admin action to verify email for selected users"""
        updated = 0
        for user in queryset:
            if not user.is_verified:
                user.is_verified = True
                user.update_kyc_status()
                user.save()
                updated += 1
        self.message_user(request, f'Email verified for {updated} users', messages.SUCCESS)
    verify_email.short_description = _('Verify email for selected users')
    
    def verify_security(self, request, queryset):
        """Admin action to verify security for selected users"""
        updated = 0
        skipped = 0
        for user in queryset:
            if user.is_verified and user.social_security_number:
                user.kyc_status = User.KYC_SECURITY_VERIFIED
                user.save()
                updated += 1
            else:
                skipped += 1
        if updated:
            self.message_user(request, f'Security verified for {updated} users', messages.SUCCESS)
        if skipped:
            self.message_user(request, f'Skipped {skipped} users (email not verified or no SSN)', messages.WARNING)
    verify_security.short_description = _('Verify security for selected users')
    
    def reset_verification(self, request, queryset):
        """Admin action to reset verification status"""
        for user in queryset:
            user.kyc_status = User.KYC_NOT_VERIFIED
            user.is_verified = False
            user.save()
        self.message_user(request, f'Verification reset for {queryset.count()} users', messages.SUCCESS)
    reset_verification.short_description = _('Reset verification status for selected users')


admin.site.register(User, UserAdmin)
