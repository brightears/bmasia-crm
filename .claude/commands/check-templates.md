# Check Email Templates

Verify all email templates exist and are properly configured in production.

## Steps
1. Authenticate to API
2. Fetch all email templates
3. Verify against expected template list
4. Report status for each template

## Expected Templates (17 total)

### Renewal Templates (4)
- renewal_30_days
- renewal_14_days
- renewal_7_days
- renewal_urgent

### Payment Templates (3)
- payment_reminder_7_days
- payment_reminder_14_days
- payment_overdue

### Seasonal Templates (7)
- seasonal_christmas
- seasonal_newyear
- seasonal_valentines
- seasonal_songkran
- seasonal_loy_krathong
- seasonal_ramadan
- seasonal_singapore_national_day

### Other Templates (3)
- quarterly_checkin
- welcome
- contract_signed

## Verification Checks
For each template verify:
1. Template exists
2. Has subject line (> 5 chars)
3. Has body content (> 100 chars)
4. Has correct department assigned
5. Is active

## Department Assignments
| Template Type | Expected Department |
|--------------|---------------------|
| seasonal_* | Music |
| renewal_*, quarterly_checkin | Admin |
| payment_* | Finance |
| welcome, contract_signed | Sales |

## Report Format
```
Template Status Report
======================
✓ renewal_30_days - Admin - 3126 chars
✓ seasonal_christmas - Music - 2500 chars
✗ missing_template - NOT FOUND
```
