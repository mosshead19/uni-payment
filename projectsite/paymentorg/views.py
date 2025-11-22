from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.views.generic import View, CreateView, UpdateView, DeleteView, ListView, DetailView, TemplateView
from django.urls import reverse_lazy
from django.http import JsonResponse, Http404
import uuid
import hmac
import hashlib
from datetime import timedelta
from django.conf import settings
from decimal import Decimal
from django.db.models import Sum, Q
import logging
import json

logger = logging.getLogger(__name__)

from .models import (
    Student, Officer, Organization, FeeType,
    PaymentRequest, Payment, Receipt, ActivityLog, AcademicYearConfig,
    Course, College, UserProfile, BulkPaymentPosting
)
from .forms import (
    StudentPaymentRequestForm, OfficerPaymentProcessForm, OrganizationForm, 
    FeeTypeForm, StudentForm, OfficerForm, VoidPaymentForm,
    StudentRegistrationForm, OfficerRegistrationForm, AcademicYearConfigForm,
    BulkPaymentPostForm, PromoteStudentToOfficerForm, DemoteOfficerToStudentForm
)
from .utils import send_receipt_email

# utility functions

def get_current_period():
    try:
        return AcademicYearConfig.objects.get(is_current=True)
    except AcademicYearConfig.DoesNotExist:
        return None
    except AcademicYearConfig.MultipleObjectsReturned:
        return AcademicYearConfig.objects.filter(is_current=True).order_by('-start_date').first()

def create_signature(message_string):
    secret_key = getattr(settings, 'SECRET_KEY', 'default-insecure-key').encode('utf-8')
    message = str(message_string).encode('utf-8')
    signature = hmac.new(secret_key, message, hashlib.sha256).hexdigest()
    return signature

def validate_signature(message_string, provided_signature):
    expected_signature = create_signature(message_string)
    return hmac.compare_digest(expected_signature, provided_signature)

# authentication views
class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    
    def form_valid(self, form):
        # Call parent to authenticate and set user in session
        result = super().form_valid(form)
        
        # Refresh user with related objects after authentication
        user = self.request.user
        user_refreshed = User.objects.select_related(
            'officer_profile',
            'student_profile',
            'user_profile'
        ).get(pk=user.pk)
        
        # Update the request.user
        self.request.user = user_refreshed
        
        # Update the session to persist the refreshed user
        update_session_auth_hash(self.request, user_refreshed)
        
        return result
    
    def get_success_url(self):
        user = self.request.user
        
        # Unified login system: Check Officer Status Flag
        is_officer = False
        if hasattr(user, 'user_profile'):
            is_officer = user.user_profile.is_officer
        elif hasattr(user, 'officer_profile'):
            is_officer = True
            # Sync UserProfile if it doesn't exist
            if not hasattr(user, 'user_profile'):
                UserProfile.objects.get_or_create(
                    user=user,
                    defaults={'is_officer': True}
                )
        
        if is_officer or user.is_superuser:
            return reverse_lazy('officer_dashboard')
        elif hasattr(user, 'student_profile'):
            # Ensure UserProfile exists for students
            if not hasattr(user, 'user_profile'):
                UserProfile.objects.get_or_create(
                    user=user,
                    defaults={'is_officer': False}
                )
            return reverse_lazy('student_dashboard')
        elif user.is_staff:
            return '/admin/'
        else:
            return reverse_lazy('home')
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.get_success_url()) 
        return super().dispatch(request, *args, **kwargs)

class SelectProfileView(TemplateView):
    template_name = 'registration/select_profile.html'

class StudentRegistrationView(CreateView):
    form_class = StudentRegistrationForm
    template_name = 'registration/student_register.html'
    success_url = reverse_lazy('login')
    
    def form_valid(self, form):
        user = form.save()
        messages.success(self.request, f'Student account for {user.username} created! Please login.')
        return redirect(self.success_url)

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        return super().form_invalid(form) 

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # System is focused on College of Sciences only
        courses = Course.objects.filter(
            college__code="COS", 
            is_active=True,
            program_type__in=['MEDICAL_BIOLOGY', 'MARINE_BIOLOGY', 'COMPUTER_SCIENCE', 'ENVIRONMENTAL_SCIENCE', 'INFORMATION_TECHNOLOGY']
        ).select_related('college').order_by('name')
        course_payload = [
            {
                'id': course.id,
                'label': course.name,
                'college_id': course.college_id,
                'program_type': course.program_type,
            }
            for course in courses
        ]

        selected_course = self.request.POST.get('course') or self.request.GET.get('course') or ''
        selected_college = self.request.POST.get('college') or self.request.GET.get('college') or ''

        context.update({
            'course_options_json': json.dumps(course_payload),
            'selected_course_id': selected_course,
            'selected_college_id': selected_college,
        })
        return context

class OfficerRegistrationView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    form_class = OfficerRegistrationForm
    template_name = 'registration/officer_register.html'
    success_url = reverse_lazy('login')
    
    def test_func(self):
        return self.request.user.is_staff
    
    def handle_no_permission(self):
        messages.error(self.request, "Administrator access required.")
        return redirect('login')
    
    def form_valid(self, form):
        user = form.save()
        messages.success(self.request, f'Officer account for {user.username} created! Please login.')
        return redirect(self.success_url)
    
    def form_invalid(self, form):
        print("--- DEBUG: Officer Registration Failed ---")
        print("Errors:", form.errors)
        messages.error(self.request, "Registration failed due to errors. Please check the form fields.")
        return super().form_invalid(form)

class PromoteStudentToOfficerView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Admin/Officer view to promote existing students to officer access"""
    template_name = 'registration/promote_student_to_officer.html'
    
    def test_func(self):
        user = self.request.user
        # Allow staff/superusers
        if user.is_staff:
            return True
        # Allow officers with promotion authority
        if hasattr(user, 'officer_profile'):
            return user.officer_profile.can_promote_officers
        return False
    
    def handle_no_permission(self):
        messages.error(self.request, "Administrator or Officer with promotion authority required.")
        return redirect('login')
    
    def get_accessible_students(self):
        """Get students accessible to this user based on their organization"""
        user = self.request.user
        
        if user.is_staff:
            # Staff can see all students
            return Student.objects.filter(is_active=True)
        
        if hasattr(user, 'officer_profile'):
            # Officer can only see students from their organization(s)
            officer = user.officer_profile
            accessible_orgs = officer.organization.get_accessible_organizations()
            
            # Build a query for students based on accessible organizations
            students_query = Student.objects.filter(is_active=True)
            
            # Filter by program affiliation matching organization's affiliation
            q_filter = Q()
            for org in accessible_orgs:
                if org.program_affiliation == 'ALL':
                    # Organization serves all programs
                    # Check if it's a college-level org or program under a college
                    if org.hierarchy_level == 'COLLEGE':
                        # Top-level college org - can access all students
                        # No filter needed, return all
                        return students_query
                    else:
                        # Program-level org under college with 'ALL' affiliation - shouldn't happen
                        # but include all just in case
                        q_filter |= Q(is_active=True)
                else:
                    # Program-specific org - match course.program_type
                    program_type = org.program_affiliation
                    q_filter |= Q(course__program_type=program_type)
            
            if q_filter:
                students_query = students_query.filter(q_filter)
            
            return students_query.distinct()
        
        return Student.objects.none()
    
    def get_accessible_organizations(self):
        """Get organizations accessible to this user"""
        user = self.request.user
        
        if user.is_staff:
            from paymentorg.models import Organization
            return Organization.objects.filter(is_active=True)
        
        if hasattr(user, 'officer_profile'):
            officer = user.officer_profile
            return officer.organization.get_accessible_organizations()
        
        return []
    
    def get(self, request):
        form = PromoteStudentToOfficerForm()
        # Filter form choices based on user's accessible organizations
        accessible_students = self.get_accessible_students()
        accessible_orgs = self.get_accessible_organizations()
        
        form.fields['student'].queryset = accessible_students
        if isinstance(accessible_orgs, list):
            org_ids = [org.id for org in accessible_orgs]
            form.fields['organization'].queryset = Organization.objects.filter(id__in=org_ids)
        else:
            form.fields['organization'].queryset = accessible_orgs
        
        context = {
            'form': form,
            'is_admin': request.user.is_staff,
            'user_organization': request.user.officer_profile.organization if hasattr(request.user, 'officer_profile') else None
        }
        return render(request, self.template_name, context)
    
    @transaction.atomic
    def post(self, request):
        form = PromoteStudentToOfficerForm(request.POST)
        
        # Filter form choices based on user's accessible organizations
        accessible_students = self.get_accessible_students()
        accessible_orgs = self.get_accessible_organizations()
        
        form.fields['student'].queryset = accessible_students
        if isinstance(accessible_orgs, list):
            org_ids = [org.id for org in accessible_orgs]
            form.fields['organization'].queryset = Organization.objects.filter(id__in=org_ids)
        else:
            form.fields['organization'].queryset = accessible_orgs
        
        if form.is_valid():
            student = form.cleaned_data['student']
            organization = form.cleaned_data['organization']
            role = form.cleaned_data['role']
            can_process_payments = form.cleaned_data['can_process_payments']
            can_void_payments = form.cleaned_data['can_void_payments']
            can_generate_reports = form.cleaned_data.get('can_generate_reports', False)
            can_promote_officers = form.cleaned_data.get('can_promote_officers', False)
            
            # Verify user can promote to this organization
            if not request.user.is_staff:
                if hasattr(request.user, 'officer_profile'):
                    accessible_org_ids = request.user.officer_profile.organization.get_accessible_organization_ids()
                    if organization.id not in accessible_org_ids:
                        messages.error(request, "You don't have permission to add officers to that organization.")
                        return render(request, self.template_name, {'form': form})
                    
                    # Only officers with can_promote_officers permission can grant promotion authority
                    if can_promote_officers and not request.user.officer_profile.can_promote_officers:
                        messages.warning(request, "Only administrators and officers with promotion authority can grant promotion to others.")
                        can_promote_officers = False
            
            user = student.user
            
            # Create or update Officer profile
            officer, created = Officer.objects.update_or_create(
                user=user,
                defaults={
                    'employee_id': student.student_id_number,  # Use student ID as employee ID
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'phone_number': getattr(student, 'phone_number', ''),
                    'organization': organization,
                    'role': role,
                    'can_process_payments': can_process_payments,
                    'can_void_payments': can_void_payments,
                    'can_generate_reports': can_generate_reports,
                    'can_promote_officers': can_promote_officers,
                }
            )
            
            # Update/create UserProfile with officer flag
            UserProfile.objects.update_or_create(
                user=user,
                defaults={'is_officer': True}
            )
            
            # If promoting the current user, refresh their session to pick up new permissions
            if request.user.id == user.id:
                # Refresh the user object to get updated officer_profile
                request.user = user.__class__.objects.get(pk=request.user.id)
                update_session_auth_hash(request, request.user)
            
            # Log the action
            ActivityLog.objects.create(
                user=request.user,
                action='promote_student_to_officer',
                description=f'Promoted {user.get_full_name()} ({student.student_id_number}) to officer with role: {role}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            status_text = "created" if created else "updated"
            messages.success(
                request,
                f'Officer profile {status_text} for {user.get_full_name()}! '
                f'They can now access the officer dashboard while keeping their student account.'
            )
            return redirect('login')
        else:
            context = {
                'form': form,
                'is_admin': request.user.is_staff,
                'user_organization': request.user.officer_profile.organization if hasattr(request.user, 'officer_profile') else None
            }
            return render(request, self.template_name, context)


class DemoteOfficerToStudentView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Admin/Officer view to demote officers back to student status"""
    template_name = 'registration/demote_officer_to_student.html'
    
    def test_func(self):
        user = self.request.user
        # Allow staff/superusers
        if user.is_staff:
            return True
        # Allow officers with promotion authority
        if hasattr(user, 'officer_profile'):
            return user.officer_profile.can_promote_officers
        return False
    
    def handle_no_permission(self):
        messages.error(self.request, "Administrator or Officer with promotion authority required.")
        return redirect('login')
    
    def get_accessible_officers(self):
        """Get officers accessible to this user based on their organization"""
        user = self.request.user
        
        if user.is_staff:
            # Staff can see all officers
            return Officer.objects.filter(is_active=True)
        
        if hasattr(user, 'officer_profile'):
            # Officer can only see officers from their organization(s)
            officer = user.officer_profile
            org_ids = officer.organization.get_accessible_organization_ids()
            return Officer.objects.filter(
                is_active=True,
                organization_id__in=org_ids
            )
        
        return Officer.objects.none()
    
    def get(self, request):
        form = DemoteOfficerToStudentForm()
        # Filter form choices based on user's accessible organizations
        accessible_officers = self.get_accessible_officers()
        form.fields['officer'].queryset = accessible_officers
        
        context = {
            'form': form,
            'is_admin': request.user.is_staff,
            'user_organization': request.user.officer_profile.organization if hasattr(request.user, 'officer_profile') else None
        }
        return render(request, self.template_name, context)
    
    @transaction.atomic
    def post(self, request):
        form = DemoteOfficerToStudentForm(request.POST)
        
        # Filter form choices based on user's accessible organizations
        accessible_officers = self.get_accessible_officers()
        form.fields['officer'].queryset = accessible_officers
        
        if form.is_valid():
            officer = form.cleaned_data['officer']
            reason = form.cleaned_data['reason']
            
            # Verify user can demote this officer
            if not request.user.is_staff:
                if hasattr(request.user, 'officer_profile'):
                    accessible_org_ids = request.user.officer_profile.organization.get_accessible_organization_ids()
                    if officer.organization.id not in accessible_org_ids:
                        messages.error(request, "You don't have permission to demote officers in that organization.")
                        return render(request, self.template_name, {'form': form})
            
            user = officer.user
            
            # Remove officer permissions
            officer.can_promote_officers = False
            officer.can_process_payments = False
            officer.can_void_payments = False
            officer.can_generate_reports = False
            officer.is_super_officer = False
            officer.save()
            
            # Update/create UserProfile to remove officer flag
            UserProfile.objects.update_or_create(
                user=user,
                defaults={'is_officer': False}
            )
            
            # If demoting the current user, refresh their session to remove permissions
            if request.user.id == user.id:
                # Refresh the user object to get updated officer_profile
                request.user = user.__class__.objects.get(pk=request.user.id)
                update_session_auth_hash(request, request.user)
            
            # Log the action
            ActivityLog.objects.create(
                user=request.user,
                action='demote_officer_to_student',
                description=f'Demoted {user.get_full_name()} from officer status. Reason: {reason}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(
                request,
                f'Officer {user.get_full_name()} has been demoted to student-only status. '
                f'They can still access the student portal with their student account.'
            )
            return redirect('officer_dashboard')
        else:
            context = {
                'form': form,
                'is_admin': request.user.is_staff,
                'user_organization': request.user.officer_profile.organization if hasattr(request.user, 'officer_profile') else None
            }
            return render(request, self.template_name, context)
class StudentRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        # Allow access if user has student profile OR is an officer (officers can view their student dashboard too)
        has_student_profile = hasattr(user, 'student_profile')
        is_officer = False
        if hasattr(user, 'user_profile'):
            is_officer = user.user_profile.is_officer
        elif hasattr(user, 'officer_profile'):
            is_officer = True
        return has_student_profile or is_officer or user.is_superuser
    
    def handle_no_permission(self):
        messages.error(self.request, "Student access required.")
        return redirect('login')

class OfficerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        # Unified login: Check Officer Status Flag
        is_officer = False
        if hasattr(user, 'user_profile'):
            is_officer = user.user_profile.is_officer
        elif hasattr(user, 'officer_profile'):
            is_officer = True
        return is_officer or user.is_superuser
    
    def handle_no_permission(self):
        messages.error(self.request, "Officer or Superuser privilege required.")
        return redirect('login')

class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff
    
    def handle_no_permission(self):
        messages.error(self.request, "Administrator access required.")
        return redirect('login')

class SuperOfficerOrStaffMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Allows access to staff users OR super officers.
    Super officers can only see data for their organization.
    """
    def test_func(self):
        user = self.request.user
        if user.is_staff:
            return True
        # Check if user is a super officer
        if hasattr(user, 'officer_profile'):
            return user.officer_profile.is_super_officer
        return False
    
    def handle_no_permission(self):
        messages.error(self.request, "Administrator or Super Officer access required.")
        return redirect('login')
    
    def get_user_organization(self):
        """Get the organization of the super officer"""
        if self.request.user.is_staff:
            return None  # Staff can see all organizations
        if hasattr(self.request.user, 'officer_profile'):
            return self.request.user.officer_profile.organization
        return None


class OrganizationHierarchyMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Allows officers with can_promote_officers permission to access and manage
    their organization and all child organizations.
    Also allows staff/superusers to access all organizations.
    """
    def test_func(self):
        user = self.request.user
        # Allow staff/superusers
        if user.is_staff:
            return True
        # Allow officers with promotion authority
        if hasattr(user, 'officer_profile'):
            return user.officer_profile.can_promote_officers or user.officer_profile.is_super_officer
        return False
    
    def handle_no_permission(self):
        messages.error(self.request, "Officer with promotion authority required.")
        return redirect('login')
    
    def get_user_organization(self):
        """Get the organization of the officer"""
        if self.request.user.is_staff:
            return None  # Staff can see all organizations
        if hasattr(self.request.user, 'officer_profile'):
            return self.request.user.officer_profile.organization
        return None
    
    def get_accessible_organizations(self):
        """Get all organizations accessible to this user"""
        if self.request.user.is_staff:
            from paymentorg.models import Organization
            return Organization.objects.all()
        
        if hasattr(self.request.user, 'officer_profile'):
            org = self.request.user.officer_profile.organization
            return org.get_accessible_organizations()
        
        return []
    
    def get_accessible_organization_ids(self):
        """Get list of organization IDs accessible to this user"""
        orgs = self.get_accessible_organizations()
        if isinstance(orgs, list):
            return [org.id for org in orgs]
        return list(orgs.values_list('id', flat=True))
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_organization'] = self.get_user_organization()
        context['accessible_organizations'] = self.get_accessible_organizations()
        context['can_promote_officers'] = (
            self.request.user.is_staff or 
            (hasattr(self.request.user, 'officer_profile') and 
             self.request.user.officer_profile.can_promote_officers)
        )
        return context

# base views
class HomePageView(TemplateView):
    template_name = "home.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['organizations'] = Organization.objects.filter(is_active=True)
        return context

# student views
class StudentDashboardView(StudentRequiredMixin, TemplateView):
    template_name = 'paymentorg/student_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get student profile - handle both regular students and officers who are students
        if hasattr(user, 'student_profile'):
            student = user.student_profile
        else:
            # If officer doesn't have student profile, redirect with error
            messages.error(self.request, "You don't have a student profile.")
            return redirect('officer_dashboard')
        
        expired_requests = student.payment_requests.filter(
            status='PENDING', 
            expires_at__lt=timezone.now()
        )
        if expired_requests.exists():
            expired_requests.update(status='EXPIRED')
        
        pending_payments = student.payment_requests.filter(status='PENDING').order_by('-created_at')
        
        # Calculate statistics
        completed_payments = student.get_completed_payments()
        total_paid = completed_payments.aggregate(Sum('amount'))['amount__sum'] or 0
        payments_count = completed_payments.count()
        
        # Two-tiered fee system: Get applicable fees
        applicable_fees = student.get_applicable_fees()
        tier1_fees = student.get_tier1_fees()
        tier2_fees = student.get_tier2_fees()
        total_outstanding = student.get_total_outstanding_fees()
        
        # Build a comprehensive list of all fees with their payment status
        all_fees_with_status = []
        for fee in applicable_fees:
            # Check if student has paid this fee
            payment = completed_payments.filter(fee_type=fee).first()
            
            # Check if student has a VALID pending request for this fee (not expired)
            pending_request = pending_payments.filter(fee_type=fee).first()
            
            # Double-check the pending request hasn't expired (in case of race condition)
            has_valid_pending = False
            if pending_request:
                if pending_request.expires_at > timezone.now():
                    has_valid_pending = True
                else:
                    # Mark as expired if somehow it slipped through
                    pending_request.status = 'EXPIRED'
                    pending_request.save()
                    pending_request = None
            
            fee_info = {
                'fee_type': fee,
                'organization': fee.organization,
                'amount': fee.amount,
                'is_paid': payment is not None,
                'payment': payment,
                'has_pending_request': has_valid_pending,
                'pending_request': pending_request,
            }
            all_fees_with_status.append(fee_info)
        
        context.update({
            'student': student,
            'pending_payments': pending_payments,
            'completed_payments': completed_payments.order_by('-created_at')[:5],
            'total_paid': total_paid,
            'payments_count': payments_count,
            'applicable_fees': applicable_fees,
            'tier1_fees': tier1_fees,
            'tier2_fees': tier2_fees,
            'total_outstanding': total_outstanding,
            'all_fees_with_status': all_fees_with_status,
        })
        return context

class PaymentHistoryView(StudentRequiredMixin, TemplateView):
    # student payment history view
    template_name = 'paymentorg/payment_history.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.request.user.student_profile
        
        # get all completed payments for the student
        payments = Payment.objects.filter(
            student=student,
            status='COMPLETED',
            is_void=False
        ).select_related('organization', 'fee_type', 'receipt').order_by('-created_at')
        
        total_spent = payments.aggregate(Sum('amount'))['amount__sum'] or 0
        payment_count = payments.count()
        
        context.update({
            'student': student,
            'payments': payments,
            'total_spent': total_spent,
            'payment_count': payment_count,
        })
        return context

class GenerateQRPaymentView(StudentRequiredMixin, CreateView):
    model = PaymentRequest
    form_class = StudentPaymentRequestForm
    template_name = 'paymentorg/generate_qr.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        student = self.request.user.student_profile
        kwargs['student'] = student
        # Use two-tiered fee system: only show applicable fees
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.request.user.student_profile
        applicable_fees = student.get_applicable_fees()
        fee_org_map = {
            fee.id: {
                'org_name': fee.organization.name,
                'org_code': fee.organization.code,
                'org_logo': fee.organization.get_logo_path(),
            }
            for fee in applicable_fees
        }
        import json
        context['fee_org_map_json'] = json.dumps(fee_org_map)
        return context
    
    @transaction.atomic
    def form_valid(self, form):
        student = self.request.user.student_profile
        fee_type = form.cleaned_data['fee_type']
        
        if PaymentRequest.objects.filter(student=student, fee_type=fee_type, status='PENDING').exists() or \
           Payment.objects.filter(student=student, fee_type=fee_type, status='COMPLETED').exists():
            messages.error(self.request, "You already have a pending or completed payment for this fee.")
            return redirect('student_dashboard')
        
        payment_request = form.save(commit=False)
        payment_request.student = student
        payment_request.organization = fee_type.organization
        payment_request.amount = fee_type.amount
        payment_request.payment_method = 'CASH'  # default payment method(for now)
        payment_request.expires_at = timezone.now() + timedelta(minutes=15)
        payment_request.qr_signature = create_signature(str(payment_request.request_id))
        payment_request.save()
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='qr_generated',
            description=f'Student {student.student_id_number} generated QR for {fee_type.name}',
            payment_request=payment_request,
            ip_address=self.request.META.get('REMOTE_ADDR')
        )
        
        messages.success(
            self.request, 
            f'QR code generated! Present this at the {fee_type.organization.code} booth.'
        )
        return redirect('show_payment_qr', request_id=payment_request.request_id)

class QuickGenerateQRView(StudentRequiredMixin, View):
    """Quick QR generation from dashboard - directly creates payment request for a specific fee"""
    
    @transaction.atomic
    def post(self, request, fee_id):
        student = request.user.student_profile
        
        try:
            fee_type = get_object_or_404(FeeType, id=fee_id, is_active=True)
            
            # Verify this fee is applicable to the student
            applicable_fees = student.get_applicable_fees()
            if fee_type not in applicable_fees:
                messages.error(request, "This fee is not applicable to you.")
                return redirect('student_dashboard')
            
            # Check if already has pending request or completed payment
            if PaymentRequest.objects.filter(student=student, fee_type=fee_type, status='PENDING').exists():
                messages.warning(request, f"You already have a pending payment request for {fee_type.name}.")
                return redirect('student_dashboard')
            
            if Payment.objects.filter(student=student, fee_type=fee_type, status='COMPLETED').exists():
                messages.info(request, f"You have already paid for {fee_type.name}.")
                return redirect('student_dashboard')
            
            # Create payment request
            payment_request = PaymentRequest.objects.create(
                student=student,
                organization=fee_type.organization,
                fee_type=fee_type,
                amount=fee_type.amount,
                payment_method='CASH',
                expires_at=timezone.now() + timedelta(minutes=15),
                qr_signature=create_signature(uuid.uuid4().hex[:12])
            )
            
            ActivityLog.objects.create(
                user=request.user,
                action='qr_generated',
                description=f'Student {student.student_id_number} generated QR for {fee_type.name}',
                payment_request=payment_request,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(
                request, 
                f'QR code generated! Present this at the {fee_type.organization.code} booth.'
            )
            # Redirect directly to QR page
            return redirect('show_payment_qr', request_id=payment_request.request_id)
            
        except Exception as e:
            messages.error(request, f"Error generating QR code: {str(e)}")
            return redirect('student_dashboard')

class PaymentRequestDetailView(StudentRequiredMixin, TemplateView):
    # payment request details and qr
    template_name = 'paymentorg/payment_request_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request_id = self.kwargs['request_id']
        student = self.request.user.student_profile
        
        try:
            payment_request = get_object_or_404(
                PaymentRequest, 
                request_id=request_id, 
                student=student,
                status='PENDING'
            )
        except ValueError:
            raise Http404("Invalid Payment Request ID.")
        
        if payment_request.is_expired():
            payment_request.status = 'EXPIRED'
            payment_request.save()
            messages.error(self.request, "This payment request has expired.")
            return redirect('student_dashboard')
        
        # if qr signature is empty, generate it
        if not payment_request.qr_signature:
            payment_request.qr_signature = create_signature(str(payment_request.request_id))
            payment_request.save(update_fields=['qr_signature'])
        
        context['payment_request'] = payment_request
        return context

class ViewPaymentRequestQRView(StudentRequiredMixin, View):
    # view/generate qr for a paymentrequest
    template_name = 'paymentorg/view_payment_request_qr.html'
    
    def get(self, request, request_id):
        student = request.user.student_profile
        
        try:
            payment_request = get_object_or_404(
                PaymentRequest, 
                request_id=request_id, 
                student=student,
                status='PENDING'
            )
        except ValueError:
            raise Http404("Invalid Payment Request ID.")
        
        if payment_request.is_expired():
            payment_request.status = 'EXPIRED'
            payment_request.save()
            messages.error(request, "This payment request has expired.")
            return redirect('student_dashboard')
        
        # if qr signature is empty, generate it
        if not payment_request.qr_signature:
            payment_request.qr_signature = create_signature(str(payment_request.request_id))
            payment_request.save(update_fields=['qr_signature'])
        
        context = {
            'payment_request': payment_request,
            'qr_data': f"PAYMENT_REQUEST|{payment_request.request_id}|{payment_request.qr_signature}",
        }
        return render(request, self.template_name, context)

class ShowPaymentQRView(StudentRequiredMixin, TemplateView):
    template_name = 'show_payment_qr.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request_id = self.kwargs['request_id']
        student = self.request.user.student_profile
        
        try:
            payment_request = get_object_or_404(
                PaymentRequest, 
                request_id=request_id, 
                student=student
            )
        except ValueError:
            raise Http404("Invalid Payment Request ID.")
            
        if payment_request.is_expired():
            payment_request.status = 'EXPIRED'
            payment_request.save()
            
        context['request'] = payment_request
        context['qr_data'] = f"PAYMENT_REQUEST|{payment_request.request_id}|{payment_request.qr_signature}"
        return context

# officer views
class OfficerDashboardView(OfficerRequiredMixin, TemplateView):
    template_name = 'paymentorg/officer_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        if user.is_superuser:
            messages.info(self.request, "Superuser: Displaying system-wide statistics.")
            
            context.update({
                'is_superuser_only': True,
                'officer': user,
                'organization': None,
                'total_collected_system': Payment.objects.filter(status='COMPLETED', is_void=False).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
                'pending_requests': PaymentRequest.objects.filter(status='PENDING', expires_at__gt=timezone.now()).order_by('created_at')[:5],
                'posted_requests': BulkPaymentPosting.objects.all().order_by('-created_at')[:20],
                'recent_payments': Payment.objects.filter(status='COMPLETED', is_void=False).order_by('-created_at')[:5],
            })
        
        else:
            officer = user.officer_profile
            organization = officer.organization
            today = timezone.now().date()
            
            pending_requests = PaymentRequest.objects.filter(
                organization=organization,
                status='PENDING',
                expires_at__gt=timezone.now()
            ).order_by('created_at')[:10]
            
            # Get posted payment postings (bulk fees posted by this officer or organization)
            posted_requests = BulkPaymentPosting.objects.filter(
                organization=organization
            ).order_by('-created_at')[:20]
            
            logger.info(f"Officer Dashboard - Organization: {organization.name}, Posted Requests Count: {posted_requests.count()}, Records: {list(posted_requests.values('fee_type__name', 'amount', 'student_count'))}")
            
            context.update({
                'is_superuser_only': False,
                'officer': officer,
                'organization': organization,
                'pending_requests': pending_requests,
                'posted_requests': posted_requests,
                'today_collections': organization.get_today_collection(),
                'recent_payments': Payment.objects.filter(
                    organization=organization,
                    status='COMPLETED',
                    is_void=False,
                    created_at__date=today
                ).order_by('-created_at')[:5],
            })
        return context

class ProcessPaymentRequestView(OfficerRequiredMixin, View):
    template_name = 'officer_process_payment.html'
    
    def get_payment_request(self, request_id, signature):
        try:
            payment_request = get_object_or_404(
                PaymentRequest, 
                request_id=request_id
            )
        except ValueError:
            raise Http404("Invalid Payment Request ID format.")

        # Validate signature - it's created from just the request_id
        request_id_str = str(payment_request.request_id)
        expected_signature = create_signature(request_id_str)
        
        logger.info(f"QR Validation - Request ID: {request_id_str}, Provided signature: {signature}, Expected: {expected_signature}")
        
        if not validate_signature(request_id_str, signature):
            logger.warning(f"Signature mismatch for request {request_id_str}")
            messages.error(self.request, "QR Code signature failed verification.")
            return None
            
        user = self.request.user
        
        if not user.is_superuser:
            officer = user.officer_profile
            # Check if officer has access to this payment request's organization
            accessible_org_ids = officer.organization.get_accessible_organization_ids()
            if payment_request.organization_id not in accessible_org_ids:
                messages.error(self.request, "This request is for a different organization.")
                return None
        
        if payment_request.status != 'PENDING':
            messages.error(self.request, f"This request is already {payment_request.status}. Cannot be processed.")
            return None

        if payment_request.is_expired():
            payment_request.status = 'EXPIRED'
            payment_request.save()
            messages.error(self.request, "This request has expired.")
            return None
            
        return payment_request

    def get(self, request, request_id, signature):
        payment_request = self.get_payment_request(request_id, signature)
        if not payment_request:
            return redirect('officer_dashboard')
        
        # generate or number from request_id (unique transaction id)
        or_number = f"OR-{str(payment_request.request_id).replace('-', '').upper()[:12]}"
        
        form = OfficerPaymentProcessForm(fee_amount=payment_request.amount)
        
        context = {
            'request': payment_request,
            'form': form,
            'student': payment_request.student,
            'or_number': or_number,
            'student_payment_method': payment_request.get_payment_method_display(),
        }
        return render(request, self.template_name, context)

    @transaction.atomic
    def post(self, request, request_id, signature):
        payment_request = self.get_payment_request(request_id, signature)
        if not payment_request:
            return redirect('officer_dashboard')
            
        form = OfficerPaymentProcessForm(
            request.POST, 
            fee_amount=payment_request.amount
        )
        
        if form.is_valid():
            officer = request.user.officer_profile if hasattr(request.user, 'officer_profile') else None
            
            # generate or number from request_id (unique transaction id from qr)
            or_number = f"OR-{str(payment_request.request_id).replace('-', '').upper()[:12]}"
            
            # check if or number already exists (shouldn't happen, but safety check)
            if Payment.objects.filter(or_number=or_number).exists():
                # if exists, append timestamp
                or_number = f"OR-{str(payment_request.request_id).replace('-', '').upper()[:12]}-{int(timezone.now().timestamp())}"
            
            payment = Payment.objects.create(
                payment_request=payment_request,
                student=payment_request.student,
                organization=payment_request.organization,
                fee_type=payment_request.fee_type,
                amount=payment_request.amount,
                amount_received=form.cleaned_data['amount_received'],
                or_number=or_number,
                payment_method=form.cleaned_data['payment_method'],
                processed_by=officer,
                notes=form.cleaned_data['notes']
            )
            payment.save() 
            
            payment_request.mark_as_paid()
            
            receipt = Receipt.objects.create(
                payment=payment,
                or_number=payment.or_number,
                verification_signature=create_signature(payment.or_number) 
            )
            
            # send receipt via email
            try:
                if send_receipt_email(receipt, payment.student):
                    messages.info(request, f"Receipt email sent to {payment.student.email}")
                else:
                    messages.warning(request, "Failed to send receipt email.")
            except Exception as e:
                messages.warning(request, f"Error sending email: {str(e)}")
            
            
            ActivityLog.objects.create(
                user=request.user,
                action='payment_processed',
                description=f'Processed payment OR#{payment.or_number} for {payment.student.student_id_number}.',
                payment=payment,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(request, f"Payment successfully processed! OR#{payment.or_number}. Change given: ₱{payment.change_given:.2f}")
            return redirect('officer_dashboard')
        
        context = {
            'request': payment_request,
            'form': form,
            'student': payment_request.student,
        }
        return render(request, self.template_name, context)

class OfficerScanQRView(OfficerRequiredMixin, TemplateView):
    # scan qr codes
    template_name = 'officer_scan_qr.html'

class AdminOrganizationDashboardView(StaffRequiredMixin, TemplateView):
    template_name = 'admin_org_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        code = self.kwargs.get('code')
        organization = get_object_or_404(Organization, code=code)
        today = timezone.now().date()

        pending_requests = PaymentRequest.objects.filter(
            organization=organization,
            status='PENDING',
            expires_at__gt=timezone.now()
        ).order_by('created_at')[:10]

        context.update({
            'organization': organization,
            'today_collections': organization.get_today_collection(),
            'total_collected': organization.get_total_collected(),
            'pending_requests': pending_requests,
            'recent_payments': Payment.objects.filter(
                organization=organization,
                status='COMPLETED',
                is_void=False,
                created_at__date=today
            ).order_by('-created_at')[:5],
        })
        return context

class PostBulkPaymentView(OfficerRequiredMixin, View):
    # post payments in bulk
    template_name = 'officer_post_payment.html'
    
    def get_organization(self):
        user = self.request.user
        if hasattr(user, 'officer_profile'):
            return user.officer_profile.organization
        # fallback for superuser without officer profile: use first organization
        if user.is_superuser:
            return Organization.objects.first()
        return None
    
    def get(self, request):
        organization = self.get_organization()
        if not organization:
            messages.error(request, "You must be assigned to an organization to post bulk payments.")
            return redirect('officer_dashboard')
        
        form = BulkPaymentPostForm(organization=organization)
        
        context = {
            'form': form,
            'organization': organization,
        }
        return render(request, self.template_name, context)
    
    @transaction.atomic
    def post(self, request):
        organization = self.get_organization()
        if not organization:
            messages.error(request, "You must be assigned to an organization to post bulk payments.")
            return redirect('officer_dashboard')
        
        form = BulkPaymentPostForm(request.POST, organization=organization)
        
        if form.is_valid():
            fee_type_name = form.cleaned_data['fee_type_name']
            fee_amount = form.cleaned_data['fee_amount']
            notes = form.cleaned_data.get('notes', '')
            
            # get current academic year and semester
            try:
                current_period = AcademicYearConfig.objects.get(is_current=True)
                academic_year = current_period.academic_year
                semester = current_period.semester
            except AcademicYearConfig.DoesNotExist:
                academic_year = timezone.now().year
                semester = '1ST'
            
            # create or get fee type
            fee_type, created = FeeType.objects.get_or_create(
                organization=organization,
                name=fee_type_name,
                academic_year=academic_year,
                semester=semester,
                defaults={
                    'amount': fee_amount,
                    'applicable_year_levels': 'All',
                    'is_active': True,
                }
            )
            
            if not created:
                # update amount if fee type already exists
                fee_type.amount = fee_amount
                fee_type.save()
            
            # Get all students belonging to this organization
            # Simply get all active students (they belong to the organization implicitly)
            students = Student.objects.filter(
                academic_year=academic_year,
                semester=semester,
                is_active=True
            ).distinct()
            
            # exclude students who already paid this fee
            paid_students = Payment.objects.filter(
                fee_type=fee_type,
                status='COMPLETED',
                is_void=False
            ).values_list('student_id', flat=True)
            
            # exclude students who already have a pending paymentrequest for this fee
            pending_requests = PaymentRequest.objects.filter(
                fee_type=fee_type,
                status='PENDING'
            ).values_list('student_id', flat=True)
            
            students = students.exclude(id__in=list(paid_students) + list(pending_requests))
            
            logger.info(f"Found {students.count()} eligible students for bulk payment in {organization.name}")
            
            if not students.exists():
                messages.warning(request, "No eligible students found in your organization for this fee type.")
                context = {'form': form, 'organization': organization}
                return render(request, self.template_name, context)
            
            created_count = 0
            failed_count = 0
            
            logger.info(f"Starting bulk payment posting: {len(list(students))} eligible students found")
            
            # create paymentrequest objects for each student
            for student in students:
                try:
                    logger.debug(f"Creating payment request for student {student.student_id_number}")
                    # create paymentrequest with unique request_id
                    payment_request = PaymentRequest.objects.create(
                        student=student,
                        organization=organization,
                        fee_type=fee_type,
                        amount=fee_amount,
                        payment_method='CASH',  # Default, student will select when generating QR
                        status='PENDING',
                        expires_at=timezone.now() + timedelta(days=30),  # Give students 30 days to pay
                        qr_signature='',  # Will be generated when student creates QR
                        created_by=request.user,  # Track who posted this bulk payment
                        notes=notes
                    )
                    
                    # generate qr signature for the request_id
                    payment_request.qr_signature = create_signature(str(payment_request.request_id))
                    payment_request.save(update_fields=['qr_signature'])
                    
                    created_count += 1
                    logger.debug(f"Successfully created payment request {payment_request.request_id}")
                    
                except Exception as e:
                    logger.error(f'Error creating payment request for {student.student_id_number}: {str(e)}', exc_info=True)
                    failed_count += 1
                    continue
            
            ActivityLog.objects.create(
                user=request.user,
                action='bulk_payment_posted',
                description=f'Posted bulk payment request for {fee_type_name} to {created_count} students in {organization.name}.',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            # Track the bulk posting
            if created_count > 0:
                BulkPaymentPosting.objects.create(
                    organization=organization,
                    fee_type=fee_type,
                    amount=fee_amount,
                    posted_by=request.user,
                    student_count=created_count,
                    notes=notes
                )
            
            messages.success(
                request,
                f"Bulk payment posted successfully! "
                f"Created {created_count} payment request(s) for {fee_type_name}. "
                f"Students can now generate QR codes from their dashboard to pay."
            )
            
            if failed_count > 0:
                messages.warning(request, f"{failed_count} payment request(s) failed to create.")
            
            return redirect('officer_dashboard')
        
        context = {
            'form': form,
            'organization': organization,
        }
        return render(request, self.template_name, context)

class VoidPaymentView(OfficerRequiredMixin, UpdateView):
    model = Payment
    form_class = VoidPaymentForm
    template_name = 'officer_void_payment.html'
    success_url = reverse_lazy('officer_dashboard')

    def test_func(self):
        user = self.request.user
        if user.is_superuser:
            return True
        return hasattr(user, 'officer_profile') and user.officer_profile.can_void_payments

    def get_object(self):
        user = self.request.user
        
        if user.is_superuser:
            payment = get_object_or_404(Payment, pk=self.kwargs['pk'])
        else:
            # Get payment and verify officer has access to the payment's organization
            payment = get_object_or_404(Payment, pk=self.kwargs['pk'])
            accessible_org_ids = user.officer_profile.organization.get_accessible_organization_ids()
            if payment.organization_id not in accessible_org_ids:
                raise Http404("Payment not found in your organization")
            
        if payment.status != 'COMPLETED' or payment.is_void:
            messages.error(self.request, "Only COMPLETED, non-voided payments can be voided.")
            raise Http404 
        return payment

    def form_valid(self, form):
        payment = self.get_object()
        officer = self.request.user.officer_profile if hasattr(self.request.user, 'officer_profile') else None
        reason = form.cleaned_data['void_reason']

        with transaction.atomic():
            payment.mark_as_void(officer=officer, reason=reason)

            ActivityLog.objects.create(
                user=self.request.user,
                action='payment_voided',
                description=f'Voided payment OR#{payment.or_number}. Reason: {reason}',
                payment=payment,
                ip_address=self.request.META.get('REMOTE_ADDR')
            )
        
        messages.success(self.request, f"Payment OR#{payment.or_number} has been successfully VOIDED.")
        return redirect(self.success_url)

class UpdateStudentProfileView(LoginRequiredMixin, UpdateView):
    model = Student
    form_class = StudentForm
    template_name = 'update_profile.html'
    success_url = reverse_lazy('student_dashboard')
    
    def get_object(self):
        return self.request.user.student_profile
    
    def form_valid(self, form):
        ActivityLog.objects.create(
            user=self.request.user,
            action='profile_updated',
            description='Updated student profile',
            ip_address=self.request.META.get('REMOTE_ADDR')
        )
        messages.success(self.request, 'Profile updated successfully.')
        return super().form_valid(form)

class UpdateOfficerProfileView(LoginRequiredMixin, UpdateView):
    model = Officer
    form_class = OfficerForm
    template_name = 'update_profile.html'
    success_url = reverse_lazy('officer_dashboard')
    
    def get_object(self):
        if self.request.user.is_superuser and not hasattr(self.request.user, 'officer_profile'):
            raise Http404("Superuser does not have a manageable Officer profile.")
        return self.request.user.officer_profile
    
    def form_valid(self, form):
        ActivityLog.objects.create(
            user=self.request.user,
            action='profile_updated',
            description='Updated officer profile',
            ip_address=self.request.META.get('REMOTE_ADDR')
        )
        messages.success(self.request, 'Profile updated successfully.')
        return super().form_valid(form)

class PaymentRequestStatusAPI(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        request_id = self.kwargs['request_id']
        try:
            payment_request = PaymentRequest.objects.get(
                request_id=request_id,
                student=request.user.student_profile
            )
            
            if payment_request.status == 'PENDING' and payment_request.is_expired():
                payment_request.status = 'EXPIRED'
                payment_request.save()

            data = {
                'status': payment_request.status,
                'is_expired': payment_request.is_expired(),
                'time_remaining': payment_request.get_time_remaining(),
            }
            if payment_request.status == 'PAID' and hasattr(payment_request, 'payment'):
                data['payment_id'] = payment_request.payment.id
                
            return JsonResponse(data)
            
        except PaymentRequest.DoesNotExist:
            return JsonResponse({'status': 'NOT_FOUND'}, status=404)
        except ValueError:
            return JsonResponse({'status': 'INVALID_ID'}, status=400)


class CreateOrganizationView(StaffRequiredMixin, CreateView):
    model = Organization
    form_class = OrganizationForm
    template_name = 'admin/create_form.html'
    success_url = reverse_lazy('organization_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Create New Organization"
        return context

class CreateFeeTypeView(StaffRequiredMixin, CreateView):
    model = FeeType
    form_class = FeeTypeForm
    template_name = 'admin/create_form.html'
    success_url = reverse_lazy('feetype_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Create New Fee Type"
        return context

# organization crud
class OrganizationListView(StaffRequiredMixin, ListView):
    model = Organization
    template_name = 'admin/organization_list.html'
    context_object_name = 'organizations'
    paginate_by = 20
    
    def get_queryset(self):
        return Organization.objects.all().order_by('name')

class OrganizationDetailView(StaffRequiredMixin, DetailView):
    model = Organization
    template_name = 'admin/organization_detail.html'
    context_object_name = 'organization'

class OrganizationUpdateView(StaffRequiredMixin, UpdateView):
    model = Organization
    form_class = OrganizationForm
    template_name = 'admin/update_form.html'
    success_url = reverse_lazy('organization_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Update Organization: {self.object.name}"
        return context

class OrganizationDeleteView(StaffRequiredMixin, DeleteView):
    model = Organization
    template_name = 'admin/delete_confirm.html'
    success_url = reverse_lazy('organization_list')
    context_object_name = 'organization'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Delete Organization"
        context['object_name'] = self.object.name
        return context

# fee type crud
class FeeTypeListView(StaffRequiredMixin, ListView):
    model = FeeType
    template_name = 'admin/feetype_list.html'
    context_object_name = 'fee_types'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = FeeType.objects.select_related('organization').all()
        org_filter = self.request.GET.get('organization')
        if org_filter:
            queryset = queryset.filter(organization_id=org_filter)
        return queryset.order_by('organization__name', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['organizations'] = Organization.objects.filter(is_active=True)
        return context

class FeeTypeDetailView(StaffRequiredMixin, DetailView):
    model = FeeType
    template_name = 'admin/feetype_detail.html'
    context_object_name = 'fee_type'

class FeeTypeUpdateView(StaffRequiredMixin, UpdateView):
    model = FeeType
    form_class = FeeTypeForm
    template_name = 'admin/update_form.html'
    success_url = reverse_lazy('feetype_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Update Fee Type: {self.object.name}"
        return context

class FeeTypeDeleteView(StaffRequiredMixin, DeleteView):
    model = FeeType
    template_name = 'admin/delete_confirm.html'
    success_url = reverse_lazy('feetype_list')
    context_object_name = 'fee_type'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Delete Fee Type"
        context['object_name'] = f"{self.object.organization.code} - {self.object.name}"
        return context

# student crud
class StudentListView(SuperOfficerOrStaffMixin, ListView):
    model = Student
    template_name = 'admin/student_list.html'
    context_object_name = 'students'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Student.objects.select_related('user').all()
        
        # Filter by organization if super officer
        org = self.get_user_organization()
        if org:
            # Get all students who have fees in this organization
            queryset = queryset.filter(applicable_fees__organization=org).distinct()
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(student_id_number__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search)
            )
        return queryset.order_by('last_name', 'first_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['is_super_officer'] = hasattr(self.request.user, 'officer_profile') and self.request.user.officer_profile.is_super_officer
        if context['is_super_officer']:
            context['organization'] = self.request.user.officer_profile.organization
        return context

class StudentDetailView(SuperOfficerOrStaffMixin, DetailView):
    model = Student
    template_name = 'admin/student_detail.html'
    context_object_name = 'student'
    
    def get_object(self, queryset=None):
        student = super().get_object(queryset)
        # Check if super officer has access to this student
        org = self.get_user_organization()
        if org:
            # Verify student has fees in this organization
            if not student.applicable_fees.filter(organization=org).exists():
                raise Http404("Student not found in your organization")
        return student
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.object
        context['pending_payments'] = student.get_pending_payments()
        context['completed_payments'] = student.get_completed_payments()[:10]
        context['is_super_officer'] = hasattr(self.request.user, 'officer_profile') and self.request.user.officer_profile.is_super_officer
        if context['is_super_officer']:
            context['organization'] = self.request.user.officer_profile.organization
        return context

class StudentUpdateView(SuperOfficerOrStaffMixin, UpdateView):
    model = Student
    form_class = StudentForm
    template_name = 'admin/update_form.html'
    success_url = reverse_lazy('student_list')
    
    def get_object(self, queryset=None):
        student = super().get_object(queryset)
        # Check if super officer has access to this student
        org = self.get_user_organization()
        if org:
            if not student.applicable_fees.filter(organization=org).exists():
                raise Http404("Student not found in your organization")
        return student
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Update Student: {self.object.get_full_name()}"
        return context

class StudentDeleteView(SuperOfficerOrStaffMixin, DeleteView):
    model = Student
    template_name = 'admin/delete_confirm.html'
    success_url = reverse_lazy('student_list')
    context_object_name = 'student'
    
    def get_object(self, queryset=None):
        student = super().get_object(queryset)
        # Check if super officer has access to this student
        org = self.get_user_organization()
        if org:
            if not student.applicable_fees.filter(organization=org).exists():
                raise Http404("Student not found in your organization")
        return student
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Delete Student"
        context['object_name'] = f"{self.object.student_id_number} - {self.object.get_full_name()}"
        return context

# officer crud
class OfficerListView(SuperOfficerOrStaffMixin, ListView):
    model = Officer
    template_name = 'admin/officer_list.html'
    context_object_name = 'officers'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Officer.objects.select_related('user', 'organization').all()
        
        # Filter by organization if super officer
        org = self.get_user_organization()
        if org:
            queryset = queryset.filter(organization=org)
        
        org_filter = self.request.GET.get('organization')
        if org_filter and not org:  # Only allow filtering if staff (not super officer)
            queryset = queryset.filter(organization_id=org_filter)
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(employee_id__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search)
            )
        return queryset.order_by('organization__name', 'last_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['organizations'] = Organization.objects.filter(is_active=True)
        context['search_query'] = self.request.GET.get('search', '')
        context['org_filter'] = self.request.GET.get('organization', '')
        context['is_super_officer'] = hasattr(self.request.user, 'officer_profile') and self.request.user.officer_profile.is_super_officer
        if context['is_super_officer']:
            context['organization'] = self.request.user.officer_profile.organization
        return context

class OfficerDetailView(SuperOfficerOrStaffMixin, DetailView):
    model = Officer
    template_name = 'admin/officer_detail.html'
    context_object_name = 'officer'
    
    def get_object(self, queryset=None):
        officer = super().get_object(queryset)
        # Check if super officer has access to this officer
        org = self.get_user_organization()
        if org and officer.organization != org:
            raise Http404("Officer not found in your organization")
        return officer
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        officer = self.object
        context['processed_payments'] = officer.processed_payments.filter(is_void=False).order_by('-created_at')[:10]
        context['voided_payments'] = officer.voided_payments.all().order_by('-voided_at')[:10]
        context['is_super_officer'] = hasattr(self.request.user, 'officer_profile') and self.request.user.officer_profile.is_super_officer
        if context['is_super_officer']:
            context['organization'] = self.request.user.officer_profile.organization
        return context

class OfficerUpdateView(SuperOfficerOrStaffMixin, UpdateView):
    model = Officer
    form_class = OfficerForm
    template_name = 'admin/update_form.html'
    success_url = reverse_lazy('officer_list')
    
    def get_object(self, queryset=None):
        officer = super().get_object(queryset)
        # Check if super officer has access to this officer
        org = self.get_user_organization()
        if org and officer.organization != org:
            raise Http404("Officer not found in your organization")
        return officer
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Update Officer: {self.object.get_full_name()}"
        return context

class OfficerDeleteView(SuperOfficerOrStaffMixin, DeleteView):
    model = Officer
    template_name = 'admin/delete_confirm.html'
    success_url = reverse_lazy('officer_list')
    context_object_name = 'officer'
    
    def get_object(self, queryset=None):
        officer = super().get_object(queryset)
        # Check if super officer has access to this officer
        org = self.get_user_organization()
        if org and officer.organization != org:
            raise Http404("Officer not found in your organization")
        return officer
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Delete Officer"
        context['object_name'] = f"{self.object.employee_id} - {self.object.get_full_name()}"
        return context

# payment request management
class PaymentRequestListView(SuperOfficerOrStaffMixin, ListView):
    model = PaymentRequest
    template_name = 'admin/paymentrequest_list.html'
    context_object_name = 'payment_requests'
    paginate_by = 30
    
    def get_queryset(self):
        queryset = PaymentRequest.objects.select_related(
            'student', 'organization', 'fee_type'
        ).all()
        
        # Filter by organization if super officer
        org = self.get_user_organization()
        if org:
            queryset = queryset.filter(organization=org)
        
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        org_filter = self.request.GET.get('organization')
        if org_filter and not org:  # Only allow filtering if staff
            queryset = queryset.filter(organization_id=org_filter)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['organizations'] = Organization.objects.filter(is_active=True)
        context['status_choices'] = PaymentRequest._meta.get_field('status').choices
        context['current_filters'] = {
            'status': self.request.GET.get('status', ''),
            'organization': self.request.GET.get('organization', ''),
        }
        context['is_super_officer'] = hasattr(self.request.user, 'officer_profile') and self.request.user.officer_profile.is_super_officer
        if context['is_super_officer']:
            context['organization'] = self.request.user.officer_profile.organization
        return context

class PaymentRequestDetailView(SuperOfficerOrStaffMixin, DetailView):
    model = PaymentRequest
    template_name = 'admin/paymentrequest_detail.html'
    context_object_name = 'request'
    
    def get_object(self, queryset=None):
        payment_request = super().get_object(queryset)
        # Check if officer has access to this payment request
        if not self.request.user.is_staff:
            if hasattr(self.request.user, 'officer_profile'):
                accessible_org_ids = self.request.user.officer_profile.organization.get_accessible_organization_ids()
                if payment_request.organization_id not in accessible_org_ids:
                    raise Http404("Payment request not found in your organization")
        return payment_request

# payment management
class PaymentListView(SuperOfficerOrStaffMixin, ListView):
    model = Payment
    template_name = 'admin/payment_list.html'
    context_object_name = 'payments'
    paginate_by = 30
    
    def get_queryset(self):
        queryset = Payment.objects.select_related(
            'student', 'organization', 'fee_type', 'processed_by'
        ).all()
        
        # Filter by organization if officer (using organization hierarchy)
        if not self.request.user.is_staff:
            if hasattr(self.request.user, 'officer_profile'):
                # Get all accessible organizations (including child orgs)
                accessible_org_ids = self.request.user.officer_profile.organization.get_accessible_organization_ids()
                queryset = queryset.filter(organization_id__in=accessible_org_ids)
        
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        void_filter = self.request.GET.get('is_void')
        if void_filter == 'true':
            queryset = queryset.filter(is_void=True)
        elif void_filter == 'false':
            queryset = queryset.filter(is_void=False)
        
        org_filter = self.request.GET.get('organization')
        if org_filter and self.request.user.is_staff:  # Only allow filtering if staff
            queryset = queryset.filter(organization_id=org_filter)
        
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['organizations'] = Organization.objects.filter(is_active=True)
        context['status_choices'] = Payment._meta.get_field('status').choices
        context['current_filters'] = {
            'status': self.request.GET.get('status', ''),
            'is_void': self.request.GET.get('is_void', ''),
            'organization': self.request.GET.get('organization', ''),
            'date_from': self.request.GET.get('date_from', ''),
            'date_to': self.request.GET.get('date_to', ''),
        }
        context['is_super_officer'] = hasattr(self.request.user, 'officer_profile') and self.request.user.officer_profile.is_super_officer
        if context['is_super_officer']:
            context['organization'] = self.request.user.officer_profile.organization
        return context

class PaymentDetailView(SuperOfficerOrStaffMixin, DetailView):
    model = Payment
    template_name = 'admin/payment_detail.html'
    context_object_name = 'payment'
    
    def get_object(self, queryset=None):
        payment = super().get_object(queryset)
        # Check if super officer has access to this payment
        org = self.get_user_organization()
        if org and payment.organization != org:
            raise Http404("Payment not found in your organization")
        return payment

# academic year config crud
class AcademicYearConfigListView(StaffRequiredMixin, ListView):
    model = AcademicYearConfig
    template_name = 'admin/academicyear_list.html'
    context_object_name = 'academic_years'
    paginate_by = 20

class AcademicYearConfigCreateView(StaffRequiredMixin, CreateView):
    model = AcademicYearConfig
    form_class = AcademicYearConfigForm
    template_name = 'admin/create_form.html'
    success_url = reverse_lazy('academicyear_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Create Academic Year Configuration"
        return context

class AcademicYearConfigUpdateView(StaffRequiredMixin, UpdateView):
    model = AcademicYearConfig
    form_class = AcademicYearConfigForm
    template_name = 'admin/update_form.html'
    success_url = reverse_lazy('academicyear_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Update Academic Year: {self.object.academic_year} - {self.object.semester}"
        return context

class AcademicYearConfigDeleteView(StaffRequiredMixin, DeleteView):
    model = AcademicYearConfig
    template_name = 'admin/delete_confirm.html'
    success_url = reverse_lazy('academicyear_list')
    context_object_name = 'academic_year'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Delete Academic Year Configuration"
        context['object_name'] = f"{self.object.academic_year} - {self.object.semester}"
        return context

# receipt views
class ReceiptListView(SuperOfficerOrStaffMixin, ListView):
    model = Receipt
    template_name = 'admin/receipt_list.html'
    context_object_name = 'receipts'
    paginate_by = 30
    
    def get_queryset(self):
        queryset = Receipt.objects.select_related('payment', 'payment__student', 'payment__organization').all()
        
        # Filter by organization if super officer
        org = self.get_user_organization()
        if org:
            queryset = queryset.filter(payment__organization=org)
        
        or_search = self.request.GET.get('or_number')
        if or_search:
            queryset = queryset.filter(or_number__icontains=or_search)
        return queryset.order_by('-created_at')

class ReceiptDetailView(LoginRequiredMixin, DetailView):
    model = Receipt
    template_name = 'admin/receipt_detail.html'
    context_object_name = 'receipt'
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Receipt.objects.all()
        elif hasattr(user, 'student_profile'):
            return Receipt.objects.filter(payment__student=user.student_profile)
        elif hasattr(user, 'officer_profile'):
            return Receipt.objects.filter(payment__organization=user.officer_profile.organization)
        return Receipt.objects.none()

# activity log views
class ActivityLogListView(StaffRequiredMixin, ListView):
    model = ActivityLog
    template_name = 'admin/activitylog_list.html'
    context_object_name = 'logs'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = ActivityLog.objects.select_related('user', 'payment', 'payment_request').all()
        action_filter = self.request.GET.get('action')
        if action_filter:
            queryset = queryset.filter(action__icontains=action_filter)
        user_filter = self.request.GET.get('user')
        if user_filter:
            queryset = queryset.filter(user__username__icontains=user_filter)
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_filters'] = {
            'action': self.request.GET.get('action', ''),
            'user': self.request.GET.get('user', ''),
        }
        return context