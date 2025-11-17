# Campaign Table Fix Summary

## Problem
The `/campaigns` page shows 500 error: `relation "crm_app_email_campaign" does not exist`

## Root Cause
Complex migration dependency chain with conflicts:
- Two `0025` migrations created (merge conflict)
- Migration `0027` tries to alter a table that may not exist
- Production database likely in inconsistent state from failed migrations

## Migrations Created
1. **0026_merge** - Merges two 0025 branches
2. **0026a_create_campaign_table_if_missing** - Creates base table
3. **0027_campaignrecipient_alter_emailcampaign_options_and_more** - Modified to use RunPython
4. **0028_fix_campaign_table_creation** - First fix attempt
5. **0029_ensure_campaign_table** - Second fix attempt
6. **0030_final_campaign_table_fix** - Comprehensive fix

## Current Status
All deployments failing. Likely issues:
1. Previous failed migrations marked as applied in django_migrations table
2. Partial table state (some columns but not all)
3. Migration dependency chain broken

## Recommended Solution
Need to:
1. Fake-apply problematic migrations in production: `python manage.py migrate crm_app 0027 --fake`
2. Then run migration 0030 which creates table if missing
3. OR: Connect directly to production DB and manually create the table

## Files Modified
- `/Users/benorbe/Library/Mobile Documents/com~apple~CloudDocs/Documents/Coding Projects/BMAsia CRM/crm_app/migrations/0025_alter_emailtemplate_body_html_and_more.py`
- `/Users/benorbe/Library/Mobile Documents/com~apple~CloudDocs/Documents/Coding Projects/BMAsia CRM/crm_app/migrations/0026_merge_20251114_1416.py`
- `/Users/benorbe/Library/Mobile Documents/com~apple~CloudDocs/Documents/Coding Projects/BMAsia CRM/crm_app/migrations/0026a_create_campaign_table_if_missing.py`
- `/Users/benorbe/Library/Mobile Documents/com~apple~CloudDocs/Documents/Coding Projects/BMAsia CRM/crm_app/migrations/0027_campaignrecipient_alter_emailcampaign_options_and_more.py`
- `/Users/benorbe/Library/Mobile Documents/com~apple~CloudDocs/Documents/Coding Projects/BMAsia CRM/crm_app/migrations/0028_fix_campaign_table_creation.py`
- `/Users/benorbe/Library/Mobile Documents/com~apple~CloudDocs/Documents/Coding Projects/BMAsia CRM/crm_app/migrations/0029_ensure_campaign_table.py`
- `/Users/benorbe/Library/Mobile Documents/com~apple~CloudDocs/Documents/Coding Projects/BMAsia CRM/crm_app/migrations/0030_final_campaign_table_fix.py`

## EmailCampaign Model
Location: `crm_app/models.py` line 1023
Table name: `crm_app_email_campaign` (via Meta.db_table)
Fields: 29 total (id, timestamps, campaign fields, analytics, legacy fields)

## Next Steps
1. Need shell access to production or manual SQL execution capability
2. Check actual migration status with: `python manage.py showmigrations crm_app`
3. Check table existence with diagnostic script
4. May need to fake-apply migrations and manually create table
