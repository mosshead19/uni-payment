from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid
from django.db.models import Sum

class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True,verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True,verbose_name="Updated At")
    is_active = models.BooleanField(default=True,verbose_name="Is Active")

    class Meta:
        abstract = True
        ordering = ['-created_at']

# ============================================
# UNIFIED USER PROFILE EXTENSION
# ============================================

class UserProfile(BaseModel):
    """
    Unified profile extension for User model.
    Provides Officer Status Flag for unified login system.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='user_profile',
        verbose_name="User"
    )
    is_officer = models.BooleanField(
        default=False,
        verbose_name="Officer Status Flag",
        help_text="Grants officer-exclusive abilities when enabled"
    )
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
    
    def __str__(self):
        return f"{self.user.username} - {'Officer' if self.is_officer else 'Student'}"

# USER PROFILE MODELS

class College(BaseModel):
    name = models.CharField(max_length=200, unique=True, verbose_name="College/Department Name")
    code = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Code")
    description = models.TextField(blank=True, verbose_name="Description")

    class Meta:
        verbose_name = "College/Department"
        verbose_name_plural = "Colleges/Departments"
        ordering = ['name']

    def __str__(self):
        return self.name

class Course(BaseModel):
    """
    Academic programs/courses.
    System supports ONLY these 5 programs: Medical Biology, Marine Biology, 
    Computer Science, Environmental Science, Information Technology
    """
    PROGRAM_CHOICES = [
        ('MEDICAL_BIOLOGY', 'Medical Biology'),
        ('MARINE_BIOLOGY', 'Marine Biology'),
        ('COMPUTER_SCIENCE', 'Computer Science'),
        ('ENVIRONMENTAL_SCIENCE', 'Environmental Science'),
        ('INFORMATION_TECHNOLOGY', 'Information Technology'),
        ('OTHER', 'Other'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="Course/Program Name")
    code = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Code")
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name='courses', verbose_name="College/Department")
    program_type = models.CharField(
        max_length=50,
        choices=PROGRAM_CHOICES,
        default='MEDICAL_BIOLOGY',
        verbose_name="Program Type",
        help_text="Select one of the 5 supported programs: Medical Biology, Marine Biology, Computer Science, Environmental Science, or Information Technology"
    )
    description = models.TextField(blank=True, verbose_name="Description")

    class Meta:
        verbose_name = "Course/Program"
        verbose_name_plural = "Courses/Programs"
        ordering = ['college', 'name']
        unique_together = [['name', 'college']]

    def __str__(self):
        return f"{self.name} ({self.college.name})"
    
    def is_program_specific(self):
        """Check if this course is one of the 5 supported programs"""
        return self.program_type != 'OTHER'
    
    def get_logo_path(self):
        """Get the static path to the program logo"""
        from django.contrib.staticfiles.storage import staticfiles_storage
        from django.conf import settings
        
        logo_map = {
            'MEDICAL_BIOLOGY': 'Medical Biology.png',
            'MARINE_BIOLOGY': 'Marine Biology.png',
            'COMPUTER_SCIENCE': 'Computer Science.png',
            'ENVIRONMENTAL_SCIENCE': 'Environmental Science.png',
            'INFORMATION_TECHNOLOGY': 'Information Technology.png',
        }
        
        logo_filename = logo_map.get(self.program_type)
        if logo_filename:
            try:
                return staticfiles_storage.url(logo_filename)
            except:
                # Fallback to manual URL construction
                return f"{settings.STATIC_URL}{logo_filename}"
        return None

class Student(BaseModel):
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='student_profile'
    )
    student_id_number = models.CharField(
        max_length=20, 
        unique=True, 
        verbose_name="Student ID Number",
        help_text="University student ID (e.g., 2021-12345)"
    )
    first_name = models.CharField(max_length=100, verbose_name="First Name")
    last_name = models.CharField(max_length=100, verbose_name="Last Name")
    middle_name = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name="Middle Name"
    )
    
    # Academic Information
    course = models.ForeignKey(
        'Course',
        on_delete=models.PROTECT,
        related_name='students',
        verbose_name="Course/Program",
        help_text="Select your course/program",
        null=True,
        blank=True
    )
    year_level = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Year Level",
        help_text="1, 2, 3, 4, or 5"
    )
    college = models.ForeignKey(
        'College',
        on_delete=models.PROTECT,
        related_name='students',
        verbose_name="College/Department",
        help_text="Select your college/department",
        null=True,
        blank=True
    )
    
    # Contact Information
    email = models.EmailField(unique=True, verbose_name="Email Address")
    phone_number = models.CharField(
        max_length=15, 
        verbose_name="Phone Number",
        help_text="Format: 09XX-XXX-XXXX"
    )
    
    # Enrollment Info
    academic_year = models.CharField(
        max_length=20,
        verbose_name="Academic Year",
        help_text="e.g., 2024-2025",
        default="2024-2025"
    )
    semester = models.CharField(
        max_length=20,
        verbose_name="Current Semester",
        choices=[
            ('1st Semester', '1st Semester'),
            ('2nd Semester', '2nd Semester'),
            ('Summer', 'Summer'),
        ],
        default='1st Semester'
    )

    class Meta:
        verbose_name = "Student"
        verbose_name_plural = "Students"
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.student_id_number} - {self.get_full_name()}"

    def get_full_name(self):
        """Return full name with middle initial"""
        if self.middle_name:
            return f"{self.first_name} {self.middle_name[0]}. {self.last_name}"
        return f"{self.first_name} {self.last_name}"

    def get_pending_payments_count(self):
        """Get count of unpaid fees"""
        return self.payment_requests.filter(status='PENDING').count()

    def get_pending_payments(self):
        """Get all pending payment requests for this student"""
        return self.payment_requests.filter(status='PENDING')

    def get_completed_payments(self):
        """Get all completed payments for this student (excluding voided)"""
        return Payment.objects.filter(student=self, status='COMPLETED', is_void=False)
    
    def get_applicable_fees(self):
        """
        Get all applicable fees for this student based on two-tiered system:
        Tier 1: Program Affiliation Fees (specific to student's program)
        Tier 2: College-Based Organization Fees (mandatory for all)
        """
        from django.db.models import Q
        
        if not self.course:
            return FeeType.objects.none()
        
        current_period = self._get_current_period()
        if not current_period:
            return FeeType.objects.none()
        
        # Tier 1: Program-specific fees (only for student's specific program)
        tier1_fees = FeeType.objects.filter(
            organization__fee_tier='TIER_1',
            organization__program_affiliation=self.course.program_type,
            is_active=True,
            academic_year=current_period.academic_year,
            semester=current_period.semester
        ).filter(
            Q(applicable_year_levels__icontains=str(self.year_level)) |
            Q(applicable_year_levels__iexact='All')
        )
        
        # Tier 2: College-wide mandatory fees (for all students)
        tier2_fees = FeeType.objects.filter(
            organization__fee_tier='TIER_2',
            is_active=True,
            academic_year=current_period.academic_year,
            semester=current_period.semester
        ).filter(
            Q(applicable_year_levels__icontains=str(self.year_level)) |
            Q(applicable_year_levels__iexact='All')
        )
        
        # Combine both tiers
        all_fees = (tier1_fees | tier2_fees).distinct()
        
        # Exclude already paid fees
        paid_fee_ids = Payment.objects.filter(
            student=self,
            status='COMPLETED',
            is_void=False
        ).values_list('fee_type_id', flat=True)
        
        # Exclude pending payment requests
        pending_fee_ids = PaymentRequest.objects.filter(
            student=self,
            status='PENDING'
        ).values_list('fee_type_id', flat=True)
        
        return all_fees.exclude(id__in=list(paid_fee_ids) + list(pending_fee_ids))
    
    def get_total_outstanding_fees(self):
        """Calculate total amount of outstanding fees"""
        fees = self.get_applicable_fees()
        return fees.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    def get_tier1_fees(self):
        """Get Tier 1 (Program-specific) fees"""
        from django.db.models import Q
        
        if not self.course:
            return FeeType.objects.none()
        
        current_period = self._get_current_period()
        if not current_period:
            return FeeType.objects.none()
        
        return FeeType.objects.filter(
            organization__fee_tier='TIER_1',
            organization__program_affiliation=self.course.program_type,
            is_active=True,
            academic_year=current_period.academic_year,
            semester=current_period.semester
        ).filter(
            Q(applicable_year_levels__icontains=str(self.year_level)) |
            Q(applicable_year_levels__iexact='All')
        )
    
    def get_tier2_fees(self):
        """Get Tier 2 (College-wide mandatory) fees"""
        from django.db.models import Q
        
        current_period = self._get_current_period()
        if not current_period:
            return FeeType.objects.none()
        
        return FeeType.objects.filter(
            organization__fee_tier='TIER_2',
            is_active=True,
            academic_year=current_period.academic_year,
            semester=current_period.semester
        ).filter(
            Q(applicable_year_levels__icontains=str(self.year_level)) |
            Q(applicable_year_levels__iexact='All')
        )
    
    def _get_current_period(self):
        """Helper method to get current academic period"""
        try:
            return AcademicYearConfig.objects.get(is_current=True)
        except AcademicYearConfig.DoesNotExist:
            return None
        except AcademicYearConfig.MultipleObjectsReturned:
            return AcademicYearConfig.objects.filter(is_current=True).order_by('-start_date').first()


class Officer(BaseModel):
    """
    Organization officer who can process payments
    """
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='officer_profile'
    )
    employee_id = models.CharField(
        max_length=20, 
        unique=True, 
        verbose_name="Employee/Officer ID"
    )
    first_name = models.CharField(max_length=100, verbose_name="First Name")
    last_name = models.CharField(max_length=100, verbose_name="Last Name")
    
    organization = models.ForeignKey(
        'Organization',
        on_delete=models.CASCADE,
        related_name='officers',
        verbose_name="Organization"
    )
    
    role = models.CharField(
        max_length=50,
        verbose_name="Role/Position",
        help_text="e.g., Treasurer, President, Finance Officer"
    )
    
    # Permissions
    can_process_payments = models.BooleanField(
        default=True,
        verbose_name="Can Process Payments"
    )
    can_void_payments = models.BooleanField(
        default=False,
        verbose_name="Can Void Payments"
    )
    can_generate_reports = models.BooleanField(
        default=False,
        verbose_name="Can Generate Reports"
    )
    
    # Contact
    email = models.EmailField(verbose_name="Email Address")
    phone_number = models.CharField(max_length=15, verbose_name="Phone Number")

    class Meta:
        verbose_name = "Officer"
        verbose_name_plural = "Officers"
        ordering = ['organization', 'last_name']

    def __str__(self):
        return f"{self.get_full_name()} - {self.organization.code}"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"


# ============================================
# ORGANIZATION & FEE MODELS
# ============================================

class Organization(BaseModel):
    """
    Student organizations that collect fees.
    Supports two-tiered fee system:
    - TIER_1: Program Affiliation Fees (specific to academic programs)
    - TIER_2: College-Based Organization Fees (mandatory for all students)
    """
    FEE_TIER_CHOICES = [
        ('TIER_1', 'Tier 1: Program Affiliation Fees'),
        ('TIER_2', 'Tier 2: College-Based Organization Fees'),
    ]
    
    PROGRAM_AFFILIATION_CHOICES = [
        ('MEDICAL_BIOLOGY', 'Medical Biology'),
        ('MARINE_BIOLOGY', 'Marine Biology'),
        ('COMPUTER_SCIENCE', 'Computer Science'),
        ('ENVIRONMENTAL_SCIENCE', 'Environmental Science'),
        ('INFORMATION_TECHNOLOGY', 'Information Technology'),
        ('ALL', 'All Programs'),
    ]
    
    name = models.CharField(
        max_length=200, 
        unique=True, 
        verbose_name="Organization Name"
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Organization Code",
        help_text="Short code (e.g., CSG, COMPENDIUM, MBIO)"
    )
    department = models.CharField(
        max_length=100,
        verbose_name="Department/College",
        help_text="e.g., College of Sciences"
    )
    
    # Two-Tiered Fee System
    fee_tier = models.CharField(
        max_length=10,
        choices=FEE_TIER_CHOICES,
        default='TIER_2',
        verbose_name="Fee Tier",
        help_text="Tier 1: Program-specific fees. Tier 2: College-wide mandatory fees."
    )
    program_affiliation = models.CharField(
        max_length=50,
        choices=PROGRAM_AFFILIATION_CHOICES,
        blank=True,
        null=True,
        default='ALL',
        verbose_name="Program Affiliation",
        help_text="Required for Tier 1 fees. Select the specific program this organization serves."
    )
    
    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )
    
    # Contact Information
    contact_email = models.EmailField(verbose_name="Contact Email")
    contact_phone = models.CharField(
        max_length=15,
        verbose_name="Contact Phone",
        blank=True
    )
    
    # Payment Booth Location
    booth_location = models.CharField(
        max_length=200,
        verbose_name="Payment Booth Location",
        help_text="e.g., Ground Floor, Main Building"
    )

    class Meta:
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"
        ordering = ['fee_tier', 'name']

    def __str__(self):
        return f"{self.name} ({self.code}) - {self.get_fee_tier_display()}"
    
    def clean(self):
        """Validate that Tier 1 organizations have program affiliation"""
        from django.core.exceptions import ValidationError
        if self.fee_tier == 'TIER_1' and not self.program_affiliation:
            raise ValidationError({
                'program_affiliation': 'Program affiliation is required for Tier 1 (Program-specific) organizations.'
            })
        if self.fee_tier == 'TIER_2' and self.program_affiliation and self.program_affiliation != 'ALL':
            # Tier 2 should typically be for all programs, but allow flexibility
            pass

    def get_active_fees_count(self):
        """Get count of active fee types"""
        return self.fee_types.filter(is_active=True).count()

    def get_total_collected(self):
        """Get total amount collected (excluding voided payments)"""
        total = self.payments.filter(status='COMPLETED', is_void=False).aggregate(
            total=models.Sum('amount')
        )
        return total['total'] or Decimal('0.00')

    def get_today_collection(self):
        """Get today's total collection (excluding voided payments)"""
        today = timezone.now().date()
        total = self.payments.filter(
            status='COMPLETED',
            is_void=False,
            created_at__date=today
        ).aggregate(total=models.Sum('amount'))
        return total['total'] or Decimal('0.00')

    def get_pending_requests_count(self):
        """Get count of pending payment requests"""
        return self.payment_requests.filter(status='PENDING').count()
    
    def get_logo_path(self):
        """Get the static path to the organization logo"""
        from django.contrib.staticfiles.storage import staticfiles_storage
        from django.conf import settings
        
        name_logo_map = {
            'College Student Government': 'College Student Government.png',
            'Compendium': 'Compendium.png',
        }
        
        program_logo_map = {
            'MEDICAL_BIOLOGY': 'Medical Biology.png',
            'MARINE_BIOLOGY': 'Marine Biology.png',
            'COMPUTER_SCIENCE': 'Computer Science.png',
            'ENVIRONMENTAL_SCIENCE': 'Environmental Science.png',
            'INFORMATION_TECHNOLOGY': 'Information Technology.png',
        }
        
        logo_filename = name_logo_map.get(self.name)
        if not logo_filename and self.program_affiliation:
            logo_filename = program_logo_map.get(self.program_affiliation)
        
        if not logo_filename:
            return None
        
        try:
            return staticfiles_storage.url(logo_filename)
        except:
            # Fallback to manual URL construction
            return f"{settings.STATIC_URL}{logo_filename}"


class FeeType(BaseModel):
    """
    Types of fees collected by organizations
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='fee_types',
        verbose_name="Organization"
    )
    
    name = models.CharField(
        max_length=100,
        verbose_name="Fee Name",
        help_text="e.g., Publication Fee, College Fee"
    )
    
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Amount (₱)"
    )
    
    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )
    
    # Applicable Period
    academic_year = models.CharField(
        max_length=20,
        verbose_name="Academic Year",
        help_text="e.g., 2024-2025"
    )
    semester = models.CharField(
        max_length=20,
        verbose_name="Semester",
        choices=[
            ('1st Semester', '1st Semester'),
            ('2nd Semester', '2nd Semester'),
            ('Summer', 'Summer'),
            ('Whole Year', 'Whole Year'),
        ]
    )
    
    # Applicable to which students
    applicable_year_levels = models.CharField(
        max_length=50,
        verbose_name="Applicable Year Levels",
        help_text="e.g., '1,2,3,4' or 'All'",
        default="All"
    )
    
    # Deadline
    deadline = models.DateField(
        verbose_name="Payment Deadline",
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Fee Type"
        verbose_name_plural = "Fee Types"
        ordering = ['organization', 'name']
        unique_together = ['organization', 'name', 'academic_year', 'semester']

    def __str__(self):
        return f"{self.organization.code} - {self.name} (₱{self.amount})"

    def is_overdue(self):
        """Check if fee is past deadline"""
        if self.deadline:
            return timezone.now().date() > self.deadline
        return False


# ============================================
# PAYMENT MODELS
# ============================================

class PaymentRequest(BaseModel):
    """
    Payment request created when student generates QR code
    """
    # Unique identifier
    request_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name="Request ID"
    )
    
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='payment_requests',
        verbose_name="Student"
    )
    
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='payment_requests',
        verbose_name="Organization"
    )
    
    fee_type = models.ForeignKey(
        FeeType,
        on_delete=models.CASCADE,
        related_name='payment_requests',
        verbose_name="Fee Type"
    )
    
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Amount (₱)"
    )
    
    # Payment Method (selected by student when generating QR)
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('CASH', 'Cash'),
            ('GCASH', 'GCash'),
            ('BANK', 'Bank Transfer'),
        ],
        default='CASH',
        verbose_name="Payment Method",
        help_text="Payment method selected by student"
    )
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('PAID', 'Paid'),
            ('CANCELLED', 'Cancelled'),
            ('EXPIRED', 'Expired'),
        ],
        default='PENDING',
        verbose_name="Status"
    )
    
    # QR Code Data
    qr_signature = models.CharField(
        max_length=128,
        verbose_name="QR Signature",
        help_text="HMAC signature for validation"
    )
    
    # Timestamps
    expires_at = models.DateTimeField(verbose_name="Expires At")
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Paid At"
    )

    class Meta:
        verbose_name = "Payment Request"
        verbose_name_plural = "Payment Requests"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['student', 'status']),
        ]

    def __str__(self):
        return f"{self.student.student_id_number} - {self.fee_type.name} - ₱{self.amount}"

    def is_expired(self):
        """Check if payment request has expired"""
        return timezone.now() > self.expires_at and self.status == 'PENDING'

    def mark_as_paid(self):
        """Update status to paid"""
        self.status = 'PAID'
        self.paid_at = timezone.now()
        self.save()

    def mark_as_cancelled(self):
        """Update status to cancelled"""
        self.status = 'CANCELLED'
        self.save()

    def get_time_remaining(self):
        """Get human-readable time remaining"""
        from django.utils.timesince import timeuntil
        if self.status == 'PENDING' and not self.is_expired():
            return timeuntil(self.expires_at, timezone.now())
        return "Expired" if self.is_expired() else "Completed"


class Payment(BaseModel):
    """
    Actual payment record after cash is received
    """
    payment_request = models.OneToOneField(
        PaymentRequest,
        on_delete=models.CASCADE,
        related_name='payment',
        verbose_name="Payment Request",
        null=True,
        blank=True,
        help_text="Leave blank for direct payments (not from QR code)"
    )
    
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name="Student"
    )
    
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name="Organization"
    )
    
    fee_type = models.ForeignKey(
        FeeType,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name="Fee Type"
    )
    
    # Amount Details
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Fee Amount (₱)"
    )
    amount_received = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Amount Received (₱)"
    )
    change_given = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Change Given (₱)"
    )
    
    # Receipt Information
    or_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Official Receipt Number"
    )
    
    # Payment Details
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('CASH', 'Cash'),
            ('GCASH', 'GCash'),
            ('BANK', 'Bank Transfer'),
        ],
        default='CASH',
        verbose_name="Payment Method"
    )
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('COMPLETED', 'Completed'),
            ('VOID', 'Void'),
        ],
        default='COMPLETED',
        verbose_name="Status"
    )
    
    # Processed By
    processed_by = models.ForeignKey(
        Officer,
        on_delete=models.SET_NULL,
        null=True,
        related_name='processed_payments',
        verbose_name="Processed By"
    )
    
    # Void Information
    is_void = models.BooleanField(default=False, verbose_name="Is Void")
    void_reason = models.TextField(
        blank=True,
        null=True,
        verbose_name="Void Reason"
    )
    voided_by = models.ForeignKey(
        Officer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='voided_payments',
        verbose_name="Voided By"
    )
    voided_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Voided At"
    )
    
    # Additional Notes
    notes = models.TextField(
        blank=True,
        verbose_name="Notes"
    )

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['or_number']),
            models.Index(fields=['student']),
            models.Index(fields=['organization']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"OR#{self.or_number} - {self.student.student_id_number} - ₱{self.amount}"

    def save(self, *args, **kwargs):
        """Calculate change before saving"""
        if self.amount_received and self.amount:
            self.change_given = self.amount_received - self.amount
        super().save(*args, **kwargs)

    def mark_as_void(self, officer, reason):
        """Mark payment as void"""
        self.status = 'VOID'
        self.is_void = True
        self.void_reason = reason
        self.voided_by = officer
        self.voided_at = timezone.now()
        self.save()


class Receipt(BaseModel):
    """
    Receipt generated after payment
    """
    payment = models.OneToOneField(
        Payment,
        on_delete=models.CASCADE,
        related_name='receipt',
        verbose_name="Payment"
    )
    
    or_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Official Receipt Number"
    )
    
    # File Storage
    receipt_pdf = models.FileField(
        upload_to='receipts/pdf/%Y/%m/',
        verbose_name="Receipt PDF",
        null=True,
        blank=True
    )
    
    receipt_qr = models.ImageField(
        upload_to='receipts/qr/%Y/%m/',
        verbose_name="Receipt QR Code",
        null=True,
        blank=True
    )
    
    # Verification
    verification_signature = models.CharField(
        max_length=128,
        verbose_name="Verification Signature",
        help_text="HMAC signature for receipt verification"
    )
    
    # Email Status
    email_sent = models.BooleanField(
        default=False,
        verbose_name="Email Sent"
    )
    email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Email Sent At"
    )
    
    # SMS Status
    sms_sent = models.BooleanField(
        default=False,
        verbose_name="SMS Sent"
    )
    sms_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="SMS Sent At"
    )

    class Meta:
        verbose_name = "Receipt"
        verbose_name_plural = "Receipts"
        ordering = ['-created_at']

    def __str__(self):
        return f"Receipt OR#{self.or_number}"


# ============================================
# ACTIVITY LOG MODEL
# ============================================

class ActivityLog(BaseModel):
    """
    Log all important activities for audit trail
    """
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='activity_logs',
        verbose_name="User"
    )
    
    action = models.CharField(
        max_length=50,
        verbose_name="Action",
        help_text="e.g., PAYMENT_PROCESSED, QR_GENERATED"
    )
    
    description = models.TextField(verbose_name="Description")
    
    # Related Objects (optional)
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs',
        verbose_name="Payment"
    )
    
    payment_request = models.ForeignKey(
        PaymentRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs',
        verbose_name="Payment Request"
    )
    
    # IP Address
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP Address"
    )

    class Meta:
        verbose_name = "Activity Log"
        verbose_name_plural = "Activity Logs"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['action', 'created_at']),
        ]

    def __str__(self):
        user_name = self.user.username if self.user else "System"
        return f"{user_name} - {self.action} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


# ============================================
# ACADEMIC YEAR CONFIGURATION
# ============================================

class AcademicYearConfig(BaseModel):
    """
    Configuration for academic year and semester
    """
    academic_year = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Academic Year",
        help_text="e.g., 2024-2025"
    )
    
    semester = models.CharField(
        max_length=20,
        verbose_name="Semester",
        choices=[
            ('1st Semester', '1st Semester'),
            ('2nd Semester', '2nd Semester'),
            ('Summer', 'Summer'),
        ]
    )
    
    start_date = models.DateField(verbose_name="Start Date")
    end_date = models.DateField(verbose_name="End Date")
    
    is_current = models.BooleanField(
        default=False,
        verbose_name="Is Current Period"
    )

    class Meta:
        verbose_name = "Academic Year Configuration"
        verbose_name_plural = "Academic Year Configurations"
        ordering = ['-start_date']
        unique_together = ['academic_year', 'semester']

    def __str__(self):
        return f"{self.academic_year} - {self.semester}"

    def save(self, *args, **kwargs):
        """Ensure only one period is marked as current"""
        if self.is_current:
            # Prevents race conditions by excluding the current object (self.pk)
            AcademicYearConfig.objects.filter(is_current=True).exclude(pk=self.pk).update(is_current=False) 
        super().save(*args, **kwargs)