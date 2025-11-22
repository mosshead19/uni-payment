#!/usr/bin/env python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'projectsite.settings')
django.setup()

from django.contrib.auth.models import User
from paymentorg.models import UserProfile, Officer, Student

# Check a few students
students = Student.objects.all()[:5]
for student in students:
    user = student.user
    print(f"\n{'='*60}")
    print(f"Student: {user.username} ({student.student_id_number})")
    
    # Check UserProfile
    if hasattr(user, 'user_profile'):
        print(f"  UserProfile exists: YES")
        print(f"    is_officer flag: {user.user_profile.is_officer}")
    else:
        print(f"  UserProfile exists: NO")
    
    # Check Officer profile
    if hasattr(user, 'officer_profile'):
        print(f"  Officer exists: YES")
        officer = user.officer_profile
        print(f"    Organization: {officer.organization}")
        print(f"    is_active: {officer.is_active}")
        print(f"    can_promote_officers: {officer.can_promote_officers}")
    else:
        print(f"  Officer exists: NO")
