from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import User, Invitation, EmailOTP


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'user_type_display', 'venue_display',
                    'isp_display', 'status_badge', 'is_activate', 'created_at')
    list_filter = ('usertype', 'venue', 'status', 'is_activate', 'created_at')
    search_fields = ('email', 'username', 'phone_number')
    ordering = ('-created_at',)

    fieldsets = (
        ('Account Information', {
            'fields': ('email', 'username', 'password', 'phone_number')
        }),
        ('Role & Permissions', {
            'fields': ('usertype', 'venue', 'isp', 'level')
        }),
        ('Status', {
            'fields': ('status', 'is_activate', 'is_invited')
        }),
        ('System Fields', {
            'fields': ('is_staff', 'is_superuser', 'device_token'),
            'classes': ('collapse',)
        }),
        ('Important Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at', 'updated_at')

    def isp_display(self, obj):
        if obj.isp:
            return obj.isp.username
        return '-'
    isp_display.short_description = 'ISP'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj and 'isp' in form.base_fields:
            # Limit ISP choices to actual ISPs from the same venue
            if obj.venue:
                form.base_fields['isp'].queryset = User.objects.filter(
                    usertype=2,
                    venue=obj.venue,
                    status=True
                )
            else:
                form.base_fields['isp'].queryset = User.objects.none()
        return form

    def user_type_display(self, obj):
        user_types = {
            1: 'Admin',
            2: 'ISP',
            3: 'Customer'
        }
        return user_types.get(obj.usertype, 'Unknown')
    user_type_display.short_description = 'User Type'

    def venue_display(self, obj):
        if obj.venue:
            return obj.venue.venue_name
        return '-'
    venue_display.short_description = 'Venue'

    def status_badge(self, obj):
        if obj.status:
            return format_html('<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 10px;">Active</span>')
        return format_html('<span style="background-color: #dc3545; color: white; padding: 3px 10px; border-radius: 10px;">Inactive</span>')
    status_badge.short_description = 'Status'


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ('email', 'invited_by', 'created_at', 'token_truncated')
    list_filter = ('created_at', 'invited_by')
    search_fields = ('email', 'invited_by__email')
    readonly_fields = ('created_at',)

    def token_truncated(self, obj):
        return f"{obj.token[:10]}..."
    token_truncated.short_description = 'Token'


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'otp', 'created_at', 'is_expired')
    list_filter = ('created_at',)
    search_fields = ('user__email', 'otp')
    readonly_fields = ('created_at',)

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'

    def is_expired(self, obj):
        # Assuming OTP expires after 10 minutes
        from django.utils import timezone
        from datetime import timedelta
        is_expired = obj.created_at + timedelta(minutes=10) < timezone.now()
        if is_expired:
            return format_html('<span style="color: #dc3545;">Expired</span>')
        return format_html('<span style="color: #28a745;">Valid</span>')
    is_expired.short_description = 'Status'

    def has_add_permission(self, request):
        return False  # Prevent manual OTP creation
