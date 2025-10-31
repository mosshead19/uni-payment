from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.views.generic import View, ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from .models import Student, Officer, Organization, FeeType, PaymentRequest, Payment, Receipt, ActivityLog
import uuid
from django.http import JsonResponse

# home page
class HomePageView(ListView):
    model = Organization
    context_object_name = 'organizations'
    template_name = "home.html"

    def get_queryset(self):
        return Organization.objects.filter(is_active=True)

# show pending payments and available fees
class StudentDashboardView(LoginRequiredMixin, ListView):
    model = PaymentRequest
    context_object_name = 'pending_payments'
    template_name = 'student_dashboard.html'
    
    def get_queryset(self):
        student = get_object_or_404(Student, user=self.request.user)
        return student.payment_requests.filter(status='PENDING')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = get_object_or_404(Student, user=self.request.user)
        
        context['student'] = student
        context['completed_payments'] = Payment.objects.filter(student=student, status='COMPLETED')
        context['available_fees'] = FeeType.objects.filter(
            organization__department=student.college,
            is_active=True
        )
        return context

# show today's payments and pending requests
class OfficerDashboardView(LoginRequiredMixin, ListView):
    model = Payment
    context_object_name = 'today_payments'
    template_name = 'officer_dashboard.html'
    
    def get_queryset(self):
        officer = get_object_or_404(Officer, user=self.request.user)
        today = timezone.now().date()
        return officer.organization.payments.filter(
            created_at__date=today,
            status='COMPLETED'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        officer = get_object_or_404(Officer, user=self.request.user)
        organization = officer.organization
        
        context['officer'] = officer
        context['organization'] = organization
        context['pending_requests'] = organization.payment_requests.filter(status='PENDING')
        context['total_today'] = sum(payment.amount for payment in self.get_queryset())
        return context

# show active fees for an organization
class OrganizationFeesView(ListView):
    model = FeeType
    context_object_name = 'active_fees'
    template_name = 'organization_fees.html'
    
    def get_queryset(self):
        organization = get_object_or_404(Organization, code=self.kwargs['org_code'])
        return organization.fee_types.filter(is_active=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['organization'] = get_object_or_404(Organization, code=self.kwargs['org_code'])
        return context

# show all student payments
class PaymentHistoryView(LoginRequiredMixin, ListView):
    model = Payment
    context_object_name = 'payments'
    template_name = 'payment_history.html'
    
    def get_queryset(self):
        student = get_object_or_404(Student, user=self.request.user)
        return Payment.objects.filter(student=student).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['student'] = get_object_or_404(Student, user=self.request.user)
        return context

# payment detail view
class PaymentDetailView(LoginRequiredMixin, DetailView):
    model = Payment
    context_object_name = 'payment'
    template_name = 'payment_detail.html'
    
    def get_queryset(self):
        if hasattr(self.request.user, 'student_profile'):
            student = self.request.user.student_profile
            return Payment.objects.filter(student=student)
        elif hasattr(self.request.user, 'officer_profile'):
            officer = self.request.user.officer_profile
            return Payment.objects.filter(organization=officer.organization)
        return Payment.objects.none()

# filter payments by query and date
class SearchPaymentsView(LoginRequiredMixin, ListView):
    model = Payment
    context_object_name = 'payments'
    template_name = 'search_payments.html'
    
    def get_queryset(self):
        officer = get_object_or_404(Officer, user=self.request.user)
        organization = officer.organization
        
        payments = organization.payments.filter(status='COMPLETED')
        
        query = self.request.GET.get('q', '')
        if query:
            payments = payments.filter(
                Q(or_number__icontains=query) |
                Q(student__student_id_number__icontains=query) |
                Q(student__first_name__icontains=query) |
                Q(student__last_name__icontains=query)
            )
        
        date_from = self.request.GET.get('date_from', '')
        if date_from:
            payments = payments.filter(created_at__date__gte=date_from)
        
        date_to = self.request.GET.get('date_to', '')
        if date_to:
            payments = payments.filter(created_at__date__lte=date_to)
        
        return payments.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        officer = get_object_or_404(Officer, user=self.request.user)
        context['officer'] = officer
        context['organization'] = officer.organization
        context['query'] = self.request.GET.get('q', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        return context

# generate QR code for payment
class GenerateQRPaymentView(LoginRequiredMixin, CreateView):
    model = PaymentRequest
    fields = []  # We'll handle creation manually
    template_name = 'generate_qr.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = get_object_or_404(Student, user=self.request.user)
        context['available_fees'] = FeeType.objects.filter(
            organization__department=student.college,
            is_active=True
        )
        return context
    
    def post(self, request, *args, **kwargs):
        try:
            student = Student.objects.get(user=request.user)
            fee_type_id = request.POST.get('fee_type')
            fee_type = get_object_or_404(FeeType, id=fee_type_id)
            
            # generate unique queue number
            queue_number = f"{fee_type.organization.code}-{student.id:03d}"
            
            # create payment request
            payment_request = PaymentRequest.objects.create(
                student=student,
                organization=fee_type.organization,
                fee_type=fee_type,
                amount=fee_type.amount,
                queue_number=queue_number,
                qr_signature=str(uuid.uuid4()),
                expires_at=timezone.now() + timezone.timedelta(hours=24)
            )
            
            # log activity
            ActivityLog.objects.create(
                user=request.user,
                action='QR_GENERATED',
                description=f'Student {student.get_full_name()} generated QR for {fee_type.name}',
                payment_request=payment_request
            )
            
            messages.success(request, f'QR code generated for {fee_type.name}. Queue number: {queue_number}')
            return redirect('student_dashboard')
            
        except Student.DoesNotExist:
            messages.error(request, 'Student profile not found.')
            return redirect('home')

# create payment record and receipt (CREATE Payment & Receipt)
class ProcessPaymentView(LoginRequiredMixin, CreateView):
    model = Payment
    fields = ['amount_received']
    template_name = 'process_payment.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        officer = get_object_or_404(Officer, user=self.request.user)
        payment_request = get_object_or_404(
            PaymentRequest, 
            request_id=self.kwargs['request_id'],
            status='PENDING'
        )
        context['officer'] = officer
        context['payment_request'] = payment_request
        return context
    
    def form_valid(self, form):
        officer = get_object_or_404(Officer, user=self.request.user)
        payment_request = get_object_or_404(
            PaymentRequest, 
            request_id=self.kwargs['request_id'],
            status='PENDING'
        )
        
        # create payment record
        payment = Payment.objects.create(
            payment_request=payment_request,
            student=payment_request.student,
            organization=payment_request.organization,
            fee_type=payment_request.fee_type,
            amount=payment_request.amount,
            amount_received=form.cleaned_data['amount_received'],
            or_number=f"OR-{uuid.uuid4().hex[:8].upper()}",
            payment_method='CASH',
            processed_by=officer
        )
        
        # update payment request status
        payment_request.mark_as_paid()
        
        # create receipt
        Receipt.objects.create(
            payment=payment,
            or_number=payment.or_number,
            verification_signature=str(uuid.uuid4())
        )
        
        # log activity
        ActivityLog.objects.create(
            user=self.request.user,
            action='PAYMENT_PROCESSED',
            description=f'Officer processed payment OR#{payment.or_number} for {payment.student.get_full_name()}',
            payment=payment,
            payment_request=payment_request
        )
        
        messages.success(self.request, f'Payment processed successfully. OR#: {payment.or_number}')
        return redirect('officer_dashboard')

# UPDATE PaymentRequest status
class CancelPaymentRequestView(LoginRequiredMixin, UpdateView):
    model = PaymentRequest
    fields = ['status']
    template_name = 'cancel_request.html'
    
    def get_object(self):
        student = get_object_or_404(Student, user=self.request.user)
        return get_object_or_404(
            PaymentRequest, 
            request_id=self.kwargs['request_id'], 
            student=student,
            status='PENDING'
        )
    
    def form_valid(self, form):
        payment_request = form.save(commit=False)
        payment_request.mark_as_cancelled()
        
        # log activity
        ActivityLog.objects.create(
            user=self.request.user,
            action='PAYMENT_CANCELLED',
            description=f'Student cancelled payment request {payment_request.queue_number}',
            payment_request=payment_request
        )
        
        messages.success(self.request, 'Payment request cancelled successfully.')
        return redirect('student_dashboard')

# mark payment as void with reason (UPDATE Payment status)
class VoidPaymentView(LoginRequiredMixin, UpdateView):
    model = Payment
    fields = ['void_reason']
    template_name = 'void_payment.html'
    
    def get_object(self):
        officer = get_object_or_404(Officer, user=self.request.user)
        
        if not officer.can_void_payments:
            messages.error(self.request, 'You do not have permission to void payments.')
            return redirect('officer_dashboard')
            
        return get_object_or_404(
            Payment,
            id=self.kwargs['payment_id'],
            organization=officer.organization,
            status='COMPLETED'
        )
    
    def form_valid(self, form):
        officer = get_object_or_404(Officer, user=self.request.user)
        payment = form.save(commit=False)
        
        # update payment status
        payment.mark_as_void(officer, form.cleaned_data['void_reason'])
        
        # log activity
        ActivityLog.objects.create(
            user=self.request.user,
            action='PAYMENT_VOIDED',
            description=f'Officer voided payment OR#{payment.or_number}. Reason: {form.cleaned_data["void_reason"]}',
            payment=payment
        )
        
        messages.success(self.request, f'Payment OR#{payment.or_number} has been voided.')
        return redirect('officer_dashboard')

# edit contact information (UPDATE Student)
class UpdateStudentProfileView(LoginRequiredMixin, UpdateView):
    model = Student
    fields = ['phone_number', 'email']
    template_name = 'update_profile.html'
    success_url = reverse_lazy('student_dashboard')
    
    def get_object(self):
        return get_object_or_404(Student, user=self.request.user)
    
    def form_valid(self, form):
        # log activity
        ActivityLog.objects.create(
            user=self.request.user,
            action='PROFILE_UPDATED',
            description='Student updated their profile information'
        )
        
        messages.success(self.request, 'Profile updated successfully.')
        return super().form_valid(form)

# delete payment request
class DeletePaymentRequestView(LoginRequiredMixin, DeleteView):
    model = PaymentRequest
    template_name = 'delete_request.html'
    success_url = reverse_lazy('student_dashboard')
    
    def get_object(self):
        student = get_object_or_404(Student, user=self.request.user)
        return get_object_or_404(
            PaymentRequest, 
            request_id=self.kwargs['request_id'], 
            student=student,
            status='PENDING'
        )
    
    def delete(self, request, *args, **kwargs):
        payment_request = self.get_object()
        
        # log activity before deletion
        ActivityLog.objects.create(
            user=request.user,
            action='PAYMENT_REQUEST_DELETED',
            description=f'Student deleted payment request {payment_request.queue_number}',
            payment_request=payment_request
        )
        
        messages.success(request, 'Payment request deleted successfully.')
        return super().delete(request, *args, **kwargs)

 #  return JSON data for student payments status
class PaymentStatusAPIView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        try:
            student = Student.objects.get(user=request.user)
            pending_count = student.get_pending_payments_count()
            recent_payments = student.get_completed_payments()[:5]
            
            data = {
                'pending_count': pending_count,
                'recent_payments': [
                    {
                        'or_number': payment.or_number,
                        'organization': payment.organization.name,
                        'amount': float(payment.amount),
                        'date': payment.created_at.isoformat()
                    }
                    for payment in recent_payments
                ]
            }
            return JsonResponse(data)
        except Student.DoesNotExist:
            return JsonResponse({'error': 'Student profile not found'}, status=404)