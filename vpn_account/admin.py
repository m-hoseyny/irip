from django.contrib import admin
from .models import VPNAccount


@admin.register(VPNAccount)
class VPNAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'email', 'protocol', 'port', 'status', 'created_at')
    list_filter = ('status', 'protocol')
    search_fields = ('email', 'user__email', 'user__username')
    readonly_fields = ('account_id', 'inbound_id', 'config_file', 'config_data', 
                      'data_usage_up', 'data_usage_down')
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
            'fields': ('config_data', 'config_file'),
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
        return False
    
    def save_model(self, request, obj, form, change):
        # If this is a new account and status is set to active, create the account
        if not change and obj.status == VPNAccount.STATUS_ACTIVE:
            obj.save()
            obj.create_wireguard_account()
        else:
            super().save_model(request, obj, form, change)
