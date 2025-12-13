# QR Code Stability Guide

## Problem Fixed
Previously, QR codes generated and deployed would become **unscannable after pushing updates** because the QR code signatures were tied to Django's `SECRET_KEY`, which could change during deployments.

## Solution
QR code signatures now use a dedicated **`QR_SIGNATURE_KEY`** that is:
- **Persistent** across all deployments
- **Independent** of Django's SECRET_KEY
- **Immutable** - never changes in production

## Setup Instructions

### 1. Generate Your QR_SIGNATURE_KEY
Run this in your Python environment to generate a secure random key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

This outputs something like: `Drmhze6EPcv0fN_81Bj-nA`

### 2. Add to Your .env File
Create or update your `.env` file in the `projectsite/` directory:

```env
SENDGRID_API_KEY=your-sendgrid-api-key-here
DEFAULT_FROM_EMAIL=UniPay <your-verified-email@example.com>
QR_SIGNATURE_KEY=your-generated-key-from-step-1
```

### 3. Verify Configuration
When you start your Django server, it will verify that `QR_SIGNATURE_KEY` is set. If missing, you'll see:

```
ValueError: QR_SIGNATURE_KEY must be set in settings.py to ensure QR code stability...
```

### 4. Deploy to Production
Once set in your production `.env`, **DO NOT CHANGE IT**.

## Important Notes

⚠️ **CRITICAL**: Once you've generated QR codes in production with a specific `QR_SIGNATURE_KEY`:
- **Never change** `QR_SIGNATURE_KEY`
- **Never rotate** to a new key without understanding the impact
- All old QR codes depend on this key remaining constant

✅ **Safe to change**: Django's `SECRET_KEY` can still be rotated normally for security - it won't affect QR code validity

## How It Works

**Before (Broken)**:
```
QR Signature = HMAC-SHA256(request_id, SECRET_KEY) ❌
- SECRET_KEY changes during deployment
- Old QR codes fail validation
```

**After (Fixed)**:
```
QR Signature = HMAC-SHA256(request_id, QR_SIGNATURE_KEY) ✅
- QR_SIGNATURE_KEY is persistent
- Old QR codes remain valid forever
```

## Testing

To verify your QR codes work:

1. Generate a QR code for a fee on the student dashboard
2. Confirm you can view/scan it
3. Push an update to your server
4. Verify the old QR code still scans correctly

## Troubleshooting

**Q: My QR codes stopped working after an update**
A: Check that `QR_SIGNATURE_KEY` is set in your `.env` file and hasn't changed.

**Q: Can I change QR_SIGNATURE_KEY?**
A: Only if you're okay with invalidating all previously generated QR codes.

**Q: What if I accidentally changed it?**
A: Revert to the original value immediately to restore all QR codes.

## Technical Details

- **Algorithm**: HMAC-SHA256
- **Key Source**: Settings (`QR_SIGNATURE_KEY` environment variable)
- **Data Signed**: Payment request ID only (immutable)
- **Verification**: Used when scanning/processing QR codes
- **Used In**: [paymentorg/views.py](paymentorg/views.py) - `create_signature()` and `validate_signature()` functions
