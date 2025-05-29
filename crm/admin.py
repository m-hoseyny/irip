from django.contrib import admin
from django.utils.html import mark_safe
from .models import FAQ, Tutorial, Ticket, TicketReply, TicketAttachment

# Register your models here.

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'order', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('question', 'answer')
    ordering = ('order', 'created_at')


@admin.register(Tutorial)
class TutorialAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'body')
    ordering = ('order', 'created_at')
    readonly_fields = ('html_preview',)
    fieldsets = (
        (None, {
            'fields': ('name', 'body', 'html_preview', 'order', 'is_active')
        }),
    )
    
    def html_preview(self, obj):
        """Display rendered HTML preview in admin"""
        if obj.body:
            return mark_safe(f'<div style="padding: 10px; border: 1px solid #ccc; background-color: #f9f9f9;">{obj.body}</div>')
        return ""
    html_preview.short_description = 'HTML Preview'


class TicketReplyInline(admin.TabularInline):
    model = TicketReply
    extra = 0
    readonly_fields = ('user', 'created_at', 'updated_at')
    fields = ('message', 'is_from_admin', 'is_read_by_admin', 'is_read_by_user', 'user', 'created_at')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return True  # Allow adding replies directly from the ticket admin


class TicketAttachmentInline(admin.TabularInline):
    model = TicketAttachment
    extra = 0
    readonly_fields = ('file_name', 'file_size', 'content_type', 'created_at')
    fields = ('file', 'file_name', 'file_size', 'content_type', 'created_at')
    can_delete = True


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'email', 'status', 'priority', 'is_read_by_admin', 'created_at')
    list_filter = ('status', 'priority', 'is_read_by_admin', 'created_at')
    search_fields = ('subject', 'body', 'email', 'phone_number')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [TicketReplyInline, TicketAttachmentInline]
    fieldsets = (
        (None, {
            'fields': ('subject', 'status', 'priority')
        }),
        ('Customer Information', {
            'fields': ('user', 'email', 'phone_number')
        }),
        ('Message', {
            'fields': ('body',)
        }),
        ('Status Flags', {
            'fields': ('is_read_by_admin', 'is_read_by_user')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, TicketReply) and not instance.pk:  # New reply
                instance.user = request.user
                instance.is_from_admin = True
                instance.is_read_by_admin = True
            instance.save()
        formset.save_m2m()


@admin.register(TicketReply)
class TicketReplyAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket', 'is_from_admin', 'is_read_by_admin', 'is_read_by_user', 'created_at')
    list_filter = ('is_from_admin', 'is_read_by_admin', 'is_read_by_user', 'created_at')
    search_fields = ('message', 'ticket__subject')
    readonly_fields = ('ticket', 'user', 'created_at', 'updated_at')
    inlines = [TicketAttachmentInline]
    fieldsets = (
        (None, {
            'fields': ('ticket', 'message')
        }),
        ('Status', {
            'fields': ('is_from_admin', 'is_read_by_admin', 'is_read_by_user')
        }),
        ('User Information', {
            'fields': ('user',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def has_add_permission(self, request):
        # Replies should be added through the ticket admin or API
        return False


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'file_name', 'ticket', 'reply', 'file_size', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('file_name', 'ticket__subject')
    readonly_fields = ('file_name', 'file_size', 'content_type', 'created_at')
    
    def has_add_permission(self, request):
        # Attachments should be added through the ticket/reply admin or API
        return False
