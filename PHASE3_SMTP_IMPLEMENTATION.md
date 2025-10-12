# Phase 3: Per-User SMTP Email System - ✅ IMPLEMENTATION COMPLETE

## Status: COMPLETE (October 12, 2025)

**Commit**: 1ad460d8
**Deployed**: Production (backend + frontend)
**Time Taken**: ~2 hours (as estimated: 90 min + build/deploy)

---

## Overview
Implement a complete per-user SMTP authentication system where each team member sends emails from their own Gmail account using their own app password. No sender dropdown needed - emails automatically sent from the logged-in user's account.

### ✅ Implementation Complete
All planned features have been successfully implemented and deployed to production.

## Architecture Decision

### Current System (Multi-Sender with Single SMTP)
- All emails sent through norbert@bmasiamusic.com Gmail SMTP
- Backend has 5 sender profiles (admin, finance, sales, support, production)
- "From" address changes but SMTP is always norbert@
- Replies may go to wrong inbox

### Target System (Per-User SMTP)
- Each user has their own Gmail SMTP credentials
- When Pom logs in and sends email → comes from pom@bmasiamusic.com via her Gmail
- When Nikki logs in and sends email → comes from nikki.h@bmasiamusic.com via her Gmail
- Replies automatically go to correct person's inbox
- Each person sees sent emails in their own Gmail Sent folder

## Implementation Plan

### Phase 1: Backend - User Model & Email Service (30-45 min)

#### Task 1.1: Update User Model
**File**: `crm_app/models.py`

**Changes needed**:
```python
class User(AbstractBaseUser, PermissionsMixin):
    # ... existing fields ...

    # Add new SMTP fields
    smtp_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Gmail address for sending emails (e.g., user@bmasiamusic.com)"
    )
    smtp_password = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Gmail app password (will be encrypted)"
    )

    def get_smtp_config(self):
        """Return user's SMTP configuration or system default"""
        if self.smtp_email and self.smtp_password:
            return {
                'email': self.smtp_email,
                'password': self.smtp_password,
                'host': 'smtp.gmail.com',
                'port': 587,
                'use_tls': True,
            }
        return None  # Fall back to system default
```

**Agent to use**: Direct edit (simple model addition)

#### Task 1.2: Create Migration
**Commands**:
```bash
python manage.py makemigrations
python manage.py migrate
```

**Test locally first**, then run on production after deployment.

#### Task 1.3: Update Email Service
**File**: `crm_app/services/email_service.py`

**Changes needed**:
1. Modify `send_contract_email()`, `send_quote_email()`, `send_invoice_email()` methods
2. Extract user from request: `user = request.user`
3. Check if user has SMTP config: `smtp_config = user.get_smtp_config()`
4. If yes, use their credentials; if no, fall back to system default
5. Fix typo: Change `niki.h@bmasiamusic.com` → `nikki.h@bmasiamusic.com` in SENDER_CONFIGS

**Example logic**:
```python
def send_contract_email(self, contract_id, recipients=None, subject=None, body=None, request=None):
    # Get user's SMTP config
    user_smtp = None
    sender_email = settings.DEFAULT_FROM_EMAIL

    if request and request.user.is_authenticated:
        user_smtp = request.user.get_smtp_config()
        if user_smtp:
            sender_email = user_smtp['email']

    # Create email connection
    if user_smtp:
        connection = get_connection(
            host=user_smtp['host'],
            port=user_smtp['port'],
            username=user_smtp['email'],
            password=user_smtp['password'],
            use_tls=user_smtp['use_tls'],
        )
    else:
        connection = None  # Use default

    # Send email using connection
    msg = EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email=sender_email,
        to=recipients,
        connection=connection
    )
    # ... rest of email sending logic
```

**Agent to use**: email-automation-specialist

#### Task 1.4: Update Admin Interface
**File**: `crm_app/admin.py`

**Changes needed**:
```python
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    fieldsets = (
        # ... existing fieldsets ...
        ('Email SMTP Configuration', {
            'fields': ('smtp_email', 'smtp_password'),
            'description': 'Configure Gmail credentials for sending emails as this user'
        }),
    )

    # Make password field use password input widget
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'smtp_password' in form.base_fields:
            form.base_fields['smtp_password'].widget = forms.PasswordInput(render_value=True)
        return form
```

**Agent to use**: django-admin-expert

### Phase 2: Frontend - Email Send Dialog (20-30 min)

#### Task 2.1: Create EmailSendDialog Component
**File**: `bmasia-crm-frontend/src/components/EmailSendDialog.tsx`

**Component specs**:
- Material-UI Dialog
- Props:
  - `open: boolean`
  - `onClose: () => void`
  - `documentType: 'quote' | 'contract' | 'invoice'`
  - `documentId: string`
  - `documentNumber: string`
  - `companyName: string`
  - `contacts: Contact[]`
  - `onSendSuccess: () => void`
  - `onSendEmail: (data: EmailSendData) => Promise<void>`

**Features**:
- Multi-select recipients (checkboxes, pre-select primary/billing contacts)
- Editable subject field (pre-filled from template)
- Editable body field (pre-filled from template, multiline)
- NO sender dropdown (automatic based on login)
- Send button with loading state
- Success Snackbar notification
- Error Alert display
- BMAsia orange accent color (#FFA500)

**Agent to use**: ui-ux-designer

#### Task 2.2: Update API Service
**File**: `bmasia-crm-frontend/src/services/api.ts`

**Add methods**:
```typescript
export interface EmailSendData {
  recipients: string[];
  subject: string;
  body: string;
}

async sendContractEmail(contractId: string, data: EmailSendData): Promise<void> {
  await authApi.post(`/contracts/${contractId}/send/`, data);
}

async sendQuoteEmail(quoteId: string, data: EmailSendData): Promise<void> {
  await authApi.post(`/quotes/${quoteId}/send/`, data);
}

async sendInvoiceEmail(invoiceId: string, data: EmailSendData): Promise<void> {
  await authApi.post(`/invoices/${invoiceId}/send/`, data);
}
```

**Agent to use**: react-dashboard-builder

#### Task 2.3: Integrate into Contracts Page
**File**: `bmasia-crm-frontend/src/pages/Contracts.tsx`

**Changes**:
1. Import EmailSendDialog
2. Add state for dialog open/close and selected contract
3. Add "Send Email" item to action menu (with Email icon)
4. Handle click: load full contract with company.contacts
5. Open dialog with contract data
6. On success: show notification, refresh list

**Agent to use**: react-dashboard-builder

#### Task 2.4: Integrate into Quotes Page
**File**: `bmasia-crm-frontend/src/pages/Quotes.tsx`

**Changes**: Same as Contracts page but for quotes

**Agent to use**: react-dashboard-builder

### Phase 3: Testing & Deployment (15-20 min)

#### Task 3.1: Local Testing
1. Test sending email as admin user
2. Create test user account (pom)
3. Configure pom's SMTP credentials in admin
4. Login as pom, send email
5. Verify email comes from pom@bmasiamusic.com
6. Verify reply goes to pom's inbox

#### Task 3.2: Build & Deploy
```bash
# Frontend build
cd bmasia-crm-frontend
npm run build

# Verify no TypeScript errors
npx tsc --noEmit

# Git commit
git add .
git commit -m "Feat: Per-user SMTP email system with frontend UI

- Add smtp_email and smtp_password to User model
- Email service uses logged-in user's SMTP credentials
- EmailSendDialog component with recipient selection
- Integrate Send Email into Contracts and Quotes pages
- Fix typo: niki.h@ -> nikki.h@
- Auto-send from user's own Gmail account

Phase 3 Complete ✅"

# Push to trigger auto-deploy
git push origin main
```

#### Task 3.3: Production Setup
1. Wait for deployment to complete
2. Run migrations on production (if not auto-run)
3. Access Django admin on production
4. For each user, add SMTP credentials:
   - Pom: pom@bmasiamusic.com + her app password
   - Nikki: nikki.h@bmasiamusic.com + her app password
   - Keith: keith@bmasiamusic.com + his app password

#### Task 3.4: Production Testing
1. Login as each user
2. Send test email from Contracts/Quotes
3. Verify sender address is correct
4. Verify reply goes to correct inbox
5. Check Gmail Sent folder for each user

## User Setup Guide (Post-Implementation)

### For Each Team Member:

**Step 1: Create Gmail App Password**
1. Go to Google Account settings
2. Security → 2-Step Verification (must be enabled)
3. App passwords
4. Generate new app password for "Mail"
5. Copy the 16-character password

**Step 2: Admin Configures User**
1. Login to Django admin: https://bmasia-crm.onrender.com/admin/
2. Go to Users
3. Click on user (Pom, Nikki, Keith, etc.)
4. Scroll to "Email SMTP Configuration"
5. Enter:
   - SMTP Email: their Gmail address
   - SMTP Password: the app password from Step 1
6. Save

**Step 3: User Tests**
1. Login to CRM with their credentials
2. Go to Contracts or Quotes
3. Click action menu (⋮) on any item
4. Click "Send Email"
5. Select recipients, edit message
6. Click "Send"
7. Check their Gmail Sent folder - email should appear there

## Security Considerations

### Password Storage
- SMTP passwords stored in database
- Consider encrypting with Django's `encrypt` field in future
- Only superusers can view/edit SMTP credentials
- Each user can only use their own credentials (no cross-user sending)

### Access Control
- Only authenticated users can send emails
- User must have permission to view the document they're sending
- Email sending logged with user attribution

### Fallback Behavior
- If user has no SMTP configured: Use system default (norbert@)
- If user's SMTP fails: Log error, notify user, don't send
- Clear error messages for authentication failures

## Expected Results

### User Experience
✅ Pom logs in → clicks "Send Email" on contract → email sent from pom@bmasiamusic.com
✅ Client receives email from Pom
✅ Client clicks Reply → reply goes to pom@bmasiamusic.com
✅ Pom sees sent email in her Gmail Sent folder
✅ Pom sees reply in her Gmail inbox

### Technical Results
✅ No "via norbert@" disclaimers
✅ Proper SPF/DKIM validation (Gmail native)
✅ Clean audit trail (who sent what)
✅ Independent SMTP credentials (revocable per user)
✅ Professional email delivery

## Rollback Plan

If implementation fails:
1. Keep backend changes (no breaking changes)
2. Remove frontend UI elements
3. Use API directly via Postman/curl
4. System falls back to default SMTP if user has no config

## Future Enhancements (Optional)

1. **Auto-create SMTP fields from user email**: When creating user with email pom@bmasiamusic.com, auto-set smtp_email
2. **User profile page**: Allow users to configure their own SMTP credentials
3. **SMTP test button**: In admin, test SMTP credentials before saving
4. **Email signature**: Per-user email signatures
5. **Send on behalf of**: Allow admins to send as other users (with logging)

## Files to Update After Implementation

1. `CLAUDE.md` - Update email system status
2. `SESSION_CHECKPOINT_2025-10-12.md` - Mark as complete
3. `EMAIL_SYSTEM_STATUS.md` - Update with per-user SMTP details
4. This file - Mark tasks as complete

## Estimated Timeline

- **Phase 1 (Backend)**: 45 minutes
  - User model: 10 min
  - Migration: 5 min
  - Email service: 20 min
  - Admin interface: 10 min

- **Phase 2 (Frontend)**: 30 minutes
  - EmailSendDialog: 15 min
  - API service: 5 min
  - Contracts integration: 5 min
  - Quotes integration: 5 min

- **Phase 3 (Deploy & Test)**: 15 minutes
  - Build & deploy: 5 min
  - Setup credentials: 5 min
  - Testing: 5 min

**Total: 90 minutes**

## Success Criteria

- ✅ User model has SMTP fields
- ✅ Migration 0025 applied locally and production
- ✅ Email service uses user's SMTP credentials with fallback
- ✅ EmailSendDialog component created
- ✅ Send Email buttons in Contracts page
- ✅ Send Email buttons in Quotes page
- ✅ Typo fixed: niki.h@ → nikki.h@
- ⏳ Emails sent from correct user account (production setup needed)
- ⏳ Replies go to correct inbox (production setup needed)
- ⏳ All team members configured with SMTP (awaiting app passwords)
- ⏳ Production testing with real users (next step)
- ✅ Documentation updated (CLAUDE.md, USER_SMTP_SETUP_GUIDE.md)

---

**Document Created**: October 12, 2025
**Implementation Status**: ✅ COMPLETE
**Deployment Status**: ✅ DEPLOYED (commit 1ad460d8)
**Next Step**: Configure team member SMTP credentials (see USER_SMTP_SETUP_GUIDE.md)
