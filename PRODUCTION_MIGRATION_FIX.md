# Production Migration Fix - Manual Steps Required

## Problem
- Production database has campaign tables created manually via Render shell
- Migration 0027 tries to create those tables → fails because they already exist
- Migration 0028 can't run because 0027 failed
- Deployment status: `update_failed`

## Solution
Mark migrations 0027 and 0028 as applied WITHOUT running them (since tables exist).

## Step-by-Step Instructions

### 1. Access Render Shell
1. Go to: https://dashboard.render.com/
2. Navigate to: **bmasia-crm** service (backend)
3. Click: **Shell** tab

### 2. Upload Migration Script
In your local terminal, copy the script to clipboard:
```bash
cat mark_migrations_applied.py
```

Then in Render Shell:
```bash
cat > mark_migrations_applied.py << 'EOF'
# [PASTE THE ENTIRE SCRIPT HERE]
EOF
```

### 3. Run Migration Script
```bash
python mark_migrations_applied.py
```

**Expected output:**
```
============================================================
MARKING MIGRATIONS AS APPLIED (NO SQL EXECUTION)
============================================================
Current migrations (last 5):
  - crm_app.0026_merge_20251114_1416
  - crm_app.0025_alter_emailtemplate_body_html_and_more
  ...

Marking migrations as applied:
  ✓ 0027_campaignrecipient_alter_emailcampaign_options_and_more - Marked as applied
  ✓ 0028_alter_emailcampaign_table - Marked as applied

Verifying migration state:
  - crm_app.0028_alter_emailcampaign_table
  - crm_app.0027_campaignrecipient_alter_emailcampaign_options_and_more
  - crm_app.0026_merge_20251114_1416
  ...

✅ Done! Migrations 0027 and 0028 marked as applied.
   Tables were created manually via Render shell.
```

### 4. Verify Migration State
```bash
python manage.py showmigrations crm_app
```

**Expected output** (last few lines):
```
[X] 0026_merge_20251114_1416
[X] 0027_campaignrecipient_alter_emailcampaign_options_and_more
[X] 0028_alter_emailcampaign_table
```

### 5. Trigger New Deployment
Now that migrations are synced, trigger a new deployment via local terminal:

```bash
curl -X POST -H "Authorization: Bearer rnd_QAJKR0jggzsxSLOCx3HfovreCzOd" \
  https://api.render.com/v1/services/srv-d13ukt8gjchc73fjat0g/deploys
```

### 6. Monitor Deployment
Check status every 15-30 seconds:
```bash
curl -H "Authorization: Bearer rnd_QAJKR0jggzsxSLOCx3HfovreCzOd" \
  "https://api.render.com/v1/services/srv-d13ukt8gjchc73fjat0g/deploys?limit=1"
```

**Expected status progression:**
- `build_in_progress` → `build_succeeded` → `update_in_progress` → `live`

### 7. Test Campaigns
1. Go to: https://bmasia-crm-frontend.onrender.com/campaigns
2. Create a new campaign
3. Verify "Review & Send" step works (no 500 error)

## What This Does

The script:
1. Connects to production PostgreSQL database
2. Inserts records into `django_migrations` table for migrations 0027 and 0028
3. Does NOT execute any migration SQL (tables already exist)
4. Syncs Django migration state with actual database state

## Why Manual Steps Required

Render's deployment process runs migrations automatically, but we need to mark them as applied BEFORE the deployment runs. This requires manual intervention via Render Shell.

## Alternative (If Script Upload Fails)

If you can't upload the script to Render Shell, use direct SQL:

```bash
python manage.py dbshell
```

Then paste:
```sql
INSERT INTO django_migrations (app, name, applied)
VALUES 
  ('crm_app', '0027_campaignrecipient_alter_emailcampaign_options_and_more', NOW()),
  ('crm_app', '0028_alter_emailcampaign_table', NOW())
ON CONFLICT DO NOTHING;
```

Exit with `\q`, then verify:
```bash
python manage.py showmigrations crm_app
```

## Files Committed
- Commit hash: 7640376
- Migration 0027: Fixed dependency (0026_merge)
- Migration 0028: State-only (EmailCampaign table name)
- mark_migrations_applied.py: Helper script for manual execution

## Next Steps After Successful Deployment
1. ✅ Verify campaigns work end-to-end
2. Clean up troubleshooting files (optional)
3. Document migration state in SESSION_CHECKPOINT
