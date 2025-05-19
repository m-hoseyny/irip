from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from .models import VPNAccount


def disable_accounts(modeladmin, request, queryset):
    """Admin action to disable selected VPN accounts"""
    disabled_count = 0
    error_count = 0
    
    for account in queryset:
        if account.status == VPNAccount.STATUS_ACTIVE:
            success = account.delete_account()
            if success:
                disabled_count += 1
            else:
                error_count += 1
    
    if disabled_count > 0:
        messages.success(request, _(f'{disabled_count} account(s) successfully disabled.'))
    if error_count > 0:
        messages.error(request, _(f'Failed to disable {error_count} account(s).'))

disable_accounts.short_description = _('Disable selected accounts')


def remove_accounts(modeladmin, request, queryset):
    """Admin action to completely remove selected VPN accounts from 3x-ui"""
    removed_count = 0
    error_count = 0
    
    for account in queryset:
        if account.inbound_id is not None:
            success = account.remove_account()
            if success:
                removed_count += 1
            else:
                error_count += 1
    
    if removed_count > 0:
        messages.success(request, _(f'{removed_count} account(s) successfully removed from 3x-ui server.'))
    if error_count > 0:
        messages.error(request, _(f'Failed to remove {error_count} account(s) from 3x-ui server.'))

remove_accounts.short_description = _('Remove accounts from 3x-ui server')


@admin.register(VPNAccount)
class VPNAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'email', 'protocol', 'port', 'status', 'created_at')
    list_filter = ('status', 'protocol')
    search_fields = ('email', 'user__email', 'user__username')
    readonly_fields = ('account_id', 'config_file', 'config_data', 
                      'data_usage_up', 'data_usage_down', 'live_config', 'config_string')
    actions = [disable_accounts, remove_accounts]
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'subscription', 'email')
        }),
        ('Account Details', {
            'fields': ('account_id', 'inbound_id', 'status', 'protocol')
        }),
        ('Connection Information', {
            'fields': ('server_ip', 'port')
        }),
        ('Configuration', {
            'fields': ('config_data', 'config_file', 'live_config', 'config_string'),
            'classes': ('collapse',),
        }),
        ('Usage Statistics', {
            'fields': ('data_usage_up', 'data_usage_down', 'data_limit')
        }),
        ('Timestamps', {
            'fields': ('expires_at',)
        }),
    )
    
    def has_delete_permission(self, request, obj=None):
        # Only allow deletion through the model's delete_account method
        return True
    
    def live_config(self, obj):
        return obj.get_inbound_from_3xui()
    
    def config_string(self, obj):
        return obj.generate_wireguard_config()
    
    def save_model(self, request, obj, form, change):
        # If this is a new account and status is set to active, create the account
        if not change and obj.status == VPNAccount.STATUS_ACTIVE:
            obj.save()
            obj.create_wireguard_account()
        else:
            super().save_model(request, obj, form, change)
