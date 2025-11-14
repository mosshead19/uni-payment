from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import (
    Student, Officer, Organization, FeeType,
    PaymentRequest, Payment, Receipt,
    ActivityLog, AcademicYearConfig, Course, College, UserProfile
)

# custom user admin to show profiles
class StudentInline(admin.StackedInline):
    model = Student
    can_delete = False
    verbose_name_plural = 'Student Profile'
    
class OfficerInline(admin.StackedInline):
    model = Officer
    can_delete = False
    verbose_name_plural = 'Officer Profile'

class CustomUserAdmin(UserAdmin):
    inlines = [StudentInline, OfficerInline]
    
# unregister default user and register custom one
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, CustomUserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_officer', 'is_active', 'created_at')
    list_display_links = ('user',)
    list_filter = ('is_officer', 'is_active')
    search_fields = ('user__username', 'user__email')
    list_editable = ('is_officer', 'is_active')
    raw_id_fields = ('user',)

@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'created_at')
    list_display_links = ('name',)
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    list_editable = ('is_active',)

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'college', 'program_type', 'is_active', 'created_at')
    list_display_links = ('name',)
    list_filter = ('college', 'program_type', 'is_active')
    search_fields = ('name', 'code', 'college__name')
    list_editable = ('is_active',)

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        'student_id_number', 'get_full_name_display', 'course',
        'year_level', 'college', 'pending_payments_count_display', 'is_active'
    )
    list_display_links = ('student_id_number', 'get_full_name_display')
    list_filter = ('college', 'course', 'year_level', 'academic_year', 'semester', 'is_active')
    search_fields = ('student_id_number', 'first_name', 'last_name', 'email')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active',)
    list_per_page = 50
    
    fieldsets = (
        (None, {
            'fields': ('user', 'student_id_number', 'is_active')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'middle_name', 'email', 'phone_number')
        }),
        ('Academic Information', {
            'fields': ('course', 'year_level', 'college', 'academic_year', 'semester')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_full_name_display(self, obj):
        return obj.get_full_name()
    get_full_name_display.short_description = 'Full Name'
    get_full_name_display.admin_order_field = 'last_name'
    
    def pending_payments_count_display(self, obj):
        count = obj.get_pending_payments_count()
        color = 'red' if count > 0 else 'green'
        return format_html('<span style="color: {};">{}</span>', color, count)
    pending_payments_count_display.short_description = 'Pending Fees'

@admin.register(Officer)
class OfficerAdmin(admin.ModelAdmin):
    list_display = (
        'employee_id', 'get_full_name_display', 'organization', 'role',
        'can_process_payments', 'can_void_payments', 'is_active'
    )
    list_display_links = ('employee_id', 'get_full_name_display')
    list_filter = ('organization', 'role', 'can_process_payments', 'can_void_payments', 'is_active')
    search_fields = ('employee_id', 'first_name', 'last_name', 'email', 'organization__code')
    list_editable = ('can_process_payments', 'can_void_payments', 'is_active')
    list_per_page = 50
    
    def get_full_name_display(self, obj):
        return obj.get_full_name()
    get_full_name_display.short_description = 'Full Name'
    get_full_name_display.admin_order_field = 'last_name'

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'code', 'fee_tier', 'program_affiliation', 'department', 
        'active_fees_count_display', 'total_collected_display', 
        'today_collection_display', 'pending_requests_display', 'is_active'
    )
    list_display_links = ('name', 'code')
    search_fields = ('name', 'code', 'department')
    list_filter = ('fee_tier', 'program_affiliation', 'department', 'is_active')
    list_editable = ('is_active',)
    list_per_page = 50
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'is_active')
        }),
        ('Two-Tiered Fee System', {
            'fields': ('fee_tier', 'program_affiliation'),
            'description': 'Tier 1: Program-specific fees. Tier 2: College-wide mandatory fees.'
        }),
        ('Organization Details', {
            'fields': ('department', 'description', 'contact_email', 'contact_phone', 'booth_location')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def active_fees_count_display(self, obj):
        return obj.get_active_fees_count()
    active_fees_count_display.short_description = 'Active Fees'
    
    def total_collected_display(self, obj):
        total = obj.get_total_collected()
        return format_html('<b>₱{:.2f}</b>', total)
    total_collected_display.short_description = 'Total Collected (Net)'
    
    def today_collection_display(self, obj):
        total = obj.get_today_collection()
        return format_html('₱{:.2f}', total)
    today_collection_display.short_description = 'Today Collected (Net)'
    
    def pending_requests_display(self, obj):
        count = obj.get_pending_requests_count()
        color = 'orange' if count > 0 else 'green'
        return format_html('<span style="color: {};">{}</span>', color, count)
    pending_requests_display.short_description = 'Pending Requests'

@admin.register(FeeType)
class FeeTypeAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'organization', 'amount', 'academic_year',
        'semester', 'applicable_year_levels', 'is_overdue_display', 'is_active'
    )
    list_display_links = ('name',)
    list_filter = ('organization', 'academic_year', 'semester', 'is_active')
    search_fields = ('name', 'organization__name', 'academic_year')
    list_editable = ('is_active',)
    list_per_page = 50
    
    def is_overdue_display(self, obj):
        overdue = obj.is_overdue()
        status = 'Yes' if overdue else 'No'
        color = 'red' if overdue else 'green'
        return format_html('<span style="color: {};">{}</span>', color, status)
    is_overdue_display.short_description = 'Overdue'

@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = (
        'queue_number', 'student_info', 'organization', 'fee_type',
        'amount', 'status_display', 'created_at', 'expires_at', 'is_expired_display'
    )
    list_display_links = ('queue_number',)
    list_filter = ('status', 'organization', 'created_at', 'is_active')
    search_fields = ('queue_number', 'student__student_id_number', 'student__last_name', 'organization__code')
    readonly_fields = (
        'request_id', 'student', 'organization', 'fee_type',
        'qr_signature', 'created_at', 'updated_at', 'expires_at', 'paid_at',
        'amount', 'queue_number', 'status'
    )
    list_per_page = 50
    actions = ['mark_as_cancelled_action', 'mark_as_expired_action']
    
    def student_info(self, obj):
        return f"{obj.student.student_id_number} - {obj.student.get_full_name()}"
    student_info.short_description = 'Student'
    
    def is_expired_display(self, obj):
        expired = obj.is_expired()
        status = 'Yes' if expired else 'No'
        color = 'red' if expired else 'green'
        if obj.status != 'PENDING':
            return 'N/A'
        return format_html('<span style="color: {};">{}</span>', color, status)
    is_expired_display.short_description = 'Expired'
    
    def status_display(self, obj):
        color_map = {
            'PENDING': 'orange',
            'PAID': 'green',
            'CANCELLED': 'gray',
            'EXPIRED': 'red'
        }
        return format_html(
            '<span style="color: {};"><b>{}</b></span>',
            color_map.get(obj.status, 'black'),
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def mark_as_cancelled_action(self, request, queryset):
        updated = queryset.filter(status='PENDING').update(status='CANCELLED')
        self.message_user(request, f"{updated} payment requests marked as CANCELLED.", messages.SUCCESS)
    mark_as_cancelled_action.short_description = "Mark selected as CANCELLED"
    
    def mark_as_expired_action(self, request, queryset):
        updated = queryset.filter(status='PENDING').update(status='EXPIRED')
        self.message_user(request, f"{updated} payment requests marked as EXPIRED.", messages.SUCCESS)
    mark_as_expired_action.short_description = "Mark selected as EXPIRED"

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'or_number', 'student_info', 'organization', 'amount',
        'payment_method', 'status_display', 'created_at', 'processed_by'
    )
    list_display_links = ('or_number',)
    list_filter = ('status', 'payment_method', 'organization', 'created_at', 'is_void', 'is_active')
    search_fields = ('or_number', 'student__student_id_number', 'organization__code')
    readonly_fields = [f.name for f in Payment._meta.fields] 
    list_per_page = 50
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
        
    def student_info(self, obj):
        return f"{obj.student.student_id_number} - {obj.student.get_full_name()}"
    student_info.short_description = 'Student'
    
    def status_display(self, obj):
        if obj.is_void:
            return format_html('<span style="color: red;"><b>VOID</b></span>')
        return format_html('<span style="color: green;"><b>{}</b></span>', obj.get_status_display())
    status_display.short_description = 'Status'

@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('or_number', 'payment_info', 'email_sent', 'created_at')
    list_display_links = ('or_number',)
    list_filter = ('email_sent', 'created_at', 'is_active')
    search_fields = ('or_number', 'payment__student__student_id_number')
    readonly_fields = [f.name for f in Receipt._meta.fields] 
    list_per_page = 50
    
    def payment_info(self, obj):
        if obj.payment and obj.payment.student:
             return f"{obj.payment.student.get_full_name()} - ₱{obj.payment.amount:.2f}"
        return "N/A"
    payment_info.short_description = 'Payment'

    def has_add_permission(self, request):
        return False

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'action', 'description_short', 'ip_address')
    list_display_links = ('created_at', 'user', 'action')
    list_filter = ('action', 'created_at', 'is_active')
    search_fields = ('user__username', 'action', 'description', 'ip_address')
    readonly_fields = [f.name for f in ActivityLog._meta.fields]
    list_per_page = 100
    
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def description_short(self, obj):
        return (obj.description[:75] + "...") if len(obj.description) > 75 else obj.description
    description_short.short_description = 'Description'

@admin.register(AcademicYearConfig)
class AcademicYearConfigAdmin(admin.ModelAdmin):
    list_display = ('academic_year', 'semester', 'start_date', 'end_date', 'is_current')
    list_display_links = ('academic_year', 'semester')
    list_filter = ('is_current', 'academic_year', 'is_active')
    search_fields = ('academic_year', 'semester')
    actions = ['set_as_current']

    def set_as_current(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Please select exactly one period to set as current.", level='ERROR')
            return
        
        config = queryset.first()
        if config:
            config.is_current = True
            config.save() 
            self.message_user(request, f"{config} has been set as the current period.", messages.SUCCESS)
    
    set_as_current.short_description = "Set selected period as current"