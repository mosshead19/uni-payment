#!/usr/bin/env python
"""
Email Configuration Diagnostic Script for UniPay
Run this from PythonAnywhere console:
    cd ~/uni-payment/projectsite
    python check_email_config.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'projectsite.settings')
django.setup()

from django.conf import settings

def check_email_config():
    print("=" * 60)
    print("📧 UniPay Email Configuration Diagnostic")
    print("=" * 60)
    
    # Check environment variables
    print("\n🔍 Environment Variables:")
    print("-" * 40)
    
    sendgrid_key = os.environ.get('SENDGRID_API_KEY', '')
    if sendgrid_key:
        # Mask the key for security
        masked_key = sendgrid_key[:10] + "..." + sendgrid_key[-4:] if len(sendgrid_key) > 14 else "***"
        print(f"✅ SENDGRID_API_KEY: Set ({masked_key})")
    else:
        print("❌ SENDGRID_API_KEY: NOT SET")
        print("   → This is why email is not configured!")
    
    default_from = os.environ.get('DEFAULT_FROM_EMAIL', '')
    if default_from:
        print(f"✅ DEFAULT_FROM_EMAIL: {default_from}")
    else:
        print(f"⚠️  DEFAULT_FROM_EMAIL: Not set (using default: {settings.DEFAULT_FROM_EMAIL})")
    
    # Check Django settings
    print("\n📋 Django Email Settings:")
    print("-" * 40)
    print(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
    
    if 'smtp' in settings.EMAIL_BACKEND.lower():
        print(f"EMAIL_HOST: {getattr(settings, 'EMAIL_HOST', 'Not set')}")
        print(f"EMAIL_PORT: {getattr(settings, 'EMAIL_PORT', 'Not set')}")
        print(f"EMAIL_USE_TLS: {getattr(settings, 'EMAIL_USE_TLS', 'Not set')}")
        print(f"EMAIL_HOST_USER: {getattr(settings, 'EMAIL_HOST_USER', 'Not set')}")
        has_password = bool(getattr(settings, 'EMAIL_HOST_PASSWORD', ''))
        print(f"EMAIL_HOST_PASSWORD: {'Set' if has_password else 'NOT SET'}")
    elif 'console' in settings.EMAIL_BACKEND.lower():
        print("⚠️  Using console backend - emails will NOT be sent!")
    
    print(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
    
    # Test email sending
    print("\n🧪 Email Test:")
    print("-" * 40)
    
    if 'console' in settings.EMAIL_BACKEND.lower():
        print("❌ Cannot test - using console backend")
        print("\n📝 TO FIX THIS:")
        print("   1. Go to PythonAnywhere → Web tab → your app")
        print("   2. Scroll to 'Environment variables' section")
        print("   3. Add: SENDGRID_API_KEY = your_sendgrid_api_key")
        print("   4. Add: DEFAULT_FROM_EMAIL = UniPay <your-verified-sender@domain.com>")
        print("   5. Reload your web app")
        return False
    
    try:
        from django.core.mail import send_mail
        
        # Try a test email (won't actually send, just validates config)
        print("Attempting to connect to SMTP server...")
        
        from django.core.mail import get_connection
        connection = get_connection()
        connection.open()
        print("✅ SMTP connection successful!")
        connection.close()
        
        print("\n✅ Email configuration appears correct!")
        print("   You can test by processing a payment.")
        return True
        
    except Exception as e:
        print(f"❌ SMTP connection failed: {str(e)}")
        print("\n   Possible issues:")
        print("   - Invalid SendGrid API key")
        print("   - SendGrid account not verified")
        print("   - Sender email not verified in SendGrid")
        return False

def show_fix_instructions():
    print("\n" + "=" * 60)
    print("🔧 HOW TO FIX ON PYTHONANYWHERE")
    print("=" * 60)
    print("""
1. Get your SendGrid API Key:
   - Go to https://sendgrid.com
   - Settings → API Keys → Create API Key
   - Give it "Full Access" or at least "Mail Send" permission
   - Copy the key (you can only see it once!)

2. Verify a Sender in SendGrid:
   - Go to Settings → Sender Authentication
   - Create a Single Sender and verify your email

3. Set Environment Variables on PythonAnywhere:
   - Go to: https://www.pythonanywhere.com
   - Web tab → Your web app
   - Scroll to "Environment variables" section
   - Click "Add a new variable"
   - Add these:
     
     SENDGRID_API_KEY = SG.xxxxxxxxxxxxx (your full API key)
     DEFAULT_FROM_EMAIL = UniPay <verified-email@yourdomain.com>

4. Reload your web app:
   - Click the green "Reload" button at the top

5. Run this script again to verify the fix.
""")

if __name__ == "__main__":
    success = check_email_config()
    if not success:
        show_fix_instructions()
    
    print("\n" + "=" * 60)
