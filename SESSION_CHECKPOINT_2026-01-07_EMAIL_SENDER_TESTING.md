# Session Checkpoint: Email Sender Testing & SMTP Fixes
**Date**: January 7, 2026
**Status**: COMPLETE ✅

## Summary

Tested and verified all email senders are working correctly with per-user SMTP authentication.

## Test Results

| Sender | Email | Purpose | Status |
|--------|-------|---------|--------|
| Kuk | production@bmasiamusic.com | Seasonal campaigns | ✅ Verified |
| Keith | keith@bmasiamusic.com | Offline alerts | ✅ Verified |
| Nikki | nikki.h@bmasiamusic.com | Renewal reminders | ✅ Verified |
| Norbert | norbert@bmasiamusic.com | Quarterly/Manual | ✅ Verified |
| Pom | pom@bmasiamusic.com | Finance/Payment | ⏸️ Pending (no Google App Password) |

## Issues Found & Fixed

### 1. Per-User SMTP Connection for Sequences
**Problem**: Sequence emails were using default SMTP instead of per-user credentials.
**Fix**: Added `_get_smtp_connection_for_sender()` method in `email_service.py` that looks up User by smtp_email and creates SMTP connection with their credentials.

**File**: `crm_app/services/email_service.py`
```python
def _get_smtp_connection_for_sender(self, from_email: str):
    """Get SMTP connection for a specific sender email."""
    from django.core.mail import get_connection
    from crm_app.models import User

    # Extract email from display name format
    import re
    email_match = re.search(r'<(.+?)>', from_email)
    clean_email = email_match.group(1) if email_match else from_email

    user = User.objects.filter(smtp_email=clean_email).first()
    if user and user.smtp_password:
        return get_connection(
            backend='django.core.mail.backends.smtp.EmailBackend',
            host='smtp.gmail.com',
            port=587,
            username=user.smtp_email,
            password=user.smtp_password,
            use_tls=True
        )
    return None
```

### 2. Note Model Field Name
**Problem**: `EmailLog.mark_as_sent()` used `created_by=None` but Note model has `author` field.
**Fix**: Changed to `author=None` in `crm_app/models.py` line 1569.

### 3. Quarterly/Manual Sequence Sender
**Problem**: `_get_sequence_sender()` returned `DEFAULT_FROM_EMAIL` (notifications@) instead of `ADMIN_EMAIL` (norbert@).
**Fix**: Changed to use `settings.ADMIN_EMAIL` for quarterly and manual sequences.

### 4. Offline Alerts Not Using Per-User SMTP
**Problem**: `offline_alert_service.py` sent emails from keith@ but didn't use his SMTP credentials.
**Fix**: Added SMTP connection lookup before sending:
```python
from_email = settings.SUPPORT_EMAIL
smtp_connection = email_service._get_smtp_connection_for_sender(from_email)
# Then pass smtp_connection to send_email()
```

### 5. Admin User SMTP Not Configured
**Problem**: Admin user had no smtp_email set, so norbert@ emails failed.
**Fix**: Configured admin user via API:
```bash
curl -X PATCH -H "Authorization: Bearer $TOKEN" \
  -d '{"smtp_email":"norbert@bmasiamusic.com","smtp_password":"..."}' \
  "https://bmasia-crm.onrender.com/api/v1/users/c5620142-4ee5-494c-b9fa-9fc587f0cb52/"
```

## New API Endpoint Added

### Test Any User's SMTP (Admin Only)
**Endpoint**: `POST /api/v1/users/{user_id}/test_smtp_send/`
**Purpose**: Admin can test any user's SMTP by sending actual email
**Body**: `{"to_email": "recipient@example.com"}`

**File**: `crm_app/views.py` lines 319-352

## Email Routing Summary

| Sequence Type | Sender Email | Settings Key |
|---------------|--------------|--------------|
| `auto_seasonal_*` | production@bmasiamusic.com | `MUSIC_DESIGN_EMAIL` |
| `auto_renewal` | nikki.h@bmasiamusic.com | `SALES_EMAIL` |
| `auto_payment` | pom@bmasiamusic.com | `FINANCE_EMAIL` |
| `auto_quarterly` | norbert@bmasiamusic.com | `ADMIN_EMAIL` |
| `manual` | norbert@bmasiamusic.com | `ADMIN_EMAIL` |
| Offline alerts | keith@bmasiamusic.com | `SUPPORT_EMAIL` |

## User SMTP Configuration Status

| Username | SMTP Email | Configured |
|----------|------------|------------|
| admin | norbert@bmasiamusic.com | ✅ |
| keith | keith@bmasiamusic.com | ✅ |
| kuk | production@bmasiamusic.com | ✅ |
| nikki | nikki.h@bmasiamusic.com | ✅ |
| pom | - | ❌ (needs Google App Password) |

## Commits Made

1. `d6383f90` - Fix: Per-user SMTP authentication for sequence emails
2. `627466d5` - Fix: Note model field name (author not created_by)
3. `7e171a8a` - Fix: Use ADMIN_EMAIL for quarterly/manual sequences
4. `23117c97` - Fix: Use per-user SMTP for offline alerts (keith@)
5. `499c1c27` - Add: Admin endpoint to test any user's SMTP

## Files Modified

| File | Changes |
|------|---------|
| `crm_app/services/email_service.py` | Added `_get_smtp_connection_for_sender()`, updated `execute_sequence_step()` |
| `crm_app/services/offline_alert_service.py` | Added SMTP connection lookup for keith@ |
| `crm_app/models.py` | Fixed Note field name in `mark_as_sent()` |
| `crm_app/views.py` | Added `test_smtp_send` admin endpoint |

## How to Test Email Senders

### Via API (Admin)
```bash
# Get token
TOKEN=$(curl -s -X POST -d '{"username":"admin","password":"bmasia123"}' \
  "https://bmasia-crm.onrender.com/api/v1/auth/login/" | jq -r '.access')

# Test specific user's SMTP
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -d '{"to_email":"test@example.com"}' \
  "https://bmasia-crm.onrender.com/api/v1/users/{user_id}/test_smtp_send/"
```

### User IDs
- admin (norbert): `c5620142-4ee5-494c-b9fa-9fc587f0cb52`
- keith: `ed26acbc-80f9-46c9-8d7a-789c88077e3f`
- kuk (production): `ce0d7b70-7b81-4bfa-8eb9-5a5927273e8a`
- nikki: (check via API)

## Next Steps

1. Configure pom@bmasiamusic.com when Google App Password is available
2. Monitor email delivery for all senders
3. Test offline alerts when zones go offline
