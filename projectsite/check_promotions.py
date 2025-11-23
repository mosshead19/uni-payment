#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'projectsite.settings')
django.setup()

from django.contrib.auth.models import User
from paymentorg.models import Officer

users = User.objects.filter(officer_profile__isnull=False)[:15]
print(f"\n{'Username':<20} {'First Name':<20} {'Can Promote':<15} {'Organization':<20}")
print("-" * 75)
for u in users:
    officer = u.officer_profile
    print(f"{u.username:<20} {u.first_name:<20} {str(officer.can_promote_officers):<15} {officer.organization.name:<20}")
