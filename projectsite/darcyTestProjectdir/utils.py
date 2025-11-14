from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

def send_receipt_email(receipt, student):
    # send receipt email to the student
    try:
        subject = f'Payment Receipt - OR#{receipt.or_number}'
        
        # create email body
        message = f"""
Dear {student.get_full_name()},

Thank you for your payment!

Receipt Details:
- Official Receipt Number: {receipt.or_number}
- Payment Date: {receipt.created_at.strftime('%B %d, %Y at %I:%M %p')}
- Fee: {receipt.payment.fee_type.name}
- Organization: {receipt.payment.organization.name}
- Amount Paid: ₱{receipt.payment.amount:.2f}
- Amount Received: ₱{receipt.payment.amount_received:.2f}
- Change: ₱{receipt.payment.change_given:.2f}
- Payment Method: {receipt.payment.get_payment_method_display()}

This is an automated message from UniPay Payment System.

Best regards,
{receipt.payment.organization.name}
        """.strip()
        
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@unipay.com')
        
        send_mail(
            subject,
            message,
            from_email,
            [student.email],
            fail_silently=False,
        )
        
        # mark email as sent
        receipt.email_sent = True
        receipt.email_sent_at = timezone.now()
        receipt.save(update_fields=['email_sent', 'email_sent_at'])
        
        logger.info(f'Receipt email sent to {student.email} for OR#{receipt.or_number}')
        return True
        
    except Exception as e:
        logger.error(f'Email send error: {str(e)}')
        return False



