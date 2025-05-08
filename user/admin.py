from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'address', 'date_of_birth', 'profile_picture', 'social_security_number')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_verified', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_verified', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'is_verified', 'groups')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone_number')


admin.site.register(User, UserAdmin)
