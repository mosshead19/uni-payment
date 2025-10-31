from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import Student, Officer, Organization, FeeType, PaymentRequest, Payment, Receipt, ActivityLog, AcademicYearConfig

# nag add ako admin interfaces - darcy

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['student_id_number', 'get_full_name_display', 'course', 'year_level', 'college', 'pending_payments_count']
    list_filter = ['college', 'course', 'year_level', 'academic_year', 'semester']
    search_fields = ['student_id_number', 'first_name', 'last_name', 'email']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_full_name_display(self, obj):
        return obj.get_full_name()
    get_full_name_display.short_description = 'Full Name'
    
    def pending_payments_count(self, obj):
        return obj.get_pending_payments_count()
    pending_payments_count.short_description = 'Pending Payments'

@admin.register(Officer)
class OfficerAdmin(admin.ModelAdmin):
    list_display = ['employee_id', 'get_full_name_display', 'organization', 'role', 'can_process_payments']
    list_filter = ['organization', 'role', 'can_process_payments']
    search_fields = ['employee_id', 'first_name', 'last_name', 'email']
    
    def get_full_name_display(self, obj):
        return obj.get_full_name()
    get_full_name_display.short_description = 'Full Name'

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'department', 'active_fees_count', 'total_collected']
    search_fields = ['name', 'code', 'department']
    
    def active_fees_count(self, obj):
        return obj.get_active_fees_count()
    active_fees_count.short_description = 'Active Fees'
    
    def total_collected(self, obj):
        return f"₱{obj.get_total_collected()}"
    total_collected.short_description = 'Total Collected'

@admin.register(FeeType)
class FeeTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'amount', 'academic_year', 'semester', 'is_overdue_display']
    list_filter = ['organization', 'academic_year', 'semester']
    search_fields = ['name', 'organization__name']
    
    def is_overdue_display(self, obj):
        return obj.is_overdue()
    is_overdue_display.boolean = True
    is_overdue_display.short_description = 'Overdue'

@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = ['queue_number', 'student_info', 'organization', 'fee_type', 'amount', 'status', 'created_at', 'is_expired_display']
    list_filter = ['status', 'organization', 'created_at']
    search_fields = ['queue_number', 'student__student_id_number', 'student__first_name']
    readonly_fields = ['request_id', 'created_at', 'updated_at', 'expires_at']
    
    def student_info(self, obj):
        return f"{obj.student.student_id_number} - {obj.student.get_full_name()}"
    student_info.short_description = 'Student'
    
    def is_expired_display(self, obj):
        return obj.is_expired()
    is_expired_display.boolean = True
    is_expired_display.short_description = 'Expired'

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['or_number', 'student_info', 'organization', 'amount', 'payment_method', 'status', 'created_at', 'is_void']
    list_filter = ['status', 'payment_method', 'organization', 'created_at']
    search_fields = ['or_number', 'student__student_id_number']
    readonly_fields = ['created_at', 'updated_at']
    
    def student_info(self, obj):
        return f"{obj.student.student_id_number} - {obj.student.get_full_name()}"
    student_info.short_description = 'Student'

@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ['or_number', 'payment_info', 'email_sent', 'sms_sent', 'created_at']
    list_filter = ['email_sent', 'sms_sent', 'created_at']
    search_fields = ['or_number']
    
    def payment_info(self, obj):
        return f"{obj.payment.student.get_full_name()} - ₱{obj.payment.amount}"
    payment_info.short_description = 'Payment'

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'description_short', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['user__username', 'action', 'description']
    readonly_fields = ['created_at']
    
    def description_short(self, obj):
        return obj.description[:50] + "..." if len(obj.description) > 50 else obj.description
    description_short.short_description = 'Description'

@admin.register(AcademicYearConfig)
class AcademicYearConfigAdmin(admin.ModelAdmin):
    list_display = ['academic_year', 'semester', 'start_date', 'end_date', 'is_current']
    list_filter = ['is_current', 'academic_year']
    search_fields = ['academic_year', 'semester']