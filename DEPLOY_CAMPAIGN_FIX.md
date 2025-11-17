# Deploy Campaign Table Fix - Instructions

## Problem
The `/campaigns` page returns 500 error: `relation "crm_app_email_campaign" does not exist`

## Solution
Use the Django management command to create the table directly, bypassing migrations.

## Deployment Steps

### 1. Deploy Latest Code
```bash
curl -X POST -H "Authorization: Bearer rnd_QAJKR0jggzsxSLOCx3HfovreCzOd" \
  https://api.render.com/v1/services/srv-d13ukt8gjchc73fjat0g/deploys
```

### 2. Access Render Shell
Log into Render dashboard: https://dashboard.render.com/
Navigate to: bmasia-crm service
Click: "Shell" tab

### 3. Run Management Command
In the Render shell, execute:
```bash
python manage.py create_campaign_table
```

Expected output:
```
Checking campaign table...
Creating crm_app_email_campaign table...
Adding foreign keys...
Creating indexes...
✓ Successfully created crm_app_email_campaign table
  29 columns + 4 indexes + 3 foreign keys
```

### 4. Mark Migrations as Applied
Still in the Render shell:
```bash
python manage.py migrate crm_app --fake
```

This marks all pending migrations as applied without running them (since we created the table manually).

### 5. Verify
Visit: https://bmasia-crm-frontend.onrender.com/campaigns

The page should now load without the 500 error.

## Alternative: SQL Direct Execution

If shell access is not available, execute this SQL directly in the database:

```sql
CREATE TABLE IF NOT EXISTS crm_app_email_campaign (
    id UUID PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    name VARCHAR(100) NOT NULL,
    campaign_type VARCHAR(20) NOT NULL,
    subject VARCHAR(200) DEFAULT '' NOT NULL,
    target_audience JSONB NULL,
    audience_count INTEGER DEFAULT 0 NOT NULL,
    scheduled_send_date TIMESTAMP WITH TIME ZONE NULL,
    actual_send_date TIMESTAMP WITH TIME ZONE NULL,
    status VARCHAR(20) DEFAULT 'draft' NOT NULL,
    send_immediately BOOLEAN DEFAULT FALSE NOT NULL,
    sender_email VARCHAR(254) DEFAULT '' NOT NULL,
    reply_to_email VARCHAR(254) NULL,
    total_sent INTEGER DEFAULT 0 NOT NULL,
    total_delivered INTEGER DEFAULT 0 NOT NULL,
    total_bounced INTEGER DEFAULT 0 NOT NULL,
    total_opened INTEGER DEFAULT 0 NOT NULL,
    total_clicked INTEGER DEFAULT 0 NOT NULL,
    total_unsubscribed INTEGER DEFAULT 0 NOT NULL,
    total_complained INTEGER DEFAULT 0 NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    start_date DATE NULL,
    end_date DATE NULL,
    emails_sent INTEGER DEFAULT 0 NOT NULL,
    last_email_sent TIMESTAMP WITH TIME ZONE NULL,
    stop_on_reply BOOLEAN DEFAULT TRUE NOT NULL,
    replied BOOLEAN DEFAULT FALSE NOT NULL,
    company_id UUID NULL REFERENCES crm_app_company(id) ON DELETE CASCADE,
    contract_id UUID NULL REFERENCES crm_app_contract(id) ON DELETE SET NULL,
    template_id UUID NULL REFERENCES crm_app_emailtemplate(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS crm_app_ema_status_e2260a_idx ON crm_app_email_campaign (status, created_at DESC);
CREATE INDEX IF NOT EXISTS crm_app_ema_campaig_62ea85_idx ON crm_app_email_campaign (campaign_type, status);
CREATE INDEX IF NOT EXISTS crm_app_ema_schedul_fd708b_idx ON crm_app_email_campaign (scheduled_send_date, status);
CREATE INDEX IF NOT EXISTS crm_app_ema_company_99dbe1_idx ON crm_app_email_campaign (company_id, is_active);
```

## Files Changed
- `crm_app/management/commands/create_campaign_table.py` - New management command
- Multiple migration files (0026-0030) - Migration fixes
- `CAMPAIGN_TABLE_FIX_SUMMARY.md` - Technical summary
- `DEPLOY_CAMPAIGN_FIX.md` - This file

## Rollback
If issues occur, the table can be dropped:
```sql
DROP TABLE IF EXISTS crm_app_email_campaign CASCADE;
```

Then revert to commit before the campaign feature was added.
