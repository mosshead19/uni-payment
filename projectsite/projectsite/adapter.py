from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.forms import ValidationError
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages

class MyAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return True

    def clean_email(self, email):
        if not email.endswith('@psu.palawan.edu.ph'):
            raise ValidationError('Only @psu.palawan.edu.ph emails are allowed.')
        return email

class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        return True

    def pre_social_login(self, request, sociallogin):
        email = sociallogin.account.extra_data.get('email')
        if email and not email.endswith('@psu.palawan.edu.ph'):
            messages.error(request, 'Only @psu.palawan.edu.ph emails are allowed.')
            # We can't easily stop the flow here without raising an exception that crashes
            # or redirecting. Raising ImmediateHttpResponse is the way.
            from allauth.exceptions import ImmediateHttpResponse
            from django.shortcuts import render
            raise ImmediateHttpResponse(render(request, 'account/login_error.html', {'error': 'Only @psu.palawan.edu.ph emails are allowed.'}))
        
        # Update profile picture for existing users on every login
        data = sociallogin.account.extra_data
        picture_url = data.get('picture')
        
        # If user exists (returning user), update their profile picture
        if sociallogin.is_existing:
            user = sociallogin.user
            if picture_url and user:
                from paymentorg.models import UserProfile
                profile, created = UserProfile.objects.get_or_create(user=user)
                if profile.profile_picture != picture_url:
                    profile.profile_picture = picture_url
                    profile.save(update_fields=['profile_picture'])

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        data = sociallogin.account.extra_data
        if data.get('given_name'):
            user.first_name = data.get('given_name')
        if data.get('family_name'):
            user.last_name = data.get('family_name')
        user.save()
        
        # Save Google profile picture to UserProfile
        picture_url = data.get('picture')
        if picture_url:
            from paymentorg.models import UserProfile
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.profile_picture = picture_url
            profile.save(update_fields=['profile_picture'])
        
        return user
