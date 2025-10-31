"""
URL configuration for projectsite project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from paymentorg import views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # home and dashboard routes
    path('', views.HomePageView.as_view(), name='home'),
    path('student/dashboard/', views.StudentDashboardView.as_view(), name='student_dashboard'),
    path('officer/dashboard/', views.OfficerDashboardView.as_view(), name='officer_dashboard'),
    
    # organization routes
    path('organization/<str:org_code>/fees/', views.OrganizationFeesView.as_view(), name='organization_fees'),
    
    # payment routes
    path('payment/history/', views.PaymentHistoryView.as_view(), name='payment_history'),
    path('payment/<int:pk>/', views.PaymentDetailView.as_view(), name='payment_detail'),
    path('payment/search/', views.SearchPaymentsView.as_view(), name='search_payments'),
    
    # QR code and payment Processing
    path('payment/generate-qr/', views.GenerateQRPaymentView.as_view(), name='generate_qr'),
    path('payment/process/<uuid:request_id>/', views.ProcessPaymentView.as_view(), name='process_payment'),
    
    # payment Management
    path('payment/cancel/<uuid:request_id>/', views.CancelPaymentRequestView.as_view(), name='cancel_payment_request'),
    path('payment/void/<int:payment_id>/', views.VoidPaymentView.as_view(), name='void_payment'),
    path('payment/delete/<uuid:request_id>/', views.DeletePaymentRequestView.as_view(), name='delete_payment_request'),
    
    # profile Management
    path('student/profile/update/', views.UpdateStudentProfileView.as_view(), name='update_student_profile'),
    
    # API routes
    path('api/payment-status/', views.PaymentStatusAPIView.as_view(), name='payment_status_api'),
]
