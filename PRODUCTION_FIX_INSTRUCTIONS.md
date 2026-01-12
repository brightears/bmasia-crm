# Production Database Fix: Adding legal_entity_name Column

## Problem
The migration file `0024_add_legal_entity_name_to_company.py` was created but never executed on production, causing a 500 error:
```
column crm_app_company.legal_entity_name does not exist
```

## Solution Options

### Option 1: Use Render Dashboard (Recommended)

1. **Access Render Dashboard**
   - Go to https://dashboard.render.com
   - Navigate to your PostgreSQL database service
   - Click on "Connect" → "PSQL Command"

2. **Connect to Database**
   - Copy the PSQL command provided
   - Run it in your terminal, or use the web shell if available

3. **Execute SQL**
   ```sql
   -- Add the missing column
   ALTER TABLE crm_app_company 
   ADD COLUMN IF NOT EXISTS legal_entity_name VARCHAR(255) DEFAULT '' NOT NULL;

   -- Mark migration as applied
   INSERT INTO django_migrations (app, name, applied) 
   VALUES ('crm_app', '0024_add_legal_entity_name_to_company', NOW()) 
   ON CONFLICT DO NOTHING;
   ```

4. **Verify**
   ```sql
   -- Check column exists
   SELECT column_name, data_type, character_maximum_length
   FROM information_schema.columns 
   WHERE table_name='crm_app_company' 
   AND column_name='legal_entity_name';

   -- Check migration is recorded
   SELECT id, applied 
   FROM django_migrations 
   WHERE name='0024_add_legal_entity_name_to_company';
   ```

### Option 2: Use Render Shell (If Available)

1. **Access your web service shell**
   - Go to Render Dashboard → Your Web Service
   - Click on "Shell" tab

2. **Run Django migrate command**
   ```bash
   python manage.py migrate crm_app 0024
   ```

### Option 3: Deploy a Temporary Migration Runner

1. **Create a temporary endpoint** in your Django app that runs migrations
2. **Deploy** the change
3. **Access** the endpoint via browser or curl
4. **Remove** the endpoint after migration completes

## Database Credentials

- **Host**: dpg-d3cbikd6ubrc73el0ke0-a.singapore-postgres.render.com
- **Port**: 5432
- **Database**: bmasia_crm
- **User**: bmasia_crm_user
- **Password**: IUEmiG1IFKkzZOsR9HBpYoRGM7zhoI7v

## PSQL Connection String

```bash
psql postgresql://bmasia_crm_user:IUEmiG1IFKkzZOsR9HBpYoRGM7zhoI7v@dpg-d3cbikd6ubrc73el0ke0-a.singapore-postgres.render.com:5432/bmasia_crm?sslmode=require
```

## SQL to Execute

```sql
-- Begin transaction
BEGIN;

-- Add the legal_entity_name column
ALTER TABLE crm_app_company 
ADD COLUMN IF NOT EXISTS legal_entity_name VARCHAR(255) DEFAULT '' NOT NULL;

-- Record the migration
INSERT INTO django_migrations (app, name, applied) 
VALUES ('crm_app', '0024_add_legal_entity_name_to_company', NOW()) 
ON CONFLICT DO NOTHING;

-- Verify changes
SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name='crm_app_company' 
AND column_name='legal_entity_name';

SELECT id, app, name, applied 
FROM django_migrations 
WHERE name='0024_add_legal_entity_name_to_company';

-- If everything looks good, commit
COMMIT;

-- If something went wrong, rollback
-- ROLLBACK;
```

## Verification After Fix

After applying the fix, verify the application is working:

1. **Access the production site**: https://bmasia-crm.onrender.com
2. **Try accessing** a page that uses the Company model
3. **Check Render logs** for any remaining errors

## Rollback (If Needed)

If something goes wrong:

```sql
BEGIN;

-- Remove the column
ALTER TABLE crm_app_company 
DROP COLUMN IF EXISTS legal_entity_name;

-- Remove migration record
DELETE FROM django_migrations 
WHERE app='crm_app' 
AND name='0024_add_legal_entity_name_to_company';

COMMIT;
```

## Notes

- The local connection attempts failed due to SSL/network restrictions
- Direct database access from Render Dashboard is the most reliable method
- The migration file exists in the codebase at: `crm_app/migrations/0024_add_legal_entity_name_to_company.py`
- After fixing, the 500 error should be resolved immediately (no restart needed for schema changes)
