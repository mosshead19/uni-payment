from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
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
    Course, College, UserProfile
)
from .forms import (
    StudentPaymentRequestForm, OfficerPaymentProcessForm, OrganizationForm, 
    FeeTypeForm, StudentForm, OfficerForm, VoidPaymentForm,
    StudentRegistrationForm, OfficerRegistrationForm, AcademicYearConfigForm,
    BulkPaymentPostForm
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

# mixins
class StudentRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return hasattr(self.request.user, 'student_profile')
    
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
        student = self.request.user.student_profile
        
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
        payment_request.qr_signature = create_signature(payment_request.request_id)
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
            payment_request.qr_signature = create_signature(payment_request.request_id)
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
            payment_request.qr_signature = create_signature(payment_request.request_id)
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
    template_name = 'officer_dashboard.html'
    
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
            
            context.update({
                'is_superuser_only': False,
                'officer': officer,
                'organization': organization,
                'pending_requests': pending_requests,
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

        message_string = f"PAYMENT_REQUEST|{payment_request.request_id}"
        if not validate_signature(message_string, signature):
            messages.error(self.request, "QR Code signature failed verification.")
            return None
            
        user = self.request.user
        
        if not user.is_superuser:
            officer = user.officer_profile
            if payment_request.organization != officer.organization:
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
            
            # get all students belonging to this organization by matching course/college
            students = Student.objects.filter(
                Q(course__code__iexact=organization.code) |
                Q(course__name__iexact=organization.name) |
                Q(college__name__iexact=organization.department) |
                Q(college__code__iexact=organization.code)
            ).filter(
                academic_year=academic_year,
                semester=semester
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
            
            if not students.exists():
                messages.warning(request, "No eligible students found in your organization for this fee type.")
                context = {'form': form, 'organization': organization}
                return render(request, self.template_name, context)
            
            created_count = 0
            failed_count = 0
            
            # create paymentrequest objects for each student
            for student in students:
                try:
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
                        notes=notes
                    )
                    
                    # generate qr signature for the request_id
                    payment_request.qr_signature = create_signature(payment_request.request_id)
                    payment_request.save(update_fields=['qr_signature'])
                    
                    created_count += 1
                    
                except Exception as e:
                    logger.error(f'Error creating payment request for {student.student_id_number}: {str(e)}')
                    failed_count += 1
                    continue
            
            ActivityLog.objects.create(
                user=request.user,
                action='bulk_payment_posted',
                description=f'Posted bulk payment request for {fee_type_name} to {created_count} students in {organization.name}.',
                ip_address=request.META.get('REMOTE_ADDR')
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
            payment = get_object_or_404(
                Payment, 
                pk=self.kwargs['pk'],
                organization=user.officer_profile.organization
            )
            
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
class StudentListView(StaffRequiredMixin, ListView):
    model = Student
    template_name = 'admin/student_list.html'
    context_object_name = 'students'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Student.objects.select_related('user').all()
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
        return context

class StudentDetailView(StaffRequiredMixin, DetailView):
    model = Student
    template_name = 'admin/student_detail.html'
    context_object_name = 'student'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.object
        context['pending_payments'] = student.get_pending_payments()
        context['completed_payments'] = student.get_completed_payments()[:10]
        return context

class StudentUpdateView(StaffRequiredMixin, UpdateView):
    model = Student
    form_class = StudentForm
    template_name = 'admin/update_form.html'
    success_url = reverse_lazy('student_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Update Student: {self.object.get_full_name()}"
        return context

class StudentDeleteView(StaffRequiredMixin, DeleteView):
    model = Student
    template_name = 'admin/delete_confirm.html'
    success_url = reverse_lazy('student_list')
    context_object_name = 'student'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Delete Student"
        context['object_name'] = f"{self.object.student_id_number} - {self.object.get_full_name()}"
        return context

# officer crud
class OfficerListView(StaffRequiredMixin, ListView):
    model = Officer
    template_name = 'admin/officer_list.html'
    context_object_name = 'officers'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Officer.objects.select_related('user', 'organization').all()
        org_filter = self.request.GET.get('organization')
        if org_filter:
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
        return context

class OfficerDetailView(StaffRequiredMixin, DetailView):
    model = Officer
    template_name = 'admin/officer_detail.html'
    context_object_name = 'officer'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        officer = self.object
        context['processed_payments'] = officer.processed_payments.filter(is_void=False).order_by('-created_at')[:10]
        context['voided_payments'] = officer.voided_payments.all().order_by('-voided_at')[:10]
        return context

class OfficerUpdateView(StaffRequiredMixin, UpdateView):
    model = Officer
    form_class = OfficerForm
    template_name = 'admin/update_form.html'
    success_url = reverse_lazy('officer_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Update Officer: {self.object.get_full_name()}"
        return context

class OfficerDeleteView(StaffRequiredMixin, DeleteView):
    model = Officer
    template_name = 'admin/delete_confirm.html'
    success_url = reverse_lazy('officer_list')
    context_object_name = 'officer'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Delete Officer"
        context['object_name'] = f"{self.object.employee_id} - {self.object.get_full_name()}"
        return context

# payment request management
class PaymentRequestListView(StaffRequiredMixin, ListView):
    model = PaymentRequest
    template_name = 'admin/paymentrequest_list.html'
    context_object_name = 'payment_requests'
    paginate_by = 30
    
    def get_queryset(self):
        queryset = PaymentRequest.objects.select_related(
            'student', 'organization', 'fee_type'
        ).all()
        
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        org_filter = self.request.GET.get('organization')
        if org_filter:
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
        return context

class PaymentRequestDetailView(StaffRequiredMixin, DetailView):
    model = PaymentRequest
    template_name = 'admin/paymentrequest_detail.html'
    context_object_name = 'request'

# payment management
class PaymentListView(StaffRequiredMixin, ListView):
    model = Payment
    template_name = 'admin/payment_list.html'
    context_object_name = 'payments'
    paginate_by = 30
    
    def get_queryset(self):
        queryset = Payment.objects.select_related(
            'student', 'organization', 'fee_type', 'processed_by'
        ).all()
        
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        void_filter = self.request.GET.get('is_void')
        if void_filter == 'true':
            queryset = queryset.filter(is_void=True)
        elif void_filter == 'false':
            queryset = queryset.filter(is_void=False)
        
        org_filter = self.request.GET.get('organization')
        if org_filter:
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
        return context

class PaymentDetailView(StaffRequiredMixin, DetailView):
    model = Payment
    template_name = 'admin/payment_detail.html'
    context_object_name = 'payment'

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
class ReceiptListView(StaffRequiredMixin, ListView):
    model = Receipt
    template_name = 'admin/receipt_list.html'
    context_object_name = 'receipts'
    paginate_by = 30
    
    def get_queryset(self):
        queryset = Receipt.objects.select_related('payment', 'payment__student', 'payment__organization').all()
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