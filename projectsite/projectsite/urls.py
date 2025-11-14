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
from django.urls import path, include
from django.contrib import admin
from django.contrib.auth import views as auth_views
from paymentorg import views
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

# initial urlpatterns list

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', views.HomePageView.as_view(), name='home'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    
    path(
        'logout/', 
        auth_views.LogoutView.as_view(template_name='registration/logged_out.html'), 
        name='logout'
    ),
    
    path('register/', views.SelectProfileView.as_view(), name='select_profile'),
    path('register/student/', views.StudentRegistrationView.as_view(), name='student_register'),
    path('register/officer/', views.OfficerRegistrationView.as_view(), name='officer_register'),

    path('student/dashboard/', views.StudentDashboardView.as_view(), name='student_dashboard'),
    path('student/profile/update/', views.UpdateStudentProfileView.as_view(), name='student_profile_update'),
    path('student/payment-history/', views.PaymentHistoryView.as_view(), name='payment_history'),
    
    path('student/request/generate/', views.GenerateQRPaymentView.as_view(), name='generate_qr'),
    path('student/request/<uuid:request_id>/', views.PaymentRequestDetailView.as_view(), name='payment_request_detail'),
    path('student/request/<uuid:request_id>/view-qr/', views.ViewPaymentRequestQRView.as_view(), name='view_payment_request_qr'),
    path('student/request/<uuid:request_id>/qr/', views.ShowPaymentQRView.as_view(), name='show_payment_qr'),
    path('api/request/<uuid:request_id>/status/', views.PaymentRequestStatusAPI.as_view(), name='api_request_status'),

    path('officer/dashboard/', views.OfficerDashboardView.as_view(), name='officer_dashboard'),
    path('officer/profile/update/', views.UpdateOfficerProfileView.as_view(), name='officer_profile_update'),
    
    path(
        'officer/process/<uuid:request_id>/<str:signature>/', 
        views.ProcessPaymentRequestView.as_view(), 
        name='officer_process_payment'
    ),
    path('officer/scan-qr/', views.OfficerScanQRView.as_view(), name='officer_scan_qr'),
    path('officer/post-bulk-payment/', views.PostBulkPaymentView.as_view(), name='officer_post_bulk_payment'),
    path('officer/void/<int:pk>/', views.VoidPaymentView.as_view(), name='officer_void_payment'),
    
    # Staff/Admin CRUD Routes
    path('staff/organization/create/', views.CreateOrganizationView.as_view(), name='create_organization'),
    path('staff/organization/', views.OrganizationListView.as_view(), name='organization_list'),
    path('staff/organization/<int:pk>/', views.OrganizationDetailView.as_view(), name='organization_detail'),
    path('staff/organization/<int:pk>/update/', views.OrganizationUpdateView.as_view(), name='organization_update'),
    path('staff/organization/<int:pk>/delete/', views.OrganizationDeleteView.as_view(), name='organization_delete'),
    
    path('staff/feetypes/create/', views.CreateFeeTypeView.as_view(), name='create_fee_type'),
    path('staff/feetypes/', views.FeeTypeListView.as_view(), name='feetype_list'),
    path('staff/feetypes/<int:pk>/', views.FeeTypeDetailView.as_view(), name='feetype_detail'),
    path('staff/feetypes/<int:pk>/update/', views.FeeTypeUpdateView.as_view(), name='feetype_update'),
    path('staff/feetypes/<int:pk>/delete/', views.FeeTypeDeleteView.as_view(), name='feetype_delete'),
    
    path('staff/students/', views.StudentListView.as_view(), name='student_list'),
    path('staff/students/<int:pk>/', views.StudentDetailView.as_view(), name='student_detail'),
    path('staff/students/<int:pk>/update/', views.StudentUpdateView.as_view(), name='student_update'),
    path('staff/students/<int:pk>/delete/', views.StudentDeleteView.as_view(), name='student_delete'),
    
    path('staff/officers/', views.OfficerListView.as_view(), name='officer_list'),
    path('staff/officers/<int:pk>/', views.OfficerDetailView.as_view(), name='officer_detail'),
    path('staff/officers/<int:pk>/update/', views.OfficerUpdateView.as_view(), name='officer_update'),
    path('staff/officers/<int:pk>/delete/', views.OfficerDeleteView.as_view(), name='officer_delete'),
    
    path('staff/payment-requests/', views.PaymentRequestListView.as_view(), name='paymentrequest_list'),
    path('staff/payment-requests/<uuid:pk>/', views.PaymentRequestDetailView.as_view(), name='paymentrequest_detail'),
    
    path('staff/payments/', views.PaymentListView.as_view(), name='payment_list'),
    path('staff/payments/<int:pk>/', views.PaymentDetailView.as_view(), name='payment_detail'),
    
    path('staff/receipts/', views.ReceiptListView.as_view(), name='receipt_list'),
    path('staff/receipts/<int:pk>/', views.ReceiptDetailView.as_view(), name='receipt_detail'),
    
    path('staff/academic-years/', views.AcademicYearConfigListView.as_view(), name='academicyear_list'),
    path('staff/academic-years/create/', views.AcademicYearConfigCreateView.as_view(), name='academicyear_create'),
    path('staff/academic-years/<int:pk>/update/', views.AcademicYearConfigUpdateView.as_view(), name='academicyear_update'),
    path('staff/academic-years/<int:pk>/delete/', views.AcademicYearConfigDeleteView.as_view(), name='academicyear_delete'),
    
    path('staff/activity-logs/', views.ActivityLogListView.as_view(), name='activitylog_list'),
    path('staff/org/<str:code>/dashboard/', views.AdminOrganizationDashboardView.as_view(), name='admin_org_dashboard'),
]