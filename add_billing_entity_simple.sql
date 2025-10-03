-- Simple SQL script to manually add billing_entity column
-- Run this via psql or Render Shell if automated migration fails

-- Add the column
ALTER TABLE crm_app_company
ADD COLUMN IF NOT EXISTS billing_entity VARCHAR(50) NOT NULL DEFAULT 'BMAsia Limited';

-- Add check constraint
ALTER TABLE crm_app_company
DROP CONSTRAINT IF EXISTS crm_app_company_billing_entity_check;

ALTER TABLE crm_app_company
ADD CONSTRAINT crm_app_company_billing_entity_check
CHECK (billing_entity IN ('BMAsia Limited', 'BMAsia (Thailand) Co., Ltd.'));

-- Mark migration as applied in Django's migration table
INSERT INTO django_migrations (app, name, applied)
VALUES ('crm_app', '0023_company_billing_entity', NOW())
ON CONFLICT DO NOTHING;
