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
        
        academic_year = Student._meta.get_field('academic_year').default
        semester = Student._meta.get_field('semester').default
        
        try:
            current_period = AcademicYearConfig.objects.get(is_current=True)
            academic_year = current_period.academic_year
            semester = current_period.semester
        except Exception:
            pass

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
                college=self.cleaned_data['college'],
                academic_year=academic_year,
                semester=semester
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
    employee_id = forms.CharField(
        max_length=20,
        label="Employee/Officer ID",
        widget=forms.TextInput(attrs={'class': 'form-control'})
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
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        required=False
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

    def clean_employee_id(self):
        employee_id = self.cleaned_data['employee_id']
        if Officer.objects.filter(employee_id=employee_id).exists():
            raise ValidationError("This employee ID is already registered.")
        return employee_id

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists() or \
           Officer.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered.")
        return email

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            # Create Officer profile
            Officer.objects.create(
                user=user,
                employee_id=self.cleaned_data['employee_id'],
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name'],
                email=self.cleaned_data['email'],
                phone_number=self.cleaned_data['phone_number'],
                organization=self.cleaned_data['organization'],
                role=self.cleaned_data['role']
            )
            # Create/update UserProfile with Officer Status Flag
            UserProfile.objects.get_or_create(
                user=user,
                defaults={'is_officer': True}
            )
        return user

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
    
    def clean_or_number_prefix(self):
        prefix = self.cleaned_data['or_number_prefix']
        if not prefix:
            raise ValidationError("OR number prefix is required.")
        return prefix

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
        fields = ['first_name', 'last_name', 'middle_name', 'email', 'phone_number']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class OfficerForm(forms.ModelForm):
    class Meta:
        model = Officer
        fields = ['first_name', 'last_name', 'email', 'phone_number']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
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
