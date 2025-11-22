#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'projectsite.settings')
django.setup()

from paymentorg.models import PaymentRequest
from paymentorg.views import create_signature

# Fix all payment requests with mismatched signatures
count = 0
for pr in PaymentRequest.objects.all():
    expected_sig = create_signature(str(pr.request_id))
    if pr.qr_signature != expected_sig:
        print(f"Fixing {pr.request_id}: {pr.qr_signature[:16]}... -> {expected_sig[:16]}...")
        pr.qr_signature = expected_sig
        pr.save(update_fields=['qr_signature'])
        count += 1

print(f"\nFixed {count} payment request signatures")
