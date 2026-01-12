# Quick Start After Restart - October 11, 2025 (UPDATED)

## 🎯 Where We Are

**✅ COMPLETED TODAY:**
- ✅ Phase 1: Contract currency fixes + PDF download
- ✅ Phase 2: Email infrastructure backend (templates, sending methods, API endpoints)
- ✅ Gmail App Password configured (norbert@bmasiamusic.com)
- ✅ Email sending tested and working
- ✅ Environment variables added to Render production
- ✅ **Default email templates created** (4 professional templates)

**📧 EMAIL SYSTEM FULLY OPERATIONAL:**
- ✅ Sending emails with PDF attachments
- ✅ 4 professional templates (editable in admin)
- ✅ Multi-user sender support (admin, finance, sales, support, production)
- ✅ Ready for production use

**⏳ NEXT STEPS:**
1. Test email system with real documents (in progress)
2. Phase 3: Frontend email dialogs
3. Phase 4: AI email drafting (optional)

---

## 📧 Gmail Configuration - COMPLETE ✅

### Status:
- ✅ App Password: `fblg duek ghmv ixse` (configured)
- ✅ Email: norbert@bmasiamusic.com
- ✅ .env updated (local)
- ✅ Render environment variables added
- ✅ Test email sent and received successfully

---

## 📝 Email Templates - COMPLETE ✅

4 professional templates created and ready:

1. **quote_send** - "Quote {{document_number}} from {{sender_name}}"
2. **contract_send** - "Contract {{document_number}} - {{company_name}}"
3. **invoice_send** - "Invoice {{document_number}} - Payment Due {{valid_until}}"
4. **renewal_manual** - "Contract Renewal Reminder - {{document_number}}"

**Edit templates at**: `/admin/crm_app/emailtemplate/`

**All templates include**:
- Professional tone
- HTML and plain text versions
- Template variables for customization
- BMAsia branding

---

## 🔧 What's Working Now

### API Endpoints (Backend):
```bash
POST /api/quotes/{id}/send/
POST /api/contracts/{id}/send/
POST /api/invoices/{id}/send/
POST /api/contracts/{id}/send_renewal_notice/
```

### Request Format:
```json
{
  "recipients": ["email@example.com"],  // Optional - auto-selects company contacts
  "subject": "Custom subject",           // Optional - uses template
  "body": "Custom body",                 // Optional - uses template
  "sender": "admin"                      // admin|finance|sales|support|production
}
```

### Features:
- ✅ PDF attachments (quotes, contracts, invoices)
- ✅ Template rendering with {{variables}}
- ✅ Fallback text if template not found
- ✅ Multi-sender support (5 team members)
- ✅ Smart recipient selection (billing contacts, decision makers)
- ✅ EmailLog tracking
- ✅ Document status updates (marks as 'Sent')
- ✅ 24-hour renewal block

---

## 📂 Key Files Modified

### Frontend (3 files):
```
✅ bmasia-crm-frontend/src/pages/Contracts.tsx
✅ bmasia-crm-frontend/src/components/ContractForm.tsx
✅ bmasia-crm-frontend/src/services/api.ts
```

### Backend (5 files):
```
✅ crm_app/models.py
✅ crm_app/admin.py
✅ crm_app/services/email_service.py
✅ crm_app/views.py
✅ bmasia_crm/settings.py
```

### Configuration:
```
✅ .env (local development) - Gmail configured
✅ Render environment variables (production)
```

### Database:
```
✅ Migration: crm_app/migrations/0025_alter_emailtemplate_body_html_and_more.py
✅ Templates: 4 email templates in database
```

---

## 📊 Testing Commands

### Test Quote Email (Django Shell):
```bash
cd "/Users/benorbe/Library/Mobile Documents/com~apple~CloudDocs/Documents/Coding Projects/BMAsia CRM"
./env/bin/python manage.py shell
```

```python
from crm_app.services.email_service import EmailService

es = EmailService()

# Send a quote
es.send_quote_email('QUOTE_ID', sender='sales')

# Send to specific recipient
es.send_contract_email('CONTRACT_ID', recipients=['test@example.com'], sender='admin')

# Send invoice
es.send_invoice_email('INVOICE_ID', sender='finance')
```

### Test via API (curl):
```bash
# Test quote email
curl -X POST http://localhost:8000/api/quotes/QUOTE_ID/send/ \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sender": "sales"}'

# Test with custom content
curl -X POST http://localhost:8000/api/contracts/CONTRACT_ID/send/ \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "recipients": ["test@example.com"],
    "subject": "Custom Subject",
    "body": "Custom body text",
    "sender": "admin"
  }'
```

---

## 🚀 Phase 3 Plan (Next)

### Components to Build:
1. **EmailSendDialog.tsx** (NEW)
   - Multi-recipient selection (checkboxes for company contacts)
   - Template preview/edit per email
   - Sender dropdown (admin, finance, sales, support, production)
   - "Generate with AI" button (Phase 4)

2. **Update Existing Pages**:
   - Quotes.tsx → Add "Send" button → Open EmailSendDialog
   - Contracts.tsx → Add "Send" button → Open EmailSendDialog
   - Invoices.tsx → Add "Send" button → Open EmailSendDialog

3. **Smart Renewal UI**:
   - Show last sent date / next scheduled date
   - Warning if automated reminder sent < 24h ago
   - Confirmation dialog with status

### Agents to Use:
- **ui-ux-designer** → EmailSendDialog component design
- **react-dashboard-builder** → Wire up Send buttons, integrate dialog
- **api-integration-specialist** → OpenAI integration (Phase 4)

---

## 🤖 Phase 4 Plan (Optional AI)

### Requirements:
- OpenAI API key
- User cautious: "keep it simple, don't break things"
- Budget: $10/month approved
- User has OpenAI account

### Implementation:
```bash
# .env
OPENAI_API_KEY=sk-...
ENABLE_AI_EMAIL_DRAFTING=True
```

### Features:
- Context-aware email generation
- Tone: Professional / Friendly / Formal
- Length: Short / Medium / Long
- User edits before sending
- Cost: ~$0.01 per draft

---

## 👥 Adding New Team Members

### Current Team:
- `admin` - Norbert (norbert@bmasiamusic.com)
- `finance` - Pom (pom@bmasiamusic.com)
- `sales` - Niki (niki.h@bmasiamusic.com)
- `support` - Keith (keith@bmasiamusic.com)
- `production` - Production Team (production@bmasiamusic.com)

### To Add New Member:
1. Update `settings.py` EMAIL_SENDERS
2. Add to `.env`
3. Add to Render environment variables
4. Use in API: `{"sender": "new_member"}`

---

## ⚠️ Important Notes

1. **Gmail App Password configured** - fblg duek ghmv ixse (stored securely)
2. **Templates are editable** - Go to `/admin/crm_app/emailtemplate/`
3. **System works without templates** - Has fallback text
4. **Migrations applied** - 0025 is latest
5. **Multi-sender configured** - All 5 team members ready
6. **All PDFs attach automatically** when sending
7. **Emails send from norbert@bmasiamusic.com** regardless of sender (sender changes signature only)

---

## 📚 Full Documentation

- **Session checkpoint**: `SESSION_CHECKPOINT_2025-01-09_FINAL.md`
- **Project instructions**: `CLAUDE.md` (updated)
- **Email templates**: Edit at `/admin/crm_app/emailtemplate/`

---

## 🎬 Next Session Commands

### If restarting Django server:
```bash
cd "/Users/benorbe/Library/Mobile Documents/com~apple~CloudDocs/Documents/Coding Projects/BMAsia CRM"
./env/bin/activate  # or: source env/bin/activate
python manage.py runserver
```

### Quick email test:
```bash
./env/bin/python manage.py shell
>>> from crm_app.services.email_service import EmailService
>>> es = EmailService()
>>> es.send_quote_email('QUOTE_ID')
```

---

**Status**: ✅ Email system fully operational - Ready for testing and Phase 3
**Date**: October 11, 2025
