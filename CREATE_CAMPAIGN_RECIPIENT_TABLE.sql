-- =====================================================
-- CREATE CAMPAIGN RECIPIENT TABLE
-- Execute this via Render Shell: python manage.py dbshell
-- =====================================================

-- Step 1: Create the table
CREATE TABLE crm_app_campaign_recipient (
    id UUID PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    campaign_id UUID NOT NULL,
    contact_id UUID NOT NULL,
    email_log_id UUID NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    sent_at TIMESTAMP WITH TIME ZONE NULL,
    delivered_at TIMESTAMP WITH TIME ZONE NULL,
    opened_at TIMESTAMP WITH TIME ZONE NULL,
    clicked_at TIMESTAMP WITH TIME ZONE NULL,
    bounced_at TIMESTAMP WITH TIME ZONE NULL,
    failed_at TIMESTAMP WITH TIME ZONE NULL,
    error_message TEXT NOT NULL DEFAULT '',
    CONSTRAINT crm_app_campaign_recipient_campaign_id_fk
        FOREIGN KEY (campaign_id) REFERENCES crm_app_email_campaign(id) ON DELETE CASCADE,
    CONSTRAINT crm_app_campaign_recipient_contact_id_fk
        FOREIGN KEY (contact_id) REFERENCES crm_app_contact(id) ON DELETE CASCADE,
    CONSTRAINT crm_app_campaign_recipient_email_log_id_fk
        FOREIGN KEY (email_log_id) REFERENCES crm_app_emaillog(id) ON DELETE SET NULL,
    CONSTRAINT crm_app_campaign_recipient_unique_campaign_contact
        UNIQUE (campaign_id, contact_id)
);

-- Step 2: Create indexes for performance
CREATE INDEX crm_app_campaign_recipient_campaign_status_idx
    ON crm_app_campaign_recipient (campaign_id, status);

CREATE INDEX crm_app_campaign_recipient_contact_status_idx
    ON crm_app_campaign_recipient (contact_id, status);

CREATE INDEX crm_app_campaign_recipient_sent_at_idx
    ON crm_app_campaign_recipient (sent_at);

CREATE INDEX crm_app_campaign_recipient_status_sent_at_idx
    ON crm_app_campaign_recipient (status, sent_at DESC);

-- Step 3: Verify table creation (run these to confirm)
-- SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'crm_app_campaign_recipient';
-- SELECT indexname FROM pg_indexes WHERE tablename = 'crm_app_campaign_recipient';
