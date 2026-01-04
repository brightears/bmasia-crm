# Session Checkpoint: Extended Email Automation System
**Date**: January 4, 2026
**Status**: COMPLETE - Deployed to Production

---

## Summary

Implemented extended email automation with:
1. Opt-out enforcement in AutoEnrollmentService
2. Quarterly check-ins based on contract START date (90/180/270/360 days)
3. Seasonal campaigns by country
4. SeasonalTriggerDate model for variable holiday dates
5. Company-level seasonal opt-out checkbox

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

1. **SeasonalTriggerDate not visible in admin** - User can't see it, need to scroll down OR it wasn't registered properly. Check admin.py registration.

2. **User wants frontend date setting** - Instead of Django admin, add a Settings page in React frontend to set variable holiday dates.

3. **Update country mapping for CNY** - Should include more Asian countries:
   - Current: Thailand, Singapore, Malaysia, Hong Kong, China, Taiwan, Vietnam
   - Add: Japan, South Korea, Philippines, Indonesia, Myanmar, Cambodia, Laos, Brunei

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

## Email Templates (17 total in production)

- 7 seasonal (Christmas, CNY, Valentine's, Songkran, Loy Krathong, Ramadan, Singapore ND)
- 4 renewal (30, 14, 7 days, urgent)
- 3 payment (7, 14 days overdue, overdue)
- 1 quarterly check-in
- 1 welcome
- 1 contract signed
