# Session Checkpoint: Contract Improvements & Bug Fixes
**Date**: January 5, 2026
**Focus**: Multi-year contract support, bug fixes, user account setup

---

## Summary

This session focused on:
1. Setting up BMAsia team user accounts
2. Adding multi-year contract support (send_renewal_reminders toggle)
3. Fixing View Details blank page bug
4. Fixing document upload in Contract Create/Edit form

---

## Changes Made

### 1. Multi-Year Contract Support

**Problem**: Contracts like Jetts Fitness (36 months, Jan 2025 - Dec 2027) were receiving renewal reminder emails prematurely.

**Solution**: Added `send_renewal_reminders` toggle to contracts.

**Files Modified**:
- `crm_app/models.py` - Added `send_renewal_reminders` BooleanField (default=True)
- `crm_app/migrations/0045_contract_send_renewal_reminders.py` - New migration
- `crm_app/serializers.py` - Added field to ContractSerializer
- `crm_app/services/auto_enrollment_service.py` - Added filter `send_renewal_reminders=True`
- `bmasia-crm-frontend/src/types/index.ts` - Added `send_renewal_reminders?: boolean`
- `bmasia-crm-frontend/src/components/ContractForm.tsx` - Added toggle switch in Contract Period section

**How to Use**:
1. Edit contract → Contract Period section
2. Uncheck "Send automatic renewal reminders"
3. Save contract
4. Renewal emails will be skipped for this contract

---

### 2. View Details Blank Page Fix

**Problem**: Clicking "View Details" on a contract caused a blank white page.

**Root Cause**: `getContractDocuments` API method expected an array but Django REST Framework returns paginated data with `{ count, results: [...] }`.

**Fix** (`bmasia-crm-frontend/src/services/api.ts` line 1105):
```typescript
// Before
return response.data;

// After
return response.data.results || response.data || [];
```

---

### 3. Contract Document Upload Fix

**Problem**: Attaching documents in Contract Create/Edit form showed files in UI but never uploaded them.

**Root Cause**: Files were stored in `attachments` state but `handleSubmit` never uploaded them.

**Fix** (`bmasia-crm-frontend/src/components/ContractForm.tsx` lines 461-478):
```typescript
// Upload attachments after saving contract
if (attachments.length > 0 && savedContract.id) {
  for (const file of attachments) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('contract', savedContract.id);
    formData.append('title', file.name.replace(/\.[^/.]+$/, ''));
    formData.append('document_type', 'other');
    await ApiService.uploadContractDocument(savedContract.id, formData);
  }
}
```

---

### 4. BMAsia Team User Accounts

Created user accounts via API:

| Username | Name | Email | Role |
|----------|------|-------|------|
| admin | Norbert Platzer | norbert@bmasiamusic.com | Admin |
| nikki | Nikki Hameede | nikki.h@bmasiamusic.com | Admin |
| pom | Pom | pom@bmasiamusic.com | Admin |
| kuk | Khun Kuk | production@bmasiamusic.com | Admin |
| keith | Keith Clifton | keith@bmasiamusic.com | Admin |

**Password**: bmasia2026 (for all new accounts)
**SMTP Setup**: Pending Gmail App Passwords from team members

---

## Database Changes

### Migration 0045: contract_send_renewal_reminders
```python
migrations.AddField(
    model_name='contract',
    name='send_renewal_reminders',
    field=models.BooleanField(
        default=True,
        help_text='Send automatic renewal reminder emails for this contract'
    ),
)
```

---

## Commits

1. `70aee2d3` - Feature: Add send_renewal_reminders toggle for multi-year contracts
2. `51444c4e` - Fix: Contract View Details blank page bug
3. `8e4b82dc` - Fix: Document upload in Contract Create/Edit form

---

## Testing Notes

### Contract Status in Form
- Status dropdown is in **Basic Information** section (top of form)
- Not in Signatories section (user was scrolling past it)
- All statuses available: Draft, Sent, Signed, **Active**, Expired, Terminated, Renewed

### Jetts Fitness Contract Setup
- Status: Active
- Dates: Dec 31, 2024 - Dec 30, 2027 (36 months)
- Value: THB 1,680,000
- Type: Custom
- Renewal: Manual
- Send Renewal Reminders: **Unchecked** (to prevent premature emails)

---

## Production URLs

- **Backend**: https://bmasia-crm.onrender.com
- **Frontend**: https://bmasia-crm-frontend.onrender.com
- **Admin**: https://bmasia-crm.onrender.com/admin/

---

## Next Steps

1. Team members need to provide Gmail App Passwords for SMTP setup
2. Continue uploading contacts and contracts
3. Test document upload in Contract Create/Edit form
