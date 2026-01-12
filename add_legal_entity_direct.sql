-- Add legal_entity_name column to production database
ALTER TABLE crm_app_company
ADD COLUMN IF NOT EXISTS legal_entity_name VARCHAR(255) NOT NULL DEFAULT '';

-- Mark migration as applied
INSERT INTO django_migrations (app, name, applied)
VALUES ('crm_app', '0024_add_legal_entity_name_to_company', NOW())
ON CONFLICT DO NOTHING;

-- Verify column was added
SELECT column_name, data_type, character_maximum_length, is_nullable
FROM information_schema.columns
WHERE table_name = 'crm_app_company' AND column_name = 'legal_entity_name';
