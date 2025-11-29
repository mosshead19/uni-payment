#!/usr/bin/env python
"""
Script to update profile pictures for all existing users with Google accounts.
Run with: python manage.py shell < update_profile_pictures.py
Or: python update_profile_pictures.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'projectsite.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from allauth.socialaccount.models import SocialAccount
from paymentorg.models import UserProfile

def update_profile_pictures():
    # Get all Google social accounts
    social_accounts = SocialAccount.objects.filter(provider='google')
    print(f'Found {social_accounts.count()} Google accounts')

    updated = 0
    for sa in social_accounts:
        user = sa.user
        extra_data = sa.extra_data
        picture_url = extra_data.get('picture')
        print(f'User: {user.username}, Email: {user.email}')
        print(f'  Picture URL: {picture_url}')
        
        if picture_url:
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.profile_picture = picture_url
            profile.save(update_fields=['profile_picture'])
            print(f'  ✓ Updated profile picture for {user.username}')
            updated += 1
    
    print(f'\nDone! Updated {updated} profile pictures.')

if __name__ == '__main__':
    update_profile_pictures()
