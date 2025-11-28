import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'projectsite.settings'
import django
django.setup()

from paymentorg.models import Receipt
from paymentorg.utils import send_receipt_email
from django.core.mail import send_mail
from django.conf import settings

# Check specific receipt
or_number = 'OR-2ED05CABC190'
r = Receipt.objects.filter(or_number=or_number).first()

if not r:
    print(f'Receipt {or_number} not found!')
    r = Receipt.objects.order_by('-created_at').first()
    print(f'Using latest receipt instead: {r.or_number}')

print('='*50)
print('Receipt:', r.or_number)
print('Created:', r.created_at)
print('Student:', r.payment.student.get_full_name())
print('Student Email (from student model):', r.payment.student.email)
print('Student Email (from user model):', r.payment.student.user.email)
print('Email sent:', r.email_sent)
print('Email sent at:', r.email_sent_at)
print('='*50)

print(f'\nSendGrid configured: {bool(settings.SENDGRID_API_KEY)}')
print(f'Email backend: {settings.EMAIL_BACKEND}')
print(f'From email: {settings.DEFAULT_FROM_EMAIL}')

# Resend email using the full HTML template
print(f'\nResending receipt email to: {r.payment.student.email}')
try:
    result = send_receipt_email(r, r.payment.student)
    print(f'Send result: {result}')
    
    # Reload from DB
    r.refresh_from_db()
    print(f'Email sent flag now: {r.email_sent}')
    print(f'Email sent at: {r.email_sent_at}')
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
