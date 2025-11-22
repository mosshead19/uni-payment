#!/usr/bin/env python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'projectsite.settings')
django.setup()

from paymentorg.models import Officer, PaymentRequest, Organization

# Find officers in the same organization
officers = Officer.objects.filter(organization__isnull=False).values('organization').distinct()

print(f"\nOrganizations with officers: {officers.count()}")

for org_data in officers[:3]:  # Check first 3 orgs
    org_id = org_data['organization']
    org = Organization.objects.get(id=org_id)
    
    print(f"\n{'='*60}")
    print(f"Organization: {org.name} (ID: {org_id})")
    
    # Get officers in this org
    org_officers = Officer.objects.filter(organization_id=org_id)
    print(f"  Officers in org: {org_officers.count()}")
    for officer in org_officers:
        print(f"    - {officer.user.username}")
    
    # Get payment requests for this org
    payment_requests = PaymentRequest.objects.filter(organization_id=org_id)
    print(f"  Payment requests in org: {payment_requests.count()}")
    if payment_requests.exists():
        for pr in payment_requests[:3]:
            print(f"    - Request ID: {pr.request_id}, Student: {pr.student.student_id_number}, Status: {pr.status}")
