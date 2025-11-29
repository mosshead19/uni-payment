from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def get_receipt_html_template(receipt, student):
    """Generate beautiful HTML email template for receipt"""
    payment = receipt.payment
    
    return f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Receipt</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f3f4f6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f3f4f6;">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="max-width: 500px; margin: 0 auto;">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #059669 0%, #14b8a6 50%, #f97316 100%); padding: 30px 40px; border-radius: 16px 16px 0 0; text-align: center;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 700;">OFFICIAL RECEIPT</h1>
                            <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-size: 14px;">UniPay Payment System</p>
                        </td>
                    </tr>
                    
                    <!-- Body -->
                    <tr>
                        <td style="background-color: #ffffff; padding: 40px; border-radius: 0 0 16px 16px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                            <!-- OR Number -->
                            <div style="text-align: center; padding-bottom: 24px; border-bottom: 1px solid #e5e7eb;">
                                <p style="color: #6b7280; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 8px 0;">Official Receipt Number</p>
                                <p style="color: #111827; font-size: 28px; font-weight: 700; font-family: 'Courier New', monospace; margin: 0;">{receipt.or_number}</p>
                                <p style="color: #6b7280; font-size: 14px; margin: 12px 0 0 0;">
                                    {receipt.created_at.strftime('%B %d, %Y')} • {receipt.created_at.strftime('%I:%M %p')}
                                </p>
                            </div>
                            
                            <!-- Amount -->
                            <div style="text-align: center; padding: 24px 0; border-bottom: 1px solid #e5e7eb;">
                                <p style="color: #6b7280; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 8px 0;">Amount Paid</p>
                                <p style="color: #059669; font-size: 36px; font-weight: 700; margin: 0;">₱{payment.amount:,.2f}</p>
                                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-top: 16px;">
                                    <tr>
                                        <td style="text-align: center; padding: 0 8px;">
                                            <span style="color: #6b7280; font-size: 13px;">Received: </span>
                                            <span style="color: #111827; font-weight: 600;">₱{payment.amount_received:,.2f}</span>
                                        </td>
                                        <td style="text-align: center; padding: 0 8px;">
                                            <span style="color: #6b7280; font-size: 13px;">Change: </span>
                                            <span style="color: #111827; font-weight: 600;">₱{payment.change_given:,.2f}</span>
                                        </td>
                                    </tr>
                                </table>
                            </div>
                            
                            <!-- Details -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-top: 24px;">
                                <tr>
                                    <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6;">
                                        <span style="color: #6b7280; font-size: 12px; text-transform: uppercase;">Student</span>
                                    </td>
                                    <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; text-align: right;">
                                        <span style="color: #111827; font-weight: 500;">{student.get_full_name()}</span><br>
                                        <span style="color: #6b7280; font-size: 13px;">{student.student_id_number}</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6;">
                                        <span style="color: #6b7280; font-size: 12px; text-transform: uppercase;">Organization</span>
                                    </td>
                                    <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; text-align: right;">
                                        <span style="color: #111827; font-weight: 500;">{payment.organization.name}</span><br>
                                        <span style="color: #6b7280; font-size: 13px;">{payment.organization.code}</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6;">
                                        <span style="color: #6b7280; font-size: 12px; text-transform: uppercase;">Fee Type</span>
                                    </td>
                                    <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; text-align: right;">
                                        <span style="color: #111827; font-weight: 500;">{payment.fee_type.name}</span><br>
                                        <span style="color: #6b7280; font-size: 13px;">{payment.fee_type.semester} • {payment.fee_type.academic_year}</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6;">
                                        <span style="color: #6b7280; font-size: 12px; text-transform: uppercase;">Payment Method</span>
                                    </td>
                                    <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; text-align: right;">
                                        <span style="color: #111827; font-weight: 500;">{payment.get_payment_method_display()}</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6;">
                                        <span style="color: #6b7280; font-size: 12px; text-transform: uppercase;">Processed By</span>
                                    </td>
                                    <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; text-align: right;">
                                        <span style="color: #111827; font-weight: 500;">{payment.processed_by.get_full_name() if payment.processed_by else 'System'}</span><br>
                                        <span style="color: #6b7280; font-size: 13px;">{payment.processed_by.officer_profile.role if payment.processed_by and hasattr(payment.processed_by, 'officer_profile') else ''}</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 12px 0;">
                                        <span style="color: #6b7280; font-size: 12px; text-transform: uppercase;">Status</span>
                                    </td>
                                    <td style="padding: 12px 0; text-align: right;">
                                        <span style="background-color: #d1fae5; color: #059669; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600;">COMPLETED</span>
                                    </td>
                                </tr>
                            </table>
                            
                            <!-- Footer Message -->
                            <div style="margin-top: 32px; padding-top: 24px; border-top: 1px solid #e5e7eb; text-align: center;">
                                <p style="color: #059669; font-size: 14px; font-weight: 500; margin: 0 0 8px 0;">✓ Payment Verified</p>
                                <p style="color: #6b7280; font-size: 13px; margin: 0;">Thank you for your payment!</p>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 40px; text-align: center;">
                            <p style="color: #9ca3af; font-size: 12px; margin: 0 0 8px 0;">This is an automated message from UniPay Payment System</p>
                            <p style="color: #9ca3af; font-size: 12px; margin: 0;">Please keep this receipt for your records</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
'''


def send_receipt_email(receipt, student):
    """Send receipt email to student using SendGrid or Django's email backend"""
    try:
        subject = f'Payment Receipt - OR#{receipt.or_number}'
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'UniPay System <noreply@unipay.com>')
        
        # Use student's email field directly
        to_email = student.email
        
        logger.info(f'Attempting to send receipt email to {to_email} for OR#{receipt.or_number}')
        logger.info(f'Email backend: {settings.EMAIL_BACKEND}')
        logger.info(f'From email: {from_email}')
        
        # Plain text version
        payment = receipt.payment
        officer_name = payment.processed_by.get_full_name() if payment.processed_by else 'System'
        officer_role = payment.processed_by.officer_profile.role if payment.processed_by and hasattr(payment.processed_by, 'officer_profile') else ''
        
        text_content = f'''
Dear {student.get_full_name()},

Thank you for your payment!

Receipt Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Official Receipt Number: {receipt.or_number}
Payment Date: {receipt.created_at.strftime('%B %d, %Y at %I:%M %p')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Amount Paid: ₱{payment.amount:,.2f}
Amount Received: ₱{payment.amount_received:,.2f}
Change: ₱{payment.change_given:,.2f}

Details:
- Student: {student.get_full_name()} ({student.student_id_number})
- Organization: {payment.organization.name} ({payment.organization.code})
- Fee Type: {payment.fee_type.name}
- Semester: {payment.fee_type.semester} • {payment.fee_type.academic_year}
- Payment Method: {payment.get_payment_method_display()}
- Processed By: {officer_name}{f' ({officer_role})' if officer_role else ''}
- Status: COMPLETED

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This is an automated message from UniPay Payment System.
Please keep this receipt for your records.
'''.strip()
        
        # HTML version
        html_content = get_receipt_html_template(receipt, student)
        
        # Create email with both plain text and HTML versions
        msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        
        # Mark email as sent
        receipt.email_sent = True
        receipt.email_sent_at = timezone.now()
        receipt.save(update_fields=['email_sent', 'email_sent_at'])
        
        logger.info(f'Receipt email sent to {to_email} for OR#{receipt.or_number}')
        return True
        
    except Exception as e:
        logger.error(f'Email send error: {str(e)}')
        return False



