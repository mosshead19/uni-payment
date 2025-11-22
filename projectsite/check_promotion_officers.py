#!/usr/bin/env python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'projectsite.settings')
django.setup()

from paymentorg.models import Officer

# Get officers with promotion authority
officers_with_promo = Officer.objects.filter(can_promote_officers=True)

print(f"\nOfficers with can_promote_officers=True: {officers_with_promo.count()}")
for officer in officers_with_promo:
    user = officer.user
    user_profile = user.user_profile if hasattr(user, 'user_profile') else None
    print(f"\n  Username: {user.username}")
    print(f"    Officer: {officer.id}")
    print(f"    Organization: {officer.organization}")
    print(f"    can_promote_officers: {officer.can_promote_officers}")
    print(f"    is_active: {officer.is_active}")
    if user_profile:
        print(f"    is_officer flag: {user_profile.is_officer}")
