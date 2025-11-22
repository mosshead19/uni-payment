#!/usr/bin/env python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'projectsite.settings')
django.setup()

from django.contrib.auth.models import User
from paymentorg.models import Officer, UserProfile

# Find a recently promoted officer with can_promote_officers=True
officer = Officer.objects.filter(can_promote_officers=True).first()

if officer:
    user = officer.user
    print(f"\nTesting newly promoted officer login simulation:")
    print(f"  Username: {user.username}")
    
    # Simulate login by reloading user with select_related (like the login view does)
    user_refreshed = User.objects.select_related(
        'officer_profile',
        'student_profile',
        'user_profile'
    ).get(pk=user.pk)
    
    print(f"\n  After select_related refresh:")
    print(f"    has officer_profile: {hasattr(user_refreshed, 'officer_profile')}")
    if hasattr(user_refreshed, 'officer_profile'):
        print(f"    officer_profile.can_promote_officers: {user_refreshed.officer_profile.can_promote_officers}")
        print(f"    officer_profile.is_super_officer: {user_refreshed.officer_profile.is_super_officer}")
    
    print(f"    has user_profile: {hasattr(user_refreshed, 'user_profile')}")
    if hasattr(user_refreshed, 'user_profile'):
        print(f"    user_profile.is_officer: {user_refreshed.user_profile.is_officer}")
    
    # Check what the template would see
    should_show_promote = False
    if hasattr(user_refreshed, 'officer_profile'):
        if user_refreshed.officer_profile.is_super_officer or user_refreshed.officer_profile.can_promote_officers:
            should_show_promote = True
    
    print(f"\n  Template would show Promote/Demote nav: {should_show_promote}")
else:
    print("No officers with can_promote_officers=True found")
