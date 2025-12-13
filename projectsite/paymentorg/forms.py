from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from django.db.models import Q
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction

from .models import (
    Student, Organization, FeeType, PaymentRequest,
    Payment, Officer, AcademicYearConfig, Course, College, UserProfile
)

# ==================== registration forms ====================
class StudentRegistrationForm(UserCreationForm):
    student_id_number = forms.CharField(
        max_length=20,
        label="Student ID Number",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '2021-12345'})
    )
    first_name = forms.CharField(
        max_length=100,
        label="First Name",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=100,
        label="Last Name",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    phone_number = forms.CharField(
        max_length=15,
        label="Phone Number",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '09XX-XXX-XXXX'}),
        required=False
    )
    college = forms.ModelChoiceField(
        queryset=College.objects.none(),
        label="College/Department",
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Select College/Department",
        help_text="College of Sciences (COS) - This system is designed for College of Sciences only"
    )
    course = forms.ModelChoiceField(
        queryset=Course.objects.none(),
        label="Course/Program",
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Select Course/Program",
        help_text="Select one of the 5 supported programs: Medical Biology, Marine Biology, Computer Science, Environmental Science, or Information Technology"
    )
    year_level = forms.IntegerField(
        min_value=1, max_value=5,
        label="Year Level",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['username',]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Choose a Username'}),
        }

    def clean_student_id_number(self):
        student_id = self.cleaned_data['student_id_number']
        if Student.objects.filter(student_id_number=student_id).exists():
            raise ValidationError("This student ID is already registered.")
        return student_id

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists() or \
           Student.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered.")
        return email
    
    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise ValidationError("This username is already taken.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        course = cleaned_data.get('course')
        college = cleaned_data.get('college')
        
        if course and college and course.college != college:
            raise ValidationError("The selected course does not belong to the selected college.")
        
        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            Student.objects.create(
                user=user,
                student_id_number=self.cleaned_data['student_id_number'],
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name'],
                email=self.cleaned_data['email'],
                phone_number=self.cleaned_data['phone_number'],
                course=self.cleaned_data['course'],
                year_level=self.cleaned_data['year_level'],
                college=self.cleaned_data['college']
            )
            # Create/update UserProfile with Officer Status Flag (False for students)
            UserProfile.objects.get_or_create(
                user=user,
                defaults={'is_officer': False}
            )
        return user

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # System is focused on College of Sciences only
        colleges_qs = College.objects.filter(code="COS", is_active=True).order_by('name')
        # Only show the 5 supported programs (filter by program_type to exclude 'OTHER')
        courses_qs = Course.objects.filter(
            college__code="COS", 
            is_active=True,
            program_type__in=['MEDICAL_BIOLOGY', 'MARINE_BIOLOGY', 'COMPUTER_SCIENCE', 'ENVIRONMENTAL_SCIENCE', 'INFORMATION_TECHNOLOGY']
        ).select_related('college').order_by('name')

        self.fields['college'].queryset = colleges_qs
        self.fields['course'].queryset = courses_qs
        self.fields['course'].label_from_instance = lambda obj: f"{obj.name}"

        selected_college = None
        if 'college' in self.data and self.data.get('college'):
            selected_college = self.data.get('college')
        elif self.initial.get('college'):
            initial_college = self.initial.get('college')
            if hasattr(initial_college, 'pk'):
                selected_college = initial_college.pk
            else:
                selected_college = initial_college

        if selected_college:
            try:
                selected_college_id = int(selected_college)
                self.fields['course'].queryset = courses_qs.filter(college_id=selected_college_id)
            except (ValueError, TypeError):
                self.fields['course'].queryset = courses_qs

        self.fields['college'].widget.attrs.setdefault('class', 'form-select')
        self.fields['course'].widget.attrs.setdefault('class', 'form-select')

class OfficerRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.filter(is_active=True),
        label="Organization",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    role = forms.CharField(
        max_length=50,
        label="Role/Position",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['username',]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Choose a Username'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered.")
        return email

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        
        if commit:
            user.save()
            # Create Officer profile
            Officer.objects.create(
                user=user,
                organization=self.cleaned_data['organization'],
                role=self.cleaned_data['role']
            )
            # Create/update UserProfile with Officer Status Flag
            UserProfile.objects.get_or_create(
                user=user,
                defaults={'is_officer': True}
            )
        return user

class PromoteStudentToOfficerForm(forms.Form):
    """Form for admins to promote existing students to officer access"""
    role = forms.CharField(
        max_length=50,
        label="Role/Position",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Cashier, Finance Officer'
        }),
        help_text="What is their position/role?"
    )
    can_process_payments = forms.BooleanField(
        label="Can Process Payments",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    can_void_payments = forms.BooleanField(
        label="Can Void Payments",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Allow this officer to void/cancel payments?"
    )
    can_generate_reports = forms.BooleanField(
        label="Can Generate Reports",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Allow this officer to generate financial reports?"
    )
    can_promote_officers = forms.BooleanField(
        label="Can Promote & Demote Officers",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Grant this officer FULL promotion authority to promote/demote students and other officers in their organization?"
    )
    is_super_officer = forms.BooleanField(
        label="Super Officer (Full Access to Officer Panel)",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Grant this officer super officer status to access all officer panel features (View Officers, View Students, Promote, Demote, Process Payments, etc.)"
    )
    
    def __init__(self, *args, student_queryset=None, organization_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Force queryset evaluation to prevent caching
        if student_queryset is not None:
            # Force evaluation by converting to list then back to queryset
            student_qs = student_queryset.all()  # Create a fresh queryset
            student_count = student_qs.count()
        else:
            student_qs = Student.objects.filter(is_active=True)
            student_count = student_qs.count()
        
        if organization_queryset is not None:
            org_qs = organization_queryset.all()  # Create a fresh queryset
            org_count = org_qs.count()
        else:
            org_qs = Organization.objects.filter(is_active=True)
            org_count = org_qs.count()
        
        # Create fields with fresh querysets
        self.fields['student'] = forms.ModelChoiceField(
            queryset=student_qs,
            label="Select Student to Promote",
            empty_label="-- Select a student --",
            widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
            help_text=f"Choose an active student to promote to officer ({student_count} available)"
        )
        
        self.fields['organization'] = forms.ModelChoiceField(
            queryset=org_qs,
            label="Assign to Organization",
            empty_label="-- Select an organization --",
            widget=forms.Select(attrs={'class': 'form-select'}),
            help_text=f"Which organization will this officer work for? ({org_count} available)"
        )
    
    def clean_student(self):
        student = self.cleaned_data['student']
        user = student.user
        
        # Check if the student's is_officer flag is True (primary check)
        # This is the most reliable indicator since it's set/unset during promotion/demotion
        if hasattr(user, 'user_profile') and user.user_profile.is_officer:
            raise ValidationError("This student is already an officer.")
        
        return student


class DemoteOfficerToStudentForm(forms.Form):
    """Form for admins/officers to demote officers back to student status"""
    reason = forms.CharField(
        max_length=500,
        label="Reason for Demotion",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'e.g., Term ended, Performance issues, Resignation'
        }),
        help_text="Why is this officer being demoted?"
    )
    
    def __init__(self, *args, officer_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Force queryset evaluation to prevent caching
        if officer_queryset is not None:
            # Force evaluation by creating a fresh queryset
            officer_qs = officer_queryset.all()  # Create a fresh queryset
            officer_count = officer_qs.count()
        else:
            officer_qs = Officer.objects.filter(is_active=True)
            officer_count = officer_qs.count()
        
        # Create field with fresh queryset
        self.fields['officer'] = forms.ModelChoiceField(
            queryset=officer_qs,
            label="Select Officer to Demote",
            empty_label="-- Select an officer --",
            widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
            help_text=f"Choose an active officer to demote to student-only status ({officer_count} available)"
        )
    
    def clean_officer(self):
        officer = self.cleaned_data['officer']
        if not hasattr(officer.user, 'officer_profile'):
            raise ValidationError("This person doesn't have an officer profile to demote.")
        return officer

# ==================== core forms ====================
class StudentPaymentRequestForm(forms.ModelForm):
    # student creates payment request (officer picks payment method)
    
    class Meta:
        model = PaymentRequest
        fields = ['fee_type']
        widgets = {
            'fee_type': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        self.student = kwargs.pop('student', None)
        super().__init__(*args, **kwargs)
        if self.student:
            # Use two-tiered fee system: get applicable fees from Student model
            applicable_fees = self.student.get_applicable_fees()
            
            self.fields['fee_type'].queryset = applicable_fees.select_related('organization').order_by(
                'organization__fee_tier', 'organization__name', 'name'
            )
            
            self.fields['fee_type'].empty_label = "Select an available fee..."
        
        self.fields['fee_type'].label = "Select Fee to Pay"
        if self.fields['fee_type'].queryset.exists():
            self.fields['fee_type'].choices = [
                (fee.id, f"[{fee.organization.get_fee_tier_display()}] {fee.organization.code} - {fee.name} (₱{fee.amount:.2f})") 
                for fee in self.fields['fee_type'].queryset
            ]

class OfficerPaymentProcessForm(forms.ModelForm):
    # process payment; or auto-generated from request_id
    
    payment_method = forms.ChoiceField(
        choices=Payment._meta.get_field('payment_method').choices,
        label="Payment Method",
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
        initial='CASH',
        help_text="Select the payment method used by the student"
    )
    
    class Meta:
        model = Payment
        fields = ['amount_received', 'payment_method', 'notes'] 
        widgets = {
            'amount_received': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg', 
                'step': '0.01',
                'min': '0.01',
                'placeholder': 'Amount Received (₱)'
            }),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional notes...'}),
        }

    def __init__(self, *args, **kwargs):
        self.fee_amount = kwargs.pop('fee_amount', None)
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        
    def clean_amount_received(self):
        amount_received = self.cleaned_data.get('amount_received')
        
        if amount_received is None:
            raise ValidationError("This field is required.")

        if self.fee_amount and amount_received < self.fee_amount:
            raise ValidationError(
                f"Amount received (₱{amount_received:.2f}) must be equal to or "
                f"greater than the fee amount (₱{self.fee_amount:.2f})."
            )
        
        return amount_received
        
    def clean_or_number(self):
        or_number = self.cleaned_data['or_number']
        if Payment.objects.filter(or_number=or_number).exists():
            raise ValidationError("This Official Receipt Number is already in use.")
        return or_number

class OfficerCreatePaymentForm(forms.Form):
    # create a payment for a student
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        label="Student",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Select the student making the payment"
    )
    fee_type = forms.ModelChoiceField(
        queryset=FeeType.objects.filter(is_active=True),
        label="Fee Type",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Select the fee being paid"
    )
    or_number = forms.CharField(
        max_length=50,
        label="Official Receipt Number",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter OR Number'})
    )
    amount_received = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        label="Amount Received (₱)",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0.01',
            'placeholder': 'Amount Received'
        })
    )
    payment_method = forms.ChoiceField(
        choices=Payment._meta.get_field('payment_method').choices,
        label="Payment Method",
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='CASH'
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Optional notes...'
        }),
        label="Notes"
    )
    send_email = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Send receipt via email",
        help_text="Email will be sent to student's registered email"
    )

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        
        if self.organization:
            # filter fee types by organization
            self.fields['fee_type'].queryset = FeeType.objects.filter(
                organization=self.organization,
                is_active=True
            )
    
    def clean_or_number(self):
        or_number = self.cleaned_data['or_number']
        if Payment.objects.filter(or_number=or_number).exists():
            raise ValidationError("This Official Receipt Number is already in use.")
        return or_number
    
    def clean_amount_received(self):
        amount_received = self.cleaned_data.get('amount_received')
        fee_type = self.cleaned_data.get('fee_type')
        
        if amount_received is None:
            raise ValidationError("This field is required.")
        
        if fee_type and amount_received < fee_type.amount:
            raise ValidationError(
                f"Amount received (₱{amount_received:.2f}) must be equal to or "
                f"greater than the fee amount (₱{fee_type.amount:.2f})."
            )
        
        return amount_received

class BulkPaymentPostForm(forms.Form):
    # post a fee to all students in an organization
    fee_type_name = forms.CharField(
        max_length=200,
        label="Fee Type Name",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Tuition Fee, Library Fee, etc.'}),
        help_text="Enter the name of the fee to post to all students"
    )
    fee_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        label="Fee Amount (₱)",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0.01',
            'placeholder': 'Amount'
        }),
        help_text="Enter the amount for this fee"
    )
    
    SEMESTER_CHOICES = [
        ('1st Semester', '1st Semester'),
        ('2nd Semester', '2nd Semester'),
        ('Summer', 'Summer'),
    ]
    
    semester = forms.ChoiceField(
        choices=SEMESTER_CHOICES,
        label="Semester",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Select the semester for this fee"
    )
    
    academic_year = forms.CharField(
        max_length=20,
        label="Academic Year",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 2024-2025'}),
        help_text="Enter the academic year (e.g., 2024-2025)"
    )
    
    YEAR_LEVEL_CHOICES = [
        ('All', 'All Year Levels'),
        ('1', '1st Year'),
        ('2', '2nd Year'),
        ('3', '3rd Year'),
        ('4', '4th Year'),
    ]
    
    applicable_year_level = forms.ChoiceField(
        choices=YEAR_LEVEL_CHOICES,
        label="Applicable Year Level",
        initial='All',
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Select which year level this fee applies to"
    )
    
    payment_deadline = forms.DateField(
        required=False,
        label="Payment Deadline (Optional)",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        help_text="Optional: Set a deadline for this payment"
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional notes for all payments...'
        }),
        label="Notes (applied to all payments)"
    )

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        
        # Set default values from current academic period
        from .models import AcademicYearConfig
        from django.utils import timezone
        try:
            current_period = AcademicYearConfig.objects.get(is_current=True)
            self.fields['academic_year'].initial = current_period.academic_year
            self.fields['semester'].initial = current_period.semester
        except AcademicYearConfig.DoesNotExist:
            self.fields['academic_year'].initial = f"{timezone.now().year}-{timezone.now().year + 1}"
    
    def clean_fee_type_name(self):
        name = self.cleaned_data['fee_type_name'].strip()
        if not name:
            raise ValidationError("Fee type name is required.")
        return name
    
    def clean_fee_amount(self):
        amount = self.cleaned_data.get('fee_amount')
        if amount is None or amount <= 0:
            raise ValidationError("Fee amount must be greater than zero.")
        return amount
    
    def clean_academic_year(self):
        year = self.cleaned_data['academic_year'].strip()
        if not year:
            raise ValidationError("Academic year is required.")
        # Basic validation for format like "2024-2025"
        import re
        if not re.match(r'^\d{4}-\d{4}$', year):
            raise ValidationError("Academic year must be in format YYYY-YYYY (e.g., 2024-2025)")
        return year
    
    def clean_payment_deadline(self):
        deadline = self.cleaned_data.get('payment_deadline')
        if deadline:
            from django.utils import timezone
            if deadline < timezone.now().date():
                raise ValidationError("Payment deadline cannot be in the past.")
        return deadline

class VoidPaymentForm(forms.Form):
    void_reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 3,
            'placeholder': 'Enter detailed reason for voiding this payment (minimum 10 characters)...'
        }),
        label="Reason for Voiding"
    )

    def clean_void_reason(self):
        void_reason = self.cleaned_data['void_reason'].strip()
        if len(void_reason) < 10:
            raise ValidationError("Please provide a detailed reason (at least 10 characters).")
        return void_reason

# ==================== PROFILE & ADMIN FORMS ====================
class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['middle_name', 'phone_number', 'year_level']
        widgets = {
            'middle_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter your middle name'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '09XX-XXX-XXXX'}),
            'year_level': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 5}),
        }
        labels = {
            'middle_name': 'Middle Name',
            'phone_number': 'Phone Number',
            'year_level': 'Year Level',
        }
        help_texts = {
            'middle_name': 'Your middle name (optional)',
            'phone_number': 'Format: 09XX-XXX-XXXX',
            'year_level': 'Your current year level (1-5)',
        }

class OfficerForm(forms.ModelForm):
    class Meta:
        model = Officer
        fields = ['role']
        widgets = {
            'role': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Treasurer, President, Finance Officer'
            }),
        }
        labels = {
            'role': 'Role/Position',
        }
        help_texts = {
            'role': 'Your position or title in the organization',
        }

class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = [
            'name', 'code', 'department', 'fee_tier', 'program_affiliation',
            'description', 'contact_email', 'contact_phone', 'booth_location'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'fee_tier': forms.Select(attrs={'class': 'form-select'}),
            'program_affiliation': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'booth_location': forms.TextInput(attrs={'class': 'form-control'}),
        }

class FeeTypeForm(forms.ModelForm):
    class Meta:
        model = FeeType
        fields = [
            'organization', 'name', 'amount', 'description',
            'academic_year', 'semester', 'applicable_year_levels', 'deadline'
        ]
        widgets = {
            'organization': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'academic_year': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 2024-2025'}),
            'semester': forms.Select(attrs={'class': 'form-select'}),
            'applicable_year_levels': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 1,2,3 or All'}),
            'deadline': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

class AcademicYearConfigForm(forms.ModelForm):
    class Meta:
        model = AcademicYearConfig
        fields = ['academic_year', 'semester', 'start_date', 'end_date', 'is_current']
        widgets = {
            'academic_year': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 2024-2025'}),
            'semester': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_current': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CreateOfficerForm(UserCreationForm):
    """Form for ALLORG to create brand new officer accounts"""
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.filter(is_active=True),
        label="Assign to Organization",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Which organization will this officer work for?"
    )
    role = forms.CharField(
        max_length=50,
        label="Role/Position",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Treasurer, Officer'}),
        help_text="What is their position/role?"
    )
    can_process_payments = forms.BooleanField(
        label="Can Process Payments",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    can_void_payments = forms.BooleanField(
        label="Can Void Payments",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    can_generate_reports = forms.BooleanField(
        label="Can Generate Reports",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    can_promote_officers = forms.BooleanField(
        label="Can Promote Officers",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Allow this officer to promote/demote students in their organization?"
    )
    is_super_officer = forms.BooleanField(
        label="Super Officer (Full Access to Officer Panel)",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Grant this officer super officer status to access all officer panel features"
    )

    class Meta:
        model = User
        fields = ['username']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Choose a Username'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered.")
        return email

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.is_staff = True
        
        if commit:
            user.save()
            # Create Officer profile
            Officer.objects.create(
                user=user,
                organization=self.cleaned_data['organization'],
                role=self.cleaned_data['role'],
                can_process_payments=self.cleaned_data['can_process_payments'],
                can_void_payments=self.cleaned_data['can_void_payments'],
                can_generate_reports=self.cleaned_data['can_generate_reports'],
                can_promote_officers=self.cleaned_data['can_promote_officers'],
                is_super_officer=self.cleaned_data.get('is_super_officer', False),
            )
            # Create UserProfile with Officer Status Flag
            UserProfile.objects.get_or_create(
                user=user,
                defaults={'is_officer': True}
            )
        return user

class CompleteProfileForm(forms.ModelForm):
    student_id_number = forms.CharField(
        max_length=20,
        label="Student ID Number",
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'e.g., 2025-0001',
            'autocomplete': 'off',
            'inputmode': 'numeric'
        })
    )
    phone_number = forms.CharField(
        max_length=15,
        label="Phone Number",
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'e.g., 09123456789',
            'inputmode': 'numeric',
            'aria-describedby': 'phoneHelp'
        }),
        required=False
    )
    college = forms.ModelChoiceField(
        queryset=College.objects.none(),
        label="College/Department",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        empty_label="Select College/Department",
        help_text="College of Sciences (COS) - This system is designed for College of Sciences only"
    )
    course = forms.ModelChoiceField(
        queryset=Course.objects.none(),
        label="Course/Program",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        empty_label="Select Course/Program",
        help_text="Select one of the 5 supported programs: Medical Biology, Marine Biology, Computer Science, Environmental Science, or Information Technology"
    )
    year_level = forms.IntegerField(
        min_value=1, max_value=5,
        label="Year Level",
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm'})
    )

    class Meta:
        model = Student
        fields = ['student_id_number', 'phone_number', 'college', 'course', 'year_level']

    def clean_student_id_number(self):
        student_id = self.cleaned_data['student_id_number']
        if Student.objects.filter(student_id_number=student_id).exists():
            raise ValidationError("This student ID is already registered.")
        return student_id

    def clean(self):
        cleaned_data = super().clean()
        course = cleaned_data.get('course')
        college = cleaned_data.get('college')
        
        if course and college and course.college != college:
            raise ValidationError("The selected course does not belong to the selected college.")
        
        return cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # System is focused on College of Sciences only
        colleges_qs = College.objects.filter(code="COS", is_active=True).order_by('name')
        # Only show the 5 supported programs (filter by program_type to exclude 'OTHER')
        courses_qs = Course.objects.filter(
            college__code="COS", 
            is_active=True,
            program_type__in=['MEDICAL_BIOLOGY', 'MARINE_BIOLOGY', 'COMPUTER_SCIENCE', 'ENVIRONMENTAL_SCIENCE', 'INFORMATION_TECHNOLOGY']
        ).select_related('college').order_by('name')

        self.fields['college'].queryset = colleges_qs
        self.fields['course'].queryset = courses_qs
        self.fields['course'].label_from_instance = lambda obj: f"{obj.name}"

        selected_college = None
        if 'college' in self.data and self.data.get('college'):
            selected_college = self.data.get('college')
        elif self.initial.get('college'):
            initial_college = self.initial.get('college')
            if hasattr(initial_college, 'pk'):
                selected_college = initial_college.pk
            else:
                selected_college = initial_college

        if selected_college:
            try:
                selected_college_id = int(selected_college)
                self.fields['course'].queryset = courses_qs.filter(college_id=selected_college_id)
            except (ValueError, TypeError):
                self.fields['course'].queryset = courses_qs

        self.fields['college'].widget.attrs.setdefault('class', 'form-select')
        self.fields['course'].widget.attrs.setdefault('class', 'form-select')

