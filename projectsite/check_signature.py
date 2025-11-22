#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'projectsite.settings')
django.setup()

from paymentorg.models import PaymentRequest
from paymentorg.views import create_signature

# Get the first payment request
pr = PaymentRequest.objects.first()
if pr:
    print(f"Request ID: {pr.request_id}")
    print(f"Stored QR Signature: {pr.qr_signature}")
    print(f"Stored QR Signature length: {len(pr.qr_signature) if pr.qr_signature else 0}")
    
    # Calculate what it should be
    expected = create_signature(str(pr.request_id))
    print(f"Expected Signature: {expected}")
    print(f"Expected Signature length: {len(expected)}")
    
    print(f"Match: {pr.qr_signature == expected}")
    
    # Also check what the QR data would be
    qr_data = f"PAYMENT_REQUEST|{pr.request_id}|{pr.qr_signature}"
    print(f"\nQR Data: {qr_data}")
else:
    print("No payment requests found")
