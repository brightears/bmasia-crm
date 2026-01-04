# Session Checkpoint: Extended Email Automation System
**Date**: January 4, 2026
**Status**: COMPLETE - Deployed to Production
**Latest Commit**: `94d72678`

---

## Summary

Implemented extended email automation with:
1. Opt-out enforcement in AutoEnrollmentService
2. Quarterly check-ins based on contract START date (90/180/270/360 days)
3. Seasonal campaigns by country (10 festivals, 18+ countries)
4. SeasonalTriggerDate model for variable holiday dates
5. Company-level seasonal opt-out checkbox
6. **NEW**: Granular contact email preferences (per-contact, per-email-type opt-out)

---

## Completed Work

### Backend Changes

| File | Changes |
|------|---------|
| `crm_app/models.py` | Added `SeasonalTriggerDate` model, `seasonal_emails_enabled` to Company, 7 new sequence types, increased `sequence_type` max_length to 30 |
| `crm_app/admin.py` | Registered `SeasonalTriggerDateAdmin` |
| `crm_app/services/auto_enrollment_service.py` | Added opt-out checks, fixed quarterly triggers, added `process_seasonal_triggers()` method |
| `crm_app/management/commands/send_emails.py` | Added 'seasonal' to email types |
| `crm_app/serializers.py` | Added `seasonal_emails_enabled` to CompanySerializer |
| `crm_app/migrations/0043_seasonal_automation_system.py` | Migration for all new fields |

### Frontend Changes

| File | Changes |
|------|---------|
| `bmasia-crm-frontend/src/types/index.ts` | Added `seasonal_emails_enabled` to Company interface |
| `bmasia-crm-frontend/src/components/CompanyForm.tsx` | Added seasonal checkbox |
| `bmasia-crm-frontend/src/pages/CompanyNew.tsx` | Added seasonal checkbox |
| `bmasia-crm-frontend/src/pages/CompanyEdit.tsx` | Added seasonal checkbox |
| `bmasia-crm-frontend/src/pages/EmailTemplates.tsx` | Added click-to-edit on rows |

### Sequence Types Added

```python
('auto_seasonal_christmas', 'Auto: Christmas (All)'),
('auto_seasonal_cny', 'Auto: Chinese New Year (Asia)'),
('auto_seasonal_songkran', 'Auto: Songkran (Thailand)'),
('auto_seasonal_loy_krathong', 'Auto: Loy Krathong (Thailand)'),
('auto_seasonal_valentines', 'Auto: Valentines Day (All)'),
('auto_seasonal_ramadan', 'Auto: Ramadan (Middle East)'),
('auto_seasonal_singapore_nd', 'Auto: Singapore National Day'),
```

### Country Mapping (in auto_enrollment_service.py)

```python
SEASONAL_COUNTRY_MAP = {
    'auto_seasonal_christmas': ['ALL'],
    'auto_seasonal_valentines': ['ALL'],
    'auto_seasonal_cny': ['Thailand', 'Singapore', 'Malaysia', 'Hong Kong', 'China', 'Taiwan', 'Vietnam'],
    'auto_seasonal_songkran': ['Thailand'],
    'auto_seasonal_loy_krathong': ['Thailand'],
    'auto_seasonal_ramadan': ['UAE', 'Saudi Arabia', 'Qatar', 'Kuwait', 'Bahrain', 'Oman', 'Malaysia', 'Indonesia'],
    'auto_seasonal_singapore_nd': ['Singapore'],
}
```

**USER REQUEST**: Update CNY to ALL Asian countries (add more), keep Ramadan for Middle East, keep Loy Krathong Thailand only.

### Fixed Trigger Dates

```python
SEASONAL_TRIGGER_DATES = {
    'auto_seasonal_christmas': (10, 15),    # Oct 15
    'auto_seasonal_valentines': (1, 31),    # Jan 31
    'auto_seasonal_songkran': (3, 29),      # Mar 29
    'auto_seasonal_singapore_nd': (7, 26),  # Jul 26
    'auto_seasonal_cny': 'variable',        # From SeasonalTriggerDate model
    'auto_seasonal_loy_krathong': 'variable',
    'auto_seasonal_ramadan': 'variable',
}
```

---

## Git Commits

```
087841e4 Feature: Extended Email Automation System
026a64d1 UX: Click on email template row to open edit form
558718ce Feature: Workflow improvements based on Boris Cherny method
```

---

## Production URLs

- **Backend**: https://bmasia-crm.onrender.com
- **Frontend**: https://bmasia-crm-frontend.onrender.com
- **Admin**: https://bmasia-crm.onrender.com/admin/

---

## Known Issues / Next Steps

✅ **RESOLVED** - All issues from previous session have been addressed:

1. ~~SeasonalTriggerDate not visible in admin~~ → **RESOLVED**: It's registered at line 2090 in admin.py, user just needs to scroll down under "CRM_APP" section

2. ~~User wants frontend date setting~~ → **IMPLEMENTED**: Created Settings.tsx page with full CRUD for holiday dates
   - Navigate to: https://bmasia-crm-frontend.onrender.com/settings
   - Or use sidebar: Administration → Settings

3. ~~Update country mapping for CNY~~ → **UPDATED**: CNY now includes ALL Asian countries:
   - Thailand, Singapore, Malaysia, Hong Kong, China, Taiwan, Vietnam
   - Japan, South Korea, Philippines, Indonesia, Myanmar, Cambodia
   - Laos, Brunei, Macau, Mongolia, North Korea

---

## Latest Deployment (January 4, 2026)

**Commit**: `05ec5657` - Feature: Frontend Settings page for variable holiday dates

### New Files
- `bmasia-crm-frontend/src/pages/Settings.tsx` - Holiday date management UI

### Modified Files
- `crm_app/services/auto_enrollment_service.py` - Updated country mapping for CNY and Ramadan
- `crm_app/serializers.py` - Added SeasonalTriggerDateSerializer
- `crm_app/views.py` - Added SeasonalTriggerDateViewSet
- `crm_app/urls.py` - Added seasonal-trigger-dates route
- `bmasia-crm-frontend/src/types/index.ts` - Added SeasonalTriggerDate interface
- `bmasia-crm-frontend/src/services/api.ts` - Added CRUD methods for seasonal dates
- `bmasia-crm-frontend/src/App.tsx` - Added /settings route
- `bmasia-crm-frontend/src/components/Layout.tsx` - Added Settings link in sidebar

---

## Key Files Reference

- **AutoEnrollmentService**: `crm_app/services/auto_enrollment_service.py` (lines 1-450)
- **SeasonalTriggerDate model**: `crm_app/models.py` (around line 1730)
- **Company.seasonal_emails_enabled**: `crm_app/models.py` (line 140)
- **Sequence types**: `crm_app/models.py` (EmailSequence.SEQUENCE_TYPE_CHOICES)
- **Plan file**: `.claude/plans/memoized-churning-bird.md`

---

## Department Email Routing

| Department | Email | Use Case |
|------------|-------|----------|
| Music Design | production@bmasiamusic.com | Seasonal campaigns |
| Sales | nikki.h@bmasiamusic.com | Contracts, quotations |
| Finance | pom@bmasiamusic.com | Invoices, payments |
| Admin | norbert@bmasiamusic.com | Quarterly, renewals |

---

## Email Templates (20 total in production)

- **10 seasonal** (Christmas, CNY, Valentine's, Songkran, Loy Krathong, Ramadan, Singapore ND, **Diwali**, **Mid-Autumn**, **Eid al-Fitr**)
- 4 renewal (30, 14, 7 days, urgent)
- 3 payment (7, 14 days overdue, overdue)
- 1 quarterly check-in
- 1 welcome
- 1 contract signed

---

## Session 2: New Festivals Added (January 4, 2026 - Later)

### New Festivals Implemented

| Festival | Template Type | Holiday Type | Target Countries |
|----------|---------------|--------------|------------------|
| **Diwali** | `seasonal_diwali` | `auto_seasonal_diwali` | India, Nepal, Singapore, Malaysia, Sri Lanka, Mauritius, Fiji |
| **Mid-Autumn Festival** | `seasonal_mid_autumn` | `auto_seasonal_mid_autumn` | China, Vietnam, Taiwan, Hong Kong, Macau, Singapore, Malaysia |
| **Eid al-Fitr** | `seasonal_eid_fitr` | `auto_seasonal_eid_fitr` | Indonesia, Malaysia, Brunei, Singapore, UAE, Saudi Arabia, Qatar, Kuwait, Bahrain, Oman, Jordan, Lebanon, Egypt, Iraq, Iran, Turkey, Pakistan, Bangladesh |

### 2026 Variable Holiday Schedule (All Pre-configured)

| Holiday | Trigger Date | Holiday Date |
|---------|--------------|--------------|
| Chinese New Year | Jan 15 | Jan 29 |
| Ramadan | Feb 3 | Feb 17 |
| Eid al-Fitr | Mar 6 | Mar 20 |
| Mid-Autumn Festival | Sep 19 | Oct 3 |
| Diwali | Oct 25 | Nov 8 |
| Loy Krathong | Oct 31 | Nov 14 |

### Git Commits (Session 2)

```
8875c788 Add email template types for new festivals
82581e74 Feature: Add Diwali, Mid-Autumn Festival, Eid al-Fitr seasonal campaigns
48d01005 Fix: Handle paginated API response in Settings page
05ec5657 Feature: Frontend Settings page for variable holiday dates
```

### Files Modified (Session 2)

| File | Changes |
|------|---------|
| `crm_app/models.py` | Added 3 holiday types to SeasonalTriggerDate, 3 sequence types to EmailSequence, 3 template types to EmailTemplate |
| `crm_app/services/auto_enrollment_service.py` | Added country mappings for Diwali, Mid-Autumn, Eid al-Fitr |
| `bmasia-crm-frontend/src/pages/Settings.tsx` | Added 3 new festivals to HOLIDAY_TYPES dropdown |
| `bmasia-crm-frontend/src/types/index.ts` | Updated SeasonalTriggerDate interface with new holiday types |

### API Data Created (via production API)

**Email Templates Created:**
- Diwali Festival Greetings (`2b4f64ab-f0b7-4d39-9eaa-e62ddd14a48d`)
- Mid-Autumn Festival Greetings (`90d1db1d-57d3-4cff-b045-7de0513cb125`)
- Eid al-Fitr Festival Greetings (`c68d25fb-7f95-456f-8a5d-613f7db83564`)

**Trigger Dates Created:**
- Diwali 2026 (`09410cfd-ba59-49b4-a875-a1e728a94cf4`)
- Mid-Autumn 2026 (`115117f6-5f11-410e-a120-6340e6625e58`)
- Eid al-Fitr 2026 (`ed3d7ea6-12aa-4660-a266-7fc3ee49527c`)
- Ramadan 2026 (`2e911be9-cfd1-476c-9d24-258e4836d3a7`)
- Loy Krathong 2026 (`f09cbe3e-4dba-4589-92f1-79d64cbad056`)

---

## Session 3: Email Sequences Created (January 4, 2026 - Final)

### 10 Seasonal Email Sequences Created

All sequences are **active** with 1 step each, linked to corresponding email templates.

| Sequence Type | Name | Template Linked |
|---------------|------|-----------------|
| `auto_seasonal_christmas` | Christmas Season Campaign | Christmas Season Music Campaign |
| `auto_seasonal_cny` | Chinese New Year Campaign | Chinese New Year Music Campaign |
| `auto_seasonal_valentines` | Valentine's Day Campaign | Valentine's Day Music Campaign |
| `auto_seasonal_songkran` | Songkran Festival Campaign | Songkran Festival Music Campaign |
| `auto_seasonal_ramadan` | Ramadan Campaign | Ramadan Music Campaign |
| `auto_seasonal_loy_krathong` | Loy Krathong Campaign | Loy Krathong Festival Music Campaign |
| `auto_seasonal_singapore_nd` | Singapore National Day Campaign | Singapore National Day Music Campaign |
| `auto_seasonal_diwali` | Diwali Festival Campaign | Diwali Festival Greetings |
| `auto_seasonal_mid_autumn` | Mid-Autumn Festival Campaign | Mid-Autumn Festival Greetings |
| `auto_seasonal_eid_fitr` | Eid al-Fitr Campaign | Eid al-Fitr Festival Greetings |

### System Status: FULLY OPERATIONAL

**Complete Automation Flow:**
1. Cron job runs daily at 9 AM Bangkok time
2. `AutoEnrollmentService.process_seasonal_triggers()` checks trigger dates
3. For matching dates, finds companies in target countries with active contracts
4. Enrolls primary contact into corresponding EmailSequence
5. Sends seasonal greeting email

**What User Needs to Load:**
- Companies with correct `country` field (e.g., "Thailand", "Singapore", "India")
- Contacts linked to companies (`receives_notifications=True`, `unsubscribed=False`)
- Contracts with `status='Active'` linked to companies

### Final Git Commit
```
50d42640 Docs: Update CLAUDE.md and session checkpoint with seasonal automation
```

---

## Quick Reference for Future Sessions

### Key Files
| File | Purpose |
|------|---------|
| `crm_app/models.py` | SeasonalTriggerDate model, EmailSequence.SEQUENCE_TYPE_CHOICES |
| `crm_app/services/auto_enrollment_service.py` | SEASONAL_COUNTRY_MAP, SEASONAL_TRIGGER_DATES, process_seasonal_triggers() |
| `crm_app/views.py` | SeasonalTriggerDateViewSet |
| `bmasia-crm-frontend/src/pages/Settings.tsx` | Holiday date management UI |

### API Endpoints
| Endpoint | Purpose |
|----------|---------|
| `/api/v1/seasonal-trigger-dates/` | CRUD for variable holiday dates |
| `/api/v1/email-sequences/` | List/manage sequences |
| `/api/v1/sequence-steps/` | Manage sequence steps |
| `/api/v1/email-templates/` | List/manage templates |

### Country Names (must match exactly)
- Thailand, Singapore, Malaysia, Hong Kong, China, Taiwan, Vietnam
- Japan, South Korea, Philippines, Indonesia, Myanmar, Cambodia, Laos, Brunei
- India, Nepal, Sri Lanka, Mauritius, Fiji
- UAE, Saudi Arabia, Qatar, Kuwait, Bahrain, Oman, Jordan, Lebanon, Egypt, Iraq, Iran, Turkey, Pakistan, Bangladesh

---

## Session 4: Granular Contact Email Preferences (January 4, 2026)

### Feature Overview

Added per-contact, per-email-type opt-out controls. Previously, contacts could only opt out of ALL emails (`receives_notifications=False`). Now they can selectively opt out of specific email types while still receiving others.

### New Contact Fields

| Field | Default | Controls |
|-------|---------|----------|
| `receives_renewal_emails` | `True` | Contract renewal reminders (30/14/7 days) |
| `receives_seasonal_emails` | `True` | Seasonal/holiday campaign emails |
| `receives_payment_emails` | `True` | Payment reminder emails |
| `receives_quarterly_emails` | `True` | Quarterly check-in emails |

### How It Works

1. **Master switch**: `receives_notifications` must be `True` for ANY emails
2. **Granular control**: Each preference field controls a specific email type
3. **AutoEnrollmentService** checks both the master switch AND the specific preference before enrolling

### Files Modified

| File | Changes |
|------|---------|
| `crm_app/models.py` | Added 4 boolean fields to Contact model |
| `crm_app/migrations/0044_contact_email_preferences.py` | Migration for new fields |
| `crm_app/serializers.py` | Added fields to ContactSerializer |
| `crm_app/services/auto_enrollment_service.py` | Updated all 4 trigger methods to check specific preferences |
| `bmasia-crm-frontend/src/types/index.ts` | Added fields to Contact interface |
| `bmasia-crm-frontend/src/components/ContactForm.tsx` | Added "Email Preferences" section with 4 toggles |

### Frontend UI

New "Email Preferences" section in ContactForm with 4 toggle switches:
- Contract Renewal Reminders
- Payment Reminders
- Quarterly Check-ins
- Seasonal Campaigns

### Git Commit

```
94d72678 Feature: Granular email preferences for contacts
```

### Use Case Example

**Scenario**: Hotel has 3 contacts:
- GM (receives all emails)
- Finance Manager (only payment emails)
- Marketing Manager (only seasonal campaigns)

**Solution**:
1. Edit Finance Manager contact → turn OFF renewal, seasonal, quarterly toggles
2. Edit Marketing Manager contact → turn OFF renewal, payment, quarterly toggles
3. GM keeps all toggles ON

Now the automation system automatically routes the right emails to the right contacts.
