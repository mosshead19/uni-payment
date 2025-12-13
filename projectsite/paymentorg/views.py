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
from django.http import JsonResponse, Http404, HttpResponse
import uuid
import hmac
import hashlib
import csv
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
    BulkPaymentPostForm, PromoteStudentToOfficerForm, DemoteOfficerToStudentForm,
    CreateOfficerForm, CompleteProfileForm
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
    # Use a persistent QR signature key that never changes between deployments
    # This ensures QR codes remain valid even when SECRET_KEY is rotated
    qr_signature_key = getattr(settings, 'QR_SIGNATURE_KEY', None)
    
    if not qr_signature_key:
        raise ValueError(
            "QR_SIGNATURE_KEY must be set in settings.py to ensure QR code stability across deployments. "
            "Add a long random string to your .env file as QR_SIGNATURE_KEY and load it in settings.py"
        )
    
    secret_key = qr_signature_key.encode('utf-8')
    message = str(message_string).encode('utf-8')
    signature = hmac.new(secret_key, message, hashlib.sha256).hexdigest()
    return signature

def validate_signature(message_string, provided_signature):
    expected_signature = create_signature(message_string)
    return hmac.compare_digest(expected_signature, provided_signature)

# affiliation helpers
def normalize_program_affiliation(affiliation):
    """Map organization program codes (e.g., ESSA, COMSCI, IT) to Course.program_type values.
    Returns the canonical program_type or None if unknown.
    """
    if not affiliation:
        return None
    code = str(affiliation).strip().upper()
    mapping = {
        # Environmental Studies & Sciences Association
        'ESSA': 'ENVIRONMENTAL_SCIENCE',
        'ENVSCI': 'ENVIRONMENTAL_SCIENCE',
        'ENVIRONMENTAL_SCIENCE': 'ENVIRONMENTAL_SCIENCE',
        # Computer Science
        'COMSCI': 'COMPUTER_SCIENCE',
        'CS': 'COMPUTER_SCIENCE',
        'COMPUTER_SCIENCE': 'COMPUTER_SCIENCE',
        # Information Technology
        'IT': 'INFORMATION_TECHNOLOGY',
        
        'INFORMATION_TECHNOLOGY': 'INFORMATION_TECHNOLOGY',
        # Marine Biology
        'MARBIO': 'MARINE_BIOLOGY',
        'MARINE_BIOLOGY': 'MARINE_BIOLOGY',
        # Medical Biology
        'MEDBIO': 'MEDICAL_BIOLOGY',
        'MEDICAL_BIOLOGY': 'MEDICAL_BIOLOGY',
    }
    return mapping.get(code)

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
            return reverse_lazy('complete_profile')
    
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
        # Allow officers with promotion authority or super officer
        if hasattr(user, 'officer_profile'):
            return user.officer_profile.can_promote_officers or user.officer_profile.is_super_officer
        return False
    
    def handle_no_permission(self):
        messages.error(self.request, "Administrator or Officer with promotion authority required.")
        return redirect('login')
    
    def get_accessible_students(self):
        """Get students accessible based on org scope - excluding already promoted students"""
        user = self.request.user
        
        # Base: all active, non-promoted students
        base_qs = Student.objects.filter(
            is_active=True
        ).exclude(
            user__officer_profile__isnull=False
        ).select_related('course', 'college').order_by('last_name', 'first_name').distinct()
        
        # Superusers see everything
        if user.is_superuser:
            return base_qs
        
        # Officers (even if they are staff) are restricted by their organization
        if hasattr(user, 'officer_profile'):
            officer = user.officer_profile
            org = officer.organization
            
            # PROGRAM-level: only students in this program
            if org.hierarchy_level == 'PROGRAM':
                return base_qs.filter(course__program_type=org.program_affiliation)
            
            # COLLEGE-level: all students (college represents whole college)
            elif org.hierarchy_level == 'COLLEGE':
                return base_qs
            
            # Default fallback
            return base_qs
            
        # Non-officer staff see everything
        if user.is_staff:
            return base_qs
        
        return Student.objects.none()
    
    def get_accessible_organizations(self):
        """Get organizations accessible to this user"""
        user = self.request.user
        
        # Superusers see everything
        if user.is_superuser:
            from paymentorg.models import Organization
            return Organization.objects.filter(is_active=True)
        
        # Officers (even if they are staff) are restricted by their organization
        if hasattr(user, 'officer_profile'):
            officer = user.officer_profile
            return officer.organization.get_accessible_organizations()
            
        # Non-officer staff see everything
        if user.is_staff:
            from paymentorg.models import Organization
            return Organization.objects.filter(is_active=True)
        
        return []
    
    def get(self, request):
        # Get accessible students
        accessible_students = self.get_accessible_students()
        
        # Restrict organizations based on user type
        if hasattr(request.user, 'officer_profile'):
            officer = request.user.officer_profile
            # Officers can only assign to their own organization
            accessible_orgs = Organization.objects.filter(id=officer.organization.id)
        else:
            # Staff can access all organizations
            accessible_orgs = Organization.objects.filter(is_active=True)
        
        form = PromoteStudentToOfficerForm(
            student_queryset=accessible_students,
            organization_queryset=accessible_orgs
        )
        
        context = {
            'form': form,
            'is_admin': request.user.is_staff,
            'user_organization': request.user.officer_profile.organization if hasattr(request.user, 'officer_profile') else None
        }
        return render(request, self.template_name, context)
    
    @transaction.atomic
    def post(self, request):
        # Filter form choices based on user's accessible students
        accessible_students = self.get_accessible_students()
        
        # For program-level officers, restrict organization to only their own
        if hasattr(request.user, 'officer_profile'):
            officer = request.user.officer_profile
            # Only allow assigning to their own organization
            accessible_orgs = Organization.objects.filter(id=officer.organization.id)
        else:
            # For superusers/staff, allow all organizations
            accessible_orgs_list = self.get_accessible_organizations()
            if isinstance(accessible_orgs_list, list):
                org_ids = [org.id for org in accessible_orgs_list]
                accessible_orgs = Organization.objects.filter(id__in=org_ids)
            else:
                accessible_orgs = accessible_orgs_list
        
        # Create form with filtered querysets
        form = PromoteStudentToOfficerForm(
            request.POST,
            student_queryset=accessible_students,
            organization_queryset=accessible_orgs
        )
        
        if form.is_valid():
            student = form.cleaned_data['student']
            organization = form.cleaned_data['organization']
            role = form.cleaned_data['role']
            can_process_payments = form.cleaned_data['can_process_payments']
            can_void_payments = form.cleaned_data['can_void_payments']
            can_generate_reports = form.cleaned_data.get('can_generate_reports', False)
            can_promote_officers = form.cleaned_data.get('can_promote_officers', False)
            is_super_officer = form.cleaned_data.get('is_super_officer', False)
            
            # Verify user can promote to this organization
            # For program-level officers, ensure they're only assigning to their own org
            if not request.user.is_superuser:
                if hasattr(request.user, 'officer_profile'):
                    officer = request.user.officer_profile
                    # Program-level officers can ONLY assign to their own organization
                    if organization.id != officer.organization.id:
                        messages.error(request, "You can only promote students to your own organization.")
                        return render(request, self.template_name, {'form': form})
                    
                    # Only officers with can_promote_officers permission can grant promotion authority
                    if can_promote_officers and not request.user.officer_profile.can_promote_officers:
                        messages.warning(request, "Only administrators and officers with promotion authority can grant promotion to others.")
                        can_promote_officers = False
                    
                    # Only super officers/admins can grant super officer status
                    if is_super_officer and not (request.user.is_superuser or request.user.officer_profile.is_super_officer):
                        messages.warning(request, "Only administrators and super officers can grant super officer status.")
                        is_super_officer = False
            
            user = student.user
            
            # Create or update Officer profile
            officer, created = Officer.objects.update_or_create(
                user=user,
                defaults={
                    'organization': organization,
                    'role': role,
                    'can_process_payments': can_process_payments,
                    'can_void_payments': can_void_payments,
                    'can_generate_reports': can_generate_reports,
                    'can_promote_officers': can_promote_officers,
                    'is_super_officer': is_super_officer,
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
                # Clear the officer_profile cache by using select_related
                from django.db.models import prefetch_related_objects
                prefetch_related_objects([request.user], 'officer_profile')
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
                f'You can now access the officer dashboard with promotion authority in {organization.name}.'
            )
            
            # If promoting the current user, redirect to officer dashboard so they see the new nav
            if request.user.id == user.id:
                return redirect('officer_dashboard')
            else:
                return redirect('promote_student_to_officer')
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
        # Allow officers with promotion authority or super officer
        if hasattr(user, 'officer_profile'):
            return user.officer_profile.can_promote_officers or user.officer_profile.is_super_officer
        return False
    
    def handle_no_permission(self):
        messages.error(self.request, "Administrator or Officer with promotion authority required.")
        return redirect('login')
    
    def get_accessible_officers(self):
        """Get officers accessible to this user based on org hierarchy"""
        user = self.request.user
        
        # Superusers see everything
        if user.is_superuser:
            return Officer.objects.filter(is_active=True)
        
        # Officers (even if they are staff) are restricted by their organization
        if hasattr(user, 'officer_profile'):
            officer = user.officer_profile
            org = officer.organization
            
            # Program-level officers see only their org
            # College/ALLORG officers see their org and all children
            if org.hierarchy_level == 'PROGRAM':
                org_ids = [org.id]
            else:
                org_ids = org.get_accessible_organization_ids()
            
            return Officer.objects.filter(
                is_active=True,
                organization_id__in=org_ids
            )
            
        # Non-officer staff see everything
        if user.is_staff:
            return Officer.objects.filter(is_active=True)
        
        return Officer.objects.none()
    
    def get(self, request):
        # Get accessible officers
        accessible_officers = self.get_accessible_officers()
        
        form = DemoteOfficerToStudentForm(officer_queryset=accessible_officers)
        
        context = {
            'form': form,
            'is_admin': request.user.is_staff,
            'user_organization': request.user.officer_profile.organization if hasattr(request.user, 'officer_profile') else None
        }
        return render(request, self.template_name, context)
    
    @transaction.atomic
    def post(self, request):
        # Get accessible officers
        accessible_officers = self.get_accessible_officers()
        
        # Create form with filtered queryset
        form = DemoteOfficerToStudentForm(request.POST, officer_queryset=accessible_officers)
        
        if form.is_valid():
            officer = form.cleaned_data['officer']
            reason = form.cleaned_data['reason']
            
            # Verify user can demote this officer
            if not request.user.is_superuser:
                if hasattr(request.user, 'officer_profile'):
                    accessible_org_ids = request.user.officer_profile.organization.get_accessible_organization_ids()
                    if officer.organization.id not in accessible_org_ids:
                        messages.error(request, "You don't have permission to demote officers in that organization.")
                        return render(request, self.template_name, {'form': form})
            
            user = officer.user
            
            # Delete the Officer object completely to make user eligible for re-promotion
            officer_id = officer.id
            officer.delete()
            
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


class SetSuperOfficerView(LoginRequiredMixin, UserPassesTestMixin, View):
    """View to set/unset super officer flag on an officer"""
    
    def test_func(self):
        user = self.request.user
        # Allow superusers
        if user.is_superuser:
            return True
        # Allow officers with promotion authority or super officer
        if hasattr(user, 'officer_profile'):
            return user.officer_profile.can_promote_officers or user.officer_profile.is_super_officer
        return False
    
    def handle_no_permission(self):
        messages.error(self.request, "You don't have permission to set super officer status.")
        return redirect('officer_dashboard')
    
    def post(self, request):
        student_id = request.POST.get('student_id')
        action = request.POST.get('action', 'toggle_super_officer')  # 'toggle_super_officer' or 'toggle_superuser'
        
        try:
            student = Student.objects.get(id=student_id)
            
            # Handle superuser toggle (only by superusers)
            if action == 'toggle_superuser':
                if not request.user.is_superuser:
                    messages.error(request, "Only superusers can modify superuser status.")
                    return redirect('list_students_in_org')
                
                # Toggle superuser status
                student.user.is_superuser = not student.user.is_superuser
                student.user.save()
                
                # Also make/revoke staff status
                student.user.is_staff = student.user.is_superuser
                student.user.save()
                
                # Log the action
                action_text = "granted" if student.user.is_superuser else "revoked"
                ActivityLog.objects.create(
                    user=request.user,
                    action='set_superuser',
                    description=f'{action_text.capitalize()} Superuser status to {student.user.get_full_name()}',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                if student.user.is_superuser:
                    messages.success(
                        request,
                        f'{student.user.get_full_name()} is now a Superuser with full system access.'
                    )
                else:
                    messages.success(
                        request,
                        f'{student.user.get_full_name()} is no longer a Superuser.'
                    )
                return redirect('list_students_in_org')
            
            # Handle super officer toggle (existing logic)
            # Verify student is an officer
            if not hasattr(student.user, 'officer_profile'):
                messages.error(request, f"{student.user.get_full_name()} is not an officer yet.")
                return redirect('list_students_in_org')
            
            officer = student.user.officer_profile
            
            # Prevent non-superusers from modifying superusers
            if not request.user.is_superuser and student.user.is_superuser:
                messages.error(request, "You don't have permission to modify superuser status.")
                return redirect('list_students_in_org')
            
            # Only superusers and super officers can change super officer status
            # Normal officers (non-super officer) cannot make anyone a super officer
            if hasattr(request.user, 'officer_profile') and not request.user.officer_profile.is_super_officer and not request.user.is_superuser:
                messages.error(request, "Only super officers and superusers can manage super officer status.")
                return redirect('list_students_in_org')
            
            # Prevent non-superusers from modifying super officers
            if not request.user.is_superuser and officer.is_super_officer:
                messages.error(request, "You don't have permission to modify super officer status.")
                return redirect('list_students_in_org')
            
            # Verify user can modify this officer
            if not request.user.is_superuser:
                if hasattr(request.user, 'officer_profile'):
                    accessible_org_ids = request.user.officer_profile.organization.get_accessible_organization_ids()
                    if officer.organization.id not in accessible_org_ids:
                        messages.error(request, "You don't have permission to modify officers in that organization.")
                        return redirect('list_students_in_org')
            
            # Toggle super officer flag
            officer.is_super_officer = not officer.is_super_officer
            officer.save()
            
            # Log the action
            action_text = "granted" if officer.is_super_officer else "revoked"
            ActivityLog.objects.create(
                user=request.user,
                action='set_super_officer',
                description=f'{action_text.capitalize()} Super Officer status to {student.user.get_full_name()}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            if officer.is_super_officer:
                messages.success(
                    request,
                    f'{student.user.get_full_name()} has been granted Super Officer status and can now manage their organization hierarchy.'
                )
            else:
                messages.success(
                    request,
                    f'{student.user.get_full_name()} has had Super Officer status revoked.'
                )
            
        except Student.DoesNotExist:
            messages.error(request, "Student not found.")
        
        return redirect('list_students_in_org')


class StepDownFromOfficerView(LoginRequiredMixin, View):
    """Allow a super officer to voluntarily step down and become a student"""
    template_name = 'registration/step_down_officer.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Only allow super officers to step down
        if not hasattr(request.user, 'officer_profile'):
            messages.error(request, "You must be an officer to access this page.")
            return redirect('student_dashboard')
        if not request.user.officer_profile.is_super_officer:
            messages.error(request, "Only super officers can step down using this feature.")
            return redirect('officer_dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        officer = request.user.officer_profile
        context = {
            'officer': officer,
            'organization': officer.organization,
        }
        return render(request, self.template_name, context)
    
    @transaction.atomic
    def post(self, request):
        reason = request.POST.get('reason', '').strip()
        confirm = request.POST.get('confirm', '')
        
        if confirm != 'STEP DOWN':
            messages.error(request, "Please type 'STEP DOWN' to confirm.")
            return redirect('officer_step_down')
        
        if not reason:
            messages.error(request, "Please provide a reason for stepping down.")
            return redirect('officer_step_down')
        
        officer = request.user.officer_profile
        user = request.user
        officer_name = officer.get_full_name()
        org_name = officer.organization.name
        
        # Delete the Officer object
        officer.delete()
        
        # Update UserProfile to remove officer flag
        UserProfile.objects.update_or_create(
            user=user,
            defaults={'is_officer': False}
        )
        
        # Refresh the user object to remove officer_profile
        user = user.__class__.objects.get(pk=user.id)
        update_session_auth_hash(request, user)
        
        # Log the action
        ActivityLog.objects.create(
            user=user,
            action='officer_step_down',
            description=f'{officer_name} voluntarily stepped down from Super Officer position at {org_name}. Reason: {reason}',
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        messages.success(
            request,
            f'You have successfully stepped down from your officer position at {org_name}. '
            f'You can continue using UniPay as a student.'
        )
        return redirect('student_dashboard')


class CreateOfficerView(LoginRequiredMixin, UserPassesTestMixin, View):
    """ALLORG-only view to create brand new officer accounts from scratch"""
    template_name = 'registration/create_officer.html'
    
    def test_func(self):
        user = self.request.user
        # Only superusers can create officers from scratch
        return user.is_superuser
    
    def handle_no_permission(self):
        messages.error(self.request, "Only administrators can access this page.")
        return redirect('officer_dashboard')
    
    def get(self, request):
        form = CreateOfficerForm()
        context = {
            'form': form,
            'user_organization': request.user.officer_profile.organization if hasattr(request.user, 'officer_profile') else None
        }
        return render(request, self.template_name, context)
    
    @transaction.atomic
    def post(self, request):
        form = CreateOfficerForm(request.POST)
        
        if form.is_valid():
            user = form.save()
            officer = user.officer_profile
            
            # Log the action
            ActivityLog.objects.create(
                user=request.user,
                action='create_officer',
                description=f'Created new officer account: {user.get_full_name()} ({user.username}) for {officer.organization.name}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(
                request,
                f'Officer account created successfully! '
                f'Username: {user.username} | Organization: {officer.organization.name}'
            )
            return redirect('officer_dashboard')
        else:
            context = {
                'form': form,
                'user_organization': request.user.officer_profile.organization if hasattr(request.user, 'officer_profile') else None
            }
            return render(request, self.template_name, context)


class ListOfficersInOrgView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """List officers in the user's organization with promote/demote actions"""
    model = Officer
    template_name = 'paymentorg/list_officers_in_org.html'
    context_object_name = 'officers'
    paginate_by = 20
    
    def test_func(self):
        user = self.request.user
        # Only officers with promote/demote ability can view this
        if hasattr(user, 'officer_profile'):
            return user.officer_profile.is_super_officer or user.officer_profile.can_promote_officers
        return False
    
    def handle_no_permission(self):
        messages.error(self.request, "You don't have permission to view this page.")
        return redirect('officer_dashboard')
    
    def get_queryset(self):
        user = self.request.user
        if not hasattr(user, 'officer_profile'):
            return Officer.objects.none()
        
        officer = user.officer_profile
        # Program-level officers see only their org; College-level/ALLORG see accessible orgs (self + children)
        if officer.organization.hierarchy_level == 'PROGRAM':
            # Program officer sees only their org
            org_ids = [officer.organization.id]
        else:
            # College/ALLORG officer sees their org and children
            org_ids = officer.organization.get_accessible_organization_ids()
        
        return Officer.objects.filter(
            is_active=True,
            organization_id__in=org_ids
        ).select_related('user', 'organization').order_by('organization', 'user__last_name', 'user__first_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['user_organization'] = user.officer_profile.organization if hasattr(user, 'officer_profile') else None
        
        # Add permission flags to each officer
        if hasattr(user, 'officer_profile'):
            officer = user.officer_profile
            for off in context['officers']:
                # Normal officers can only demote regular officers, not super officers or superusers
                off.can_demote = (not off.user.is_superuser and not off.is_super_officer and 
                                 officer.can_promote_officers)
                # Only super officers and superusers can make someone a super officer
                off.can_make_super_officer = (not off.user.is_superuser and officer.is_super_officer)
                # Only superusers can make someone a superuser
                off.can_make_superuser = user.is_superuser and not off.user.is_superuser
        
        return context


class ListStudentsInOrgView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """List students in the user's organization with promote actions"""
    model = Student
    template_name = 'paymentorg/list_students_in_org.html'
    context_object_name = 'students'
    paginate_by = 20
    
    def test_func(self):
        user = self.request.user
        # Allow superusers to access all students
        if user.is_superuser:
            return True
        # Only officers with promote/demote ability can view this
        if hasattr(user, 'officer_profile'):
            return user.officer_profile.is_super_officer or user.officer_profile.can_promote_officers
        return False
    
    def handle_no_permission(self):
        messages.error(self.request, "You don't have permission to view this page.")
        return redirect('officer_dashboard')
    
    def get_queryset(self):
        user = self.request.user
        
        # Superusers see all students across all organizations
        if user.is_superuser:
            return Student.objects.filter(is_active=True).select_related('user', 'course', 'course__college').order_by('last_name', 'first_name')
        
        if not hasattr(user, 'officer_profile'):
            return Student.objects.none()
        
        officer = user.officer_profile
        org = officer.organization
        
        # Base queryset: all active students
        qs = Student.objects.filter(is_active=True).select_related('user', 'course', 'course__college')
        
        # Filter by org scope: students whose program matches org's affiliation
        if org.hierarchy_level == 'COLLEGE':
            # College-level org: show all students
            pass
        elif org.hierarchy_level == 'PROGRAM':
            # Program-level org: show only students in that program
            if org.program_affiliation and org.program_affiliation != 'ALL':
                program_type = normalize_program_affiliation(org.program_affiliation)
                if program_type:
                    qs = qs.filter(course__program_type=program_type)
                else:
                    # Unknown program code; show none to avoid cross-program exposure
                    qs = qs.none()
        
        return qs.order_by('last_name', 'first_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if hasattr(user, 'officer_profile'):
            officer = user.officer_profile
            context['user_organization'] = officer.organization
            # Mark students who are already promoted and get their role info
            for student in context['students']:
                student.is_promoted = hasattr(student.user, 'officer_profile') and student.user.officer_profile is not None
                student.is_super_officer = False
                student.is_superuser = student.user.is_superuser
                
                if student.is_promoted:
                    student_officer = student.user.officer_profile
                    student.is_super_officer = student_officer.is_super_officer
                    student.officer_org = student_officer.organization.name
                
                # Determine role label
                if student.is_superuser:
                    student.role_label = "Superuser"
                elif student.is_super_officer:
                    student.role_label = "Super Officer"
                elif student.is_promoted:
                    student.role_label = "Officer"
                else:
                    student.role_label = "Student"
                
                # Determine if can be promoted/demoted
                student.can_promote = not student.is_promoted and not student.is_superuser and officer.can_promote_officers
                # Normal officers can only demote regular officers, not super officers or superusers
                student.can_demote = (student.is_promoted and not student.is_superuser and 
                                     not student.is_super_officer and officer.can_promote_officers)
                # Only super officers and superusers can make someone a super officer
                student.can_make_super_officer = (student.is_promoted and not student.is_superuser and 
                                                 officer.is_super_officer)
                # Only superusers can make someone a superuser
                student.can_make_superuser = user.is_superuser and not student.is_superuser
            
            # Calculate accurate stats from the current student list
            students_list = list(context['students'])
            context['officer_count'] = sum(1 for s in students_list if s.is_promoted and not s.is_super_officer and not s.is_superuser)
            context['super_officer_count'] = sum(1 for s in students_list if s.is_super_officer)
            context['superuser_count'] = sum(1 for s in students_list if s.is_superuser)
        return context


class StudentRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        # Allow access if user has student profile OR is an officer (officers can view their student dashboard too)
        has_student_profile = hasattr(user, 'student_profile')
        is_officer = False
        if hasattr(user, 'user_profile') and user.user_profile.is_officer:
            is_officer = True
        # Always treat presence of officer_profile as officer regardless of user_profile flag
        if hasattr(user, 'officer_profile'):
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
        if hasattr(user, 'user_profile') and user.user_profile.is_officer:
            is_officer = True
        # Presence of officer_profile should grant officer access even if user_profile flag not yet synced
        if hasattr(user, 'officer_profile'):
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


class AllOrgAdminMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Allows ALLORG officers (is_super_officer=True) to perform admin CRUD operations
    on organizations. Also allows staff/superusers.
    """
    def test_func(self):
        user = self.request.user
        # Allow staff/superusers
        if user.is_staff:
            return True
        # Allow super officers to manage organizations
        if hasattr(user, 'officer_profile'):
            return user.officer_profile.is_super_officer
        return False
    
    def handle_no_permission(self):
        messages.error(self.request, "Administrator access required. Only ALLORG administrators can manage organizations.")
        return redirect('officer_dashboard')
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
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            # Check for officer
            if hasattr(request.user, 'officer_profile') or request.user.is_superuser:
                return redirect('officer_dashboard')
            
            # Check for student
            if hasattr(request.user, 'student_profile'):
                return redirect('student_dashboard')
            
            # If neither, redirect to complete profile
            return redirect('complete_profile')
            
        return super().dispatch(request, *args, **kwargs)
    
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
        
        # Expiration disabled: do not auto-expire pending requests
        
        # Two-tiered fee system: Get ALL applicable fees for this student (before any filtering)
        # This includes the academic year filter already applied by get_applicable_fees()
        base_applicable_fees = student.get_applicable_fees()
        
        # Get academic year choices from the student's applicable fees only
        academic_year_choices = list(
            base_applicable_fees.values_list('academic_year', flat=True)
            .distinct()
            .order_by('-academic_year')
        )
        
        # Get filter parameters from request
        selected_academic_year = self.request.GET.get('academic_year', '')
        selected_semester = self.request.GET.get('semester', '')
        
        # Default to most recent academic year if not specified (and choices exist)
        if not selected_academic_year and academic_year_choices:
            selected_academic_year = academic_year_choices[0]
        
        # Get pending payments - will be filtered based on selected filters
        pending_payments = student.payment_requests.filter(status='PENDING').order_by('-created_at')
        
        # Apply filters to get final applicable fees
        applicable_fees = base_applicable_fees.order_by('-created_at')  # Most recently posted first
        
        # Apply academic year filter
        if selected_academic_year:
            applicable_fees = applicable_fees.filter(academic_year=selected_academic_year)
        
        # Apply semester filter - when empty string is selected, show ALL semesters
        if selected_semester:  # Only filter if a specific semester is selected
            applicable_fees = applicable_fees.filter(semester=selected_semester)
        
        # Filter pending payments by the same criteria
        filtered_pending_payments = pending_payments
        if selected_academic_year:
            filtered_pending_payments = filtered_pending_payments.filter(fee_type__academic_year=selected_academic_year)
        if selected_semester:  # Only filter if a specific semester is selected
            filtered_pending_payments = filtered_pending_payments.filter(fee_type__semester=selected_semester)
        
       # Calculate statistics based on FILTERED fees
        completed_payments = student.get_completed_payments()

        # IMPORTANT: Filter completed payments to match the DISPLAYED applicable_fees
        # Get the fee IDs that are currently displayed (after all filters applied)
        displayed_fee_ids = list(applicable_fees.values_list('id', flat=True))

        # Only count payments for fees that are CURRENTLY DISPLAYED
        filtered_completed_payments = completed_payments.filter(fee_type_id__in=displayed_fee_ids)
        
        # Now calculate stats from ONLY the displayed fees' payments
        total_paid = filtered_completed_payments.aggregate(Sum('amount'))['amount__sum'] or 0
        payments_count = filtered_completed_payments.count()

        # Get IDs of fees that have been paid (from the filtered set)
        paid_fee_ids = filtered_completed_payments.values_list('fee_type_id', flat=True)

        # Calculate UNPAID fees only (fees in applicable_fees but NOT in paid_fee_ids)
        unpaid_fees = applicable_fees.exclude(id__in=paid_fee_ids)
        remaining_balance = unpaid_fees.aggregate(Sum('amount'))['amount__sum'] or 0

        # Total amount due = sum of all DISPLAYED applicable fees
        total_amount_due = applicable_fees.aggregate(Sum('amount'))['amount__sum'] or 0

        # Calculate pending total strictly from filtered pending requests
        pending_total = filtered_pending_payments.aggregate(Sum('amount'))['amount__sum'] or 0

        # Count pending payment requests (waiting for approval)
        pending_count = filtered_pending_payments.count()
        
        # Build a comprehensive list of all fees with their payment status
        all_fees_with_status = []
        
        for fee in applicable_fees:
            # Check if student has paid this fee (from filtered payments)
            payment = filtered_completed_payments.filter(fee_type=fee).first()
            
            # Check if student has a pending request for this fee
            pending_request = filtered_pending_payments.filter(fee_type=fee).first()
            
            # Expiration disabled: any pending request remains valid
            has_valid_pending = bool(pending_request)
            has_qr_generated = bool(pending_request.qr_signature) if pending_request else False
            
            fee_info = {
                'fee_type': fee,
                'organization': fee.organization,
                'amount': fee.amount,
                'is_paid': payment is not None,
                'payment': payment,
                'has_pending_request': has_valid_pending,
                'pending_request': pending_request,
                'has_qr_generated': has_qr_generated,  # True if student has clicked "Generate QR"
            }
            all_fees_with_status.append(fee_info)
        
        # Get student organizations for filter dropdown (from their applicable fees)
        student_organizations = Organization.objects.filter(
            fee_types__in=student.get_applicable_fees()
        ).distinct().order_by('name')
        
        context.update({
            'student': student,
            'pending_payments': filtered_pending_payments,
            'completed_payments': filtered_completed_payments.order_by('-created_at')[:5],
            'total_amount_due': total_amount_due,
            'total_paid': total_paid,
            'remaining_balance': remaining_balance,
             'pending_total': pending_total,  # expose pending sum for verification
            'payments_count': payments_count,
            'pending_count': pending_count,  # Payments waiting for approval
            'applicable_fees': applicable_fees,
            'all_fees_with_status': all_fees_with_status,
            'student_organizations': student_organizations,
            # Filter context
            'academic_year_choices': academic_year_choices,
            'selected_academic_year': selected_academic_year,
            'selected_semester': selected_semester,
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
        # Expiration disabled
        payment_request.expires_at = timezone.now()
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
        return redirect('view_payment_request_qr', request_id=payment_request.request_id)

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
                # Expiration disabled
                expires_at=timezone.now(),
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
            return redirect('view_payment_request_qr', request_id=payment_request.request_id)
            
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
        
        # Expiration disabled
        
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
        
        # Expiration disabled
        
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
            
        # Expiration disabled
            
        context['payment_request'] = payment_request
        context['qr_data'] = f"PAYMENT_REQUEST|{payment_request.request_id}|{payment_request.qr_signature}"
        return context

# officer views
class OfficerDashboardView(OfficerRequiredMixin, TemplateView):
    template_name = 'paymentorg/officer_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        if user.is_superuser and not hasattr(user, 'officer_profile'):
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
            current_period = get_current_period()
            
            # SPEC: Show pending requests strictly by officer's organization and status
            pending_requests = PaymentRequest.objects.filter(
                organization=organization,
                status='PENDING'
            ).order_by('created_at')[:10]
            
            # Count total pending requests (not just the first 10 displayed)
            # SPEC: Count pending requests strictly by officer's organization and status
            pending_requests_count = PaymentRequest.objects.filter(
                organization=organization,
                status='PENDING'
            ).count()
            
            # Get posted payment postings (bulk fees posted by this officer or organization)
            posted_requests = BulkPaymentPosting.objects.filter(
                organization=organization
            ).order_by('-created_at')[:20]
            
            logger.info(f"Officer Dashboard - Organization: {organization.name}, Posted Requests Count: {posted_requests.count()}, Records: {list(posted_requests.values('fee_type__name', 'amount', 'student_count'))}")
            
            # Get recent payments from all officers in this organization (not just today)
            recent_payments = Payment.objects.filter(
                organization=organization,
                status='COMPLETED',
            ).select_related('student', 'processed_by', 'receipt').order_by('-created_at')[:20]
            
            # Get recent activity logs for this organization
            # Filter by: officers in this org, or payments/requests belonging to this org
            org_officer_user_ids = Officer.objects.filter(
                organization=organization
            ).values_list('user_id', flat=True)
            
            recent_activity_logs = ActivityLog.objects.filter(
                Q(user_id__in=org_officer_user_ids) |
                Q(payment__organization=organization) |
                Q(payment_request__organization=organization)
            ).select_related('user', 'payment', 'payment_request').order_by('-created_at')[:15]
            
            context.update({
                'is_superuser_only': False,
                'officer': officer,
                'organization': organization,
                'pending_requests': pending_requests,
                'pending_requests_count': pending_requests_count,
                'posted_requests': posted_requests,
                'today_collections': organization.get_today_collection(),
                'total_collected_system': organization.get_total_collected(),
                'recent_payments': recent_payments,
                'recent_activity_logs': recent_activity_logs,
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
        
        # Check organization access - officers can only process payments for their organization scope
        # Superusers (admin) can process any payment
        # Super officers can only process payments within their organization hierarchy
        if not user.is_superuser:
            if not hasattr(user, 'officer_profile'):
                messages.error(self.request, "You must be an officer to process payments.")
                return None
            
            officer = user.officer_profile
            # Get accessible organizations (officer's org + child orgs)
            accessible_org_ids = officer.organization.get_accessible_organization_ids()
            
            if payment_request.organization_id not in accessible_org_ids:
                # Provide a clear error message about organization mismatch
                messages.error(
                    self.request, 
                    f"This payment QR is for {payment_request.organization.name}. "
                    f"You can only process payments for {officer.organization.name}"
                    f"{' and its affiliated organizations' if len(accessible_org_ids) > 1 else ''}."
                )
                return None
        
        if payment_request.status != 'PENDING':
            messages.error(self.request, f"This request is already {payment_request.status}. Cannot be processed.")
            return None

        # Expiration disabled
            
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
                from django.conf import settings
                if getattr(settings, 'SENDGRID_API_KEY', ''):
                    if send_receipt_email(receipt, payment.student):
                        messages.info(request, f"✓ Receipt email sent to {payment.student.email}")
                    else:
                        messages.warning(request, f"Failed to send receipt email to {payment.student.email}")
                else:
                    messages.info(request, "Email service not configured - receipt email not sent")
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
            semester = form.cleaned_data['semester']
            academic_year = form.cleaned_data['academic_year']
            applicable_year_level = form.cleaned_data['applicable_year_level']
            payment_deadline = form.cleaned_data.get('payment_deadline')
            
            # create or get fee type
            fee_type, created = FeeType.objects.get_or_create(
                organization=organization,
                name=fee_type_name,
                academic_year=academic_year,
                semester=semester,
                defaults={
                    'amount': fee_amount,
                    'applicable_year_levels': applicable_year_level,
                    'is_active': True,
                }
            )
            
            if not created:
                # update amount and year level if fee type already exists
                fee_type.amount = fee_amount
                fee_type.applicable_year_levels = applicable_year_level
                fee_type.save()
            
            # Select eligible students scoped to the organization level
            # Program-level: only students whose course.program_type matches org.program_affiliation
            # College-level: students from all child program organizations
            students = Student.objects.filter(is_active=True)
            
            if organization.hierarchy_level == 'PROGRAM':
                # For PROGRAM-level orgs:
                # - If program_affiliation == 'ALL': cascade to all child organizations
                # - Otherwise: filter to specific program type
                
                if organization.program_affiliation == 'ALL':
                    # 'ALL' means get students from all child organizations
                    child_orgs = organization.child_organizations.all()
                    
                    eligible_programs = []
                    
                    # Collect all program types from child organizations
                    for child_org in child_orgs:
                        if child_org.program_affiliation and child_org.program_affiliation != 'ALL':
                            program_type = normalize_program_affiliation(child_org.program_affiliation)
                            if program_type:
                                eligible_programs.append(program_type)
                    
                    if eligible_programs:
                        students = students.filter(course__program_type__in=eligible_programs)
                    else:
                        # If no child programs found with specific affiliations, include all students
                        # Keep all students (already filtered by is_active=True above)
                        pass
                        
                elif organization.program_affiliation:
                    # Specific program affiliation
                    program_type = normalize_program_affiliation(organization.program_affiliation)
                    if program_type:
                        students = students.filter(course__program_type=program_type)
                    else:
                        # If program code is unknown, avoid cross-program posting
                        students = students.none()
                else:
                    # If program affiliation is missing, avoid cross-program posting
                    students = students.none()
            
            elif organization.hierarchy_level == 'COLLEGE':
                # For college-level orgs, get students from all child program organizations
                # This includes all students whose programs are children of this college
                child_orgs = organization.child_organizations.all()
                
                from django.db.models import Q
                eligible_programs = []
                
                # Collect all program types from child organizations
                for child_org in child_orgs:
                    if child_org.program_affiliation and child_org.program_affiliation != 'ALL':
                        program_type = normalize_program_affiliation(child_org.program_affiliation)
                        if program_type:
                            eligible_programs.append(program_type)
                
                # Filter students by eligible program types
                if eligible_programs:
                    students = students.filter(course__program_type__in=eligible_programs)
                else:
                    # Fallback: if no child programs found, get by college name
                    students = students.filter(course__college__name=organization.department)
            
            if applicable_year_level != 'All':
                students = students.filter(year_level=applicable_year_level)
            
            students = students.distinct()
            
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
            
            # Determine expiry date - use payment_deadline if provided, otherwise 30 days
            if payment_deadline:
                from datetime import datetime
                expires_at = timezone.make_aware(datetime.combine(payment_deadline, datetime.max.time()))
            else:
                expires_at = timezone.now() + timedelta(days=30)
            
            # create paymentrequest objects for each student
            for student in students:
                try:
                    # create paymentrequest with unique request_id
                    # NOTE: qr_signature is left empty - it will be generated when the student
                    # explicitly clicks "Generate QR" on their dashboard. This ensures the
                    # dashboard first shows "Generate QR" instead of "View QR" after posting.
                    payment_request = PaymentRequest.objects.create(
                        student=student,
                        organization=organization,
                        fee_type=fee_type,
                        amount=fee_amount,
                        payment_method='CASH',  # Default, student will select when generating QR
                        status='PENDING',
                        expires_at=expires_at,
                        qr_signature='',  # Will be generated when student clicks "Generate QR"
                        created_by=request.user,  # Track who posted this bulk payment
                        notes=notes
                    )
                    
                    created_count += 1
                    
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
                f"Payment posted successfully for {fee_type_name}. "
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


class BulkPaymentPostingDetailView(OfficerRequiredMixin, DetailView):
    """View details of a bulk payment posting"""
    model = BulkPaymentPosting
    template_name = 'paymentorg/bulk_posting_detail.html'
    context_object_name = 'posting'
    
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return BulkPaymentPosting.objects.all()
        if hasattr(user, 'officer_profile'):
            return BulkPaymentPosting.objects.filter(organization=user.officer_profile.organization)
        return BulkPaymentPosting.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        posting = self.get_object()
        # Get associated payment requests for this posting (based on fee_type, organization, and date)
        context['payment_requests'] = PaymentRequest.objects.filter(
            fee_type=posting.fee_type,
            organization=posting.organization,
            amount=posting.amount,
            created_at__date=posting.created_at.date()
        ).select_related('student', 'student__user')[:50]
        return context


class BulkPaymentPostingUpdateView(OfficerRequiredMixin, UpdateView):
    """Edit a bulk payment posting"""
    model = BulkPaymentPosting
    template_name = 'paymentorg/bulk_posting_edit.html'
    fields = ['notes']
    
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return BulkPaymentPosting.objects.all()
        if hasattr(user, 'officer_profile'):
            return BulkPaymentPosting.objects.filter(organization=user.officer_profile.organization)
        return BulkPaymentPosting.objects.none()
    
    def get_success_url(self):
        messages.success(self.request, 'Bulk posting updated successfully.')
        return reverse_lazy('officer_dashboard')


class BulkPaymentPostingDeleteView(OfficerRequiredMixin, DeleteView):
    """Delete a bulk payment posting"""
    model = BulkPaymentPosting
    template_name = 'paymentorg/bulk_posting_delete.html'
    success_url = reverse_lazy('officer_dashboard')
    
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return BulkPaymentPosting.objects.all()
        if hasattr(user, 'officer_profile'):
            return BulkPaymentPosting.objects.filter(organization=user.officer_profile.organization)
        return BulkPaymentPosting.objects.none()
    
    def delete(self, request, *args, **kwargs):
        posting = self.get_object()
        messages.success(request, f'Bulk posting for "{posting.fee_type.name}" deleted successfully.')
        return super().delete(request, *args, **kwargs)


class VoidPaymentView(OfficerRequiredMixin, UpdateView):
    model = Payment
    form_class = VoidPaymentForm
    template_name = 'officer_void_payment.html'
    success_url = reverse_lazy('officer_dashboard')

    def test_func(self):
        user = self.request.user
        if user.is_superuser:
            return True
        if hasattr(user, 'officer_profile'):
            return user.officer_profile.can_void_payments or user.officer_profile.is_super_officer
        return False

    def get_form_kwargs(self):
        # Remove 'instance' from kwargs since VoidPaymentForm is a regular Form, not ModelForm
        kwargs = super().get_form_kwargs()
        kwargs.pop('instance', None)
        return kwargs

    def get_object(self):
        user = self.request.user
        
        if user.is_superuser or (hasattr(user, 'officer_profile') and user.officer_profile.is_super_officer):
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
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # If officer also has a student profile, add the student form
        if hasattr(self.request.user, 'student_profile'):
            if self.request.POST:
                context['student_form'] = StudentForm(self.request.POST, instance=self.request.user.student_profile, prefix='student')
            else:
                context['student_form'] = StudentForm(instance=self.request.user.student_profile, prefix='student')
        return context
    
    def form_valid(self, form):
        # Save officer form
        response = super().form_valid(form)
        
        # Also save student form if it exists
        if hasattr(self.request.user, 'student_profile'):
            student_form = StudentForm(self.request.POST, instance=self.request.user.student_profile, prefix='student')
            if student_form.is_valid():
                student_form.save()
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='profile_updated',
            description='Updated officer profile',
            ip_address=self.request.META.get('REMOTE_ADDR')
        )
        messages.success(self.request, 'Profile updated successfully.')
        return response
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        
        # Validate both forms if student profile exists
        student_form_valid = True
        if hasattr(request.user, 'student_profile'):
            student_form = StudentForm(request.POST, instance=request.user.student_profile, prefix='student')
            student_form_valid = student_form.is_valid()
        
        if form.is_valid() and student_form_valid:
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

class PaymentRequestStatusAPI(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        request_id = self.kwargs['request_id']
        try:
            # Check if user has student profile
            if not hasattr(request.user, 'student_profile'):
                return JsonResponse({'status': 'NOT_STUDENT', 'error': 'User is not a student'}, status=403)
            
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
            return JsonResponse({'status': 'NOT_FOUND', 'error': 'Payment request not found'}, status=404)
        except AttributeError as e:
            return JsonResponse({'status': 'ERROR', 'error': str(e)}, status=500)
        except ValueError:
            return JsonResponse({'status': 'INVALID_ID'}, status=400)


class CreateOrganizationView(AllOrgAdminMixin, CreateView):
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
class OrganizationListView(AllOrgAdminMixin, ListView):
    model = Organization
    template_name = 'admin/organization_list.html'
    context_object_name = 'organizations'
    paginate_by = 20
    
    def get_queryset(self):
        return Organization.objects.all().order_by('name')

class OrganizationDetailView(AllOrgAdminMixin, DetailView):
    model = Organization
    template_name = 'admin/organization_detail.html'
    context_object_name = 'organization'

class OrganizationUpdateView(AllOrgAdminMixin, UpdateView):
    model = Organization
    form_class = OrganizationForm
    template_name = 'admin/update_form.html'
    success_url = reverse_lazy('organization_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Update Organization: {self.object.name}"
        return context

class OrganizationDeleteView(AllOrgAdminMixin, DeleteView):
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
class FeeTypeListView(SuperOfficerOrStaffMixin, ListView):
    model = FeeType
    template_name = 'admin/feetype_list.html'
    context_object_name = 'fee_types'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = FeeType.objects.select_related('organization').all()
        
        # Filter by organization scope for super officers
        org = self.get_user_organization()
        if org:
            accessible_org_ids = org.get_accessible_organization_ids()
            queryset = queryset.filter(organization_id__in=accessible_org_ids)
        
        org_filter = self.request.GET.get('organization')
        if org_filter:
            queryset = queryset.filter(organization_id=org_filter)
        return queryset.order_by('organization__name', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        org = self.get_user_organization()
        if org:
            # Super officers only see their accessible organizations
            accessible_org_ids = org.get_accessible_organization_ids()
            context['organizations'] = Organization.objects.filter(id__in=accessible_org_ids, is_active=True)
        else:
            context['organizations'] = Organization.objects.filter(is_active=True)
        context['is_super_officer'] = hasattr(self.request.user, 'officer_profile') and self.request.user.officer_profile.is_super_officer
        if context['is_super_officer']:
            context['organization'] = self.request.user.officer_profile.organization
        return context

class FeeTypeDetailView(SuperOfficerOrStaffMixin, DetailView):
    model = FeeType
    template_name = 'admin/feetype_detail.html'
    context_object_name = 'fee_type'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        org = self.get_user_organization()
        if org:
            accessible_org_ids = org.get_accessible_organization_ids()
            queryset = queryset.filter(organization_id__in=accessible_org_ids)
        return queryset

class FeeTypeUpdateView(SuperOfficerOrStaffMixin, UpdateView):
    model = FeeType
    form_class = FeeTypeForm
    template_name = 'admin/update_form.html'
    success_url = reverse_lazy('feetype_list')
    
    def get_queryset(self):
        queryset = super().get_queryset()
        org = self.get_user_organization()
        if org:
            accessible_org_ids = org.get_accessible_organization_ids()
            queryset = queryset.filter(organization_id__in=accessible_org_ids)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Update Fee Type: {self.object.name}"
        return context

class FeeTypeDeleteView(SuperOfficerOrStaffMixin, DeleteView):
    model = FeeType
    template_name = 'admin/delete_confirm.html'
    success_url = reverse_lazy('feetype_list')
    context_object_name = 'fee_type'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        org = self.get_user_organization()
        if org:
            accessible_org_ids = org.get_accessible_organization_ids()
            queryset = queryset.filter(organization_id__in=accessible_org_ids)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Delete Fee Type"
        context['object_name'] = f"{self.object.organization.code} - {self.object.name}"
        # Show warning about pending payments
        pending_count = PaymentRequest.objects.filter(fee_type=self.object, status='PENDING').count()
        if pending_count > 0:
            context['warning'] = f"Warning: There are {pending_count} pending payment requests for this fee type. They will be cancelled."
        return context
    
    def form_valid(self, form):
        fee_type = self.get_object()
        user = self.request.user
        
        # Log the deletion for transparency
        ActivityLog.objects.create(
            user=user,
            action='fee_type_deleted',
            description=f'Deleted fee type "{fee_type.name}" (₱{fee_type.amount}) from {fee_type.organization.name}. '
                       f'Academic Year: {fee_type.academic_year}, Semester: {fee_type.semester}.',
            ip_address=self.request.META.get('REMOTE_ADDR')
        )
        
        # Cancel any pending payment requests for this fee type
        pending_requests = PaymentRequest.objects.filter(fee_type=fee_type, status='PENDING')
        cancelled_count = pending_requests.count()
        if cancelled_count > 0:
            pending_requests.update(status='CANCELLED')
            ActivityLog.objects.create(
                user=user,
                action='payment_requests_cancelled',
                description=f'Cancelled {cancelled_count} pending payment requests due to fee type deletion: {fee_type.name}.',
                ip_address=self.request.META.get('REMOTE_ADDR')
            )
        
        messages.success(self.request, f'Fee type "{fee_type.name}" has been deleted successfully.')
        if cancelled_count > 0:
            messages.info(self.request, f'{cancelled_count} pending payment requests were cancelled.')
        
        return super().form_valid(form)

# student crud
class StudentListView(SuperOfficerOrStaffMixin, ListView):
    model = Student
    template_name = 'admin/student_list.html'
    context_object_name = 'students'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Student.objects.select_related('user').all()
        
        # Superusers see all students; super officers see only their org's students
        org = self.get_user_organization()
        if org and not self.request.user.is_superuser:
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
        
        # Superusers see all officers; super officers see only their org's officers
        org = self.get_user_organization()
        if org and not self.request.user.is_superuser:
            queryset = queryset.filter(organization=org)
        
        org_filter = self.request.GET.get('organization')
        if org_filter and not org:  # Only allow filtering if staff (not super officer)
            queryset = queryset.filter(organization_id=org_filter)
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search)
            )
        return queryset.order_by('organization__name', 'user__last_name')
    
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
        context['object_name'] = f"{self.object.get_full_name()}"
        return context

# payment request management
class PaymentRequestListView(LoginRequiredMixin, ListView):
    model = PaymentRequest
    template_name = 'admin/paymentrequest_list.html'
    context_object_name = 'payment_requests'
    paginate_by = 30
    
    def get_queryset(self):
        user = self.request.user
        
        # Students see only their own payment requests
        if hasattr(user, 'student_profile'):
            return PaymentRequest.objects.filter(
                student=user.student_profile
            ).select_related('student', 'organization', 'fee_type').order_by('-created_at')
        
        # Officers and admins
        queryset = PaymentRequest.objects.select_related(
            'student', 'organization', 'fee_type'
        ).all()
        
        # Filter by organization if officer
        if hasattr(user, 'officer_profile'):
            org = user.officer_profile.organization
            if org:
                accessible_org_ids = org.get_accessible_organization_ids()
                queryset = queryset.filter(organization_id__in=accessible_org_ids)
        
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        org_filter = self.request.GET.get('organization')
        if org_filter and user.is_staff:  # Only allow filtering if staff
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

class PaymentRequestDetailView(LoginRequiredMixin, DetailView):
    model = PaymentRequest
    template_name = 'admin/paymentrequest_detail.html'
    context_object_name = 'request'
    
    def get_object(self, queryset=None):
        payment_request = super().get_object(queryset)
        user = self.request.user
        
        # Students can only view their own payment requests
        if hasattr(user, 'student_profile'):
            if payment_request.student != user.student_profile:
                raise Http404("Payment request not found")
        # Officers can only view payment requests from their organization
        elif hasattr(user, 'officer_profile'):
            accessible_org_ids = user.officer_profile.organization.get_accessible_organization_ids()
            if payment_request.organization_id not in accessible_org_ids:
                raise Http404("Payment request not found in your organization")
        # Superusers can see all
        elif not user.is_superuser:
            raise Http404("Payment request not found")
        
        return payment_request

# payment management
class PaymentListView(LoginRequiredMixin, ListView):
    model = Payment
    template_name = 'admin/payment_list.html'
    context_object_name = 'payments'
    paginate_by = 30
    
    def get_queryset(self):
        user = self.request.user
        
        # Officers and admins see organization payments (transaction history)
        # Check officer_profile FIRST since officers are also students
        if hasattr(user, 'officer_profile'):
            # Get all accessible organizations (including child orgs)
            accessible_org_ids = user.officer_profile.organization.get_accessible_organization_ids()
            queryset = Payment.objects.select_related(
                'student', 'organization', 'fee_type', 'processed_by'
            ).filter(organization_id__in=accessible_org_ids)
        elif user.is_staff or user.is_superuser:
            # Staff/superuser see all payments
            queryset = Payment.objects.select_related(
                'student', 'organization', 'fee_type', 'processed_by'
            ).all()
        elif hasattr(user, 'student_profile'):
            # Regular students (not officers) see only their own payments
            return Payment.objects.filter(
                student=user.student_profile
            ).select_related('student', 'organization', 'fee_type', 'processed_by').order_by('-created_at')
        else:
            # No profile - return empty
            return Payment.objects.none()
        
        # Apply filters for officers/admins
        status_filter = self.request.GET.get('status')
        if status_filter == 'completed':
            queryset = queryset.filter(is_void=False)
        elif status_filter == 'voided':
            queryset = queryset.filter(is_void=True)
        
        org_filter = self.request.GET.get('organization')
        if org_filter and user.is_staff:  # Only allow filtering if staff
            queryset = queryset.filter(organization_id=org_filter)
        
        academic_year_filter = self.request.GET.get('academic_year')
        if academic_year_filter:
            queryset = queryset.filter(fee_type__academic_year=academic_year_filter)
        
        semester_filter = self.request.GET.get('semester')
        if semester_filter:
            queryset = queryset.filter(fee_type__semester=semester_filter)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['organizations'] = Organization.objects.filter(is_active=True)
        context['status_choices'] = Payment._meta.get_field('status').choices
        context['current_filters'] = {
            'status': self.request.GET.get('status', ''),
            'academic_year': self.request.GET.get('academic_year', ''),
            'semester': self.request.GET.get('semester', ''),
        }
        context['semester_choices'] = [
            ('1st Semester', '1st Semester'),
            ('2nd Semester', '2nd Semester'),
        ]
        # Get distinct academic years from fee types
        context['academic_year_choices'] = FeeType.objects.values_list(
            'academic_year', flat=True
        ).distinct().order_by('-academic_year')
        
        context['is_super_officer'] = hasattr(self.request.user, 'officer_profile') and self.request.user.officer_profile.is_super_officer
        if hasattr(self.request.user, 'officer_profile'):
            context['officer'] = self.request.user.officer_profile
            context['organization'] = self.request.user.officer_profile.organization
        
        # Calculate stats for the stats cards (use get_queryset to get unsliced queryset)
        all_payments = self.get_queryset()
        context['completed_count'] = all_payments.filter(is_void=False).count()
        context['voided_count'] = all_payments.filter(is_void=True).count()
        context['total_amount'] = all_payments.filter(is_void=False).aggregate(total=Sum('amount'))['total'] or 0
        
        return context


class ExportPaymentsView(LoginRequiredMixin, View):
    """Export payments to CSV for officers"""
    
    def get(self, request):
        user = request.user
        
        # Only officers and admins can export
        if not hasattr(user, 'officer_profile') and not user.is_staff:
            return Http404("Not authorized to export payments")
        
        # Build queryset with same filters as PaymentListView
        queryset = Payment.objects.select_related(
            'student', 'organization', 'fee_type', 'processed_by'
        ).all()
        
        # Filter by organization if officer
        if hasattr(user, 'officer_profile'):
            accessible_org_ids = user.officer_profile.organization.get_accessible_organization_ids()
            queryset = queryset.filter(organization_id__in=accessible_org_ids)
        
        # Apply filters
        status_filter = request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        void_filter = request.GET.get('is_void')
        if void_filter == 'true':
            queryset = queryset.filter(is_void=True)
        elif void_filter == 'false':
            queryset = queryset.filter(is_void=False)
        
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        semester_filter = request.GET.get('semester')
        if semester_filter:
            queryset = queryset.filter(fee_type__semester=semester_filter)
        
        queryset = queryset.order_by('-created_at')
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        response['Content-Disposition'] = f'attachment; filename="payments_export_{timestamp}.csv"'
        
        writer = csv.writer(response)
        # Write header
        writer.writerow([
            'OR Number',
            'Date',
            'Student ID',
            'Student Name',
            'Organization',
            'Fee Type',
            'Semester',
            'Academic Year',
            'Amount',
            'Amount Received',
            'Change Given',
            'Status',
            'Is Void',
            'Payment Method',
            'Processed By',
        ])
        
        # Write data rows
        for payment in queryset:
            writer.writerow([
                payment.or_number,
                payment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                payment.student.student_id_number,
                payment.student.get_full_name(),
                payment.organization.name,
                payment.fee_type.name,
                payment.fee_type.semester,
                payment.fee_type.academic_year,
                payment.amount,
                payment.amount_received,
                payment.change_given,
                payment.status,
                'Yes' if payment.is_void else 'No',
                payment.get_payment_method_display() if hasattr(payment, 'get_payment_method_display') else payment.payment_method,
                payment.processed_by.get_full_name() if payment.processed_by else 'N/A',
            ])
        
        return response


class PaymentDetailView(LoginRequiredMixin, DetailView):
    model = Payment
    template_name = 'admin/payment_detail.html'
    context_object_name = 'payment'
    
    def get_object(self, queryset=None):
        payment = super().get_object(queryset)
        user = self.request.user
        
        # Superusers can see all payments
        if user.is_superuser:
            return payment
        
        # Officers can view payments from their organization or accessible orgs
        if hasattr(user, 'officer_profile'):
            officer = user.officer_profile
            # Get accessible organizations (officer's org + child orgs)
            accessible_org_ids = officer.organization.get_accessible_organization_ids()
            # Allow if payment's organization is in officer's accessible orgs
            # This allows fellow officers from the same org to view each other's processed payments
            if payment.organization_id and payment.organization_id in accessible_org_ids:
                return payment
            # Super officers can also see payments in parent org hierarchy
            if officer.is_super_officer:
                return payment
            raise Http404("Payment not found in your organization")
        
        # Students can only view their own payments
        if hasattr(user, 'student_profile'):
            if payment.student == user.student_profile:
                return payment
            raise Http404("Payment not found")
        
        raise Http404("Payment not found")

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
class ReceiptListView(LoginRequiredMixin, ListView):
    model = Receipt
    template_name = 'admin/receipt_list.html'
    context_object_name = 'receipts'
    paginate_by = 30
    
    def get_queryset(self):
        user = self.request.user
        
        # Students see only their own receipts
        if hasattr(user, 'student_profile'):
            return Receipt.objects.filter(
                payment__student=user.student_profile
            ).select_related('payment', 'payment__student', 'payment__organization').order_by('-created_at')
        
        # Officers and admins can see receipts from their organization
        queryset = Receipt.objects.select_related('payment', 'payment__student', 'payment__organization').all()
        
        if hasattr(user, 'officer_profile'):
            org = user.officer_profile.organization
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
        # Superusers and staff can see all receipts
        if user.is_staff or user.is_superuser:
            return Receipt.objects.all()
        # Students can only see their own receipts
        elif hasattr(user, 'student_profile'):
            return Receipt.objects.filter(payment__student=user.student_profile)
        # Officers can see receipts from their org hierarchy
        # This allows fellow officers from the same org to view each other's processed receipts
        elif hasattr(user, 'officer_profile'):
            officer = user.officer_profile
            # Get accessible organizations (officer's org + child orgs)
            accessible_org_ids = officer.organization.get_accessible_organization_ids()
            # Super officers can see all receipts in their org + all from accessible orgs
            if officer.is_super_officer:
                return Receipt.objects.all()
            # Regular officers can see receipts from their org + children
            return Receipt.objects.filter(payment__organization_id__in=accessible_org_ids)
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

class CompleteProfileView(LoginRequiredMixin, View):
    template_name = 'registration/complete_profile.html'
    
    def get(self, request):
        # If student profile already exists, redirect to dashboard
        if hasattr(request.user, 'student_profile'):
            return redirect('student_dashboard')
        
        # If officer profile exists, redirect to officer dashboard
        if hasattr(request.user, 'officer_profile'):
            return redirect('officer_dashboard')
            
        form = CompleteProfileForm()
        
        # Context for dynamic dropdowns (same as StudentRegistrationView)
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
        
        context = {
            'form': form,
            'course_options_json': json.dumps(course_payload),
        }
        return render(request, self.template_name, context)

    @transaction.atomic
    def post(self, request):
        form = CompleteProfileForm(request.POST)
        if form.is_valid():
            student = form.save(commit=False)
            student.user = request.user
            student.first_name = request.user.first_name
            student.last_name = request.user.last_name
            student.email = request.user.email
            
            # Set academic year
            try:
                current_period = AcademicYearConfig.objects.get(is_current=True)
                student.academic_year = current_period.academic_year
                student.semester = current_period.semester
            except Exception:
                student.academic_year = "2024-2025"
                student.semester = "1st Semester"
                
            student.save()
            
            # Create UserProfile
            UserProfile.objects.get_or_create(
                user=request.user,
                defaults={'is_officer': False}
            )
            
            messages.success(request, "Profile completed successfully!")
            return redirect('student_dashboard')
        
        # Re-render with errors
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
        
        context = {
            'form': form,
            'course_options_json': json.dumps(course_payload),
        }
        return render(request, self.template_name, context)


# API endpoints for real-time updates
class CheckNewPaymentsAPI(StudentRequiredMixin, View):
    """Check if new payments have been posted for the student's organizations"""
    
    def get(self, request):
        student = request.user.student_profile
        
        # Get student's applicable fees to determine their organizations
        student_orgs = Organization.objects.filter(
            fee_types__in=student.get_applicable_fees()
        ).distinct()
        
        # Get the last check time from the request (client-side tracking)
        last_check_time_str = request.GET.get('last_check', None)
        
        new_fees = []
        has_new = False
        
        if last_check_time_str:
            try:
                last_check_time = timezone.datetime.fromisoformat(last_check_time_str)
                # Find fees posted since last check
                newly_posted_fees = FeeType.objects.filter(
                    organization__in=student_orgs,
                    created_at__gt=last_check_time
                ).order_by('-created_at')
                
                if newly_posted_fees.exists():
                    has_new = True
                    new_fees = [
                        {
                            'id': fee.id,
                            'name': fee.name,
                            'organization': fee.organization.name,
                            'organization_code': fee.organization.code,
                            'amount': str(fee.amount),
                            'academic_year': str(fee.academic_year),
                            'semester': fee.semester,
                            'posted_at': fee.created_at.isoformat(),
                        }
                        for fee in newly_posted_fees[:5]  # Limit to 5 most recent
                    ]
            except (ValueError, TypeError):
                pass
        
        return JsonResponse({
            'has_new_payments': has_new,
            'new_fees': new_fees,
            'current_time': timezone.now().isoformat(),
            'student_organizations': [org.code for org in student_orgs],
        })