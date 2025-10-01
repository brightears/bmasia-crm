# Generated manually for database performance optimization

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0020a_enable_pg_trgm_extension'),
    ]

    operations = [
        # Add missing indexes for frequently queried fields

        # User model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_user_role_idx ON auth_user (role);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_user_role_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_user_is_active_idx ON auth_user (is_active);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_user_is_active_idx;"
        ),

        # Company model additional indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_company_is_active_idx ON crm_app_company (is_active);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_company_is_active_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_company_soundtrack_account_idx ON crm_app_company (soundtrack_account_id) WHERE soundtrack_account_id IS NOT NULL AND soundtrack_account_id != '';",
            reverse_sql="DROP INDEX IF EXISTS crm_app_company_soundtrack_account_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_company_created_at_idx ON crm_app_company (created_at);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_company_created_at_idx;"
        ),

        # Contact model additional indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_contact_is_active_idx ON crm_app_contact (is_active);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_contact_is_active_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_contact_contact_type_idx ON crm_app_contact (contact_type);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_contact_contact_type_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_contact_receives_notifications_idx ON crm_app_contact (receives_notifications);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_contact_receives_notifications_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_contact_unsubscribed_idx ON crm_app_contact (unsubscribed);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_contact_unsubscribed_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_contact_company_active_idx ON crm_app_contact (company_id, is_active, receives_notifications, unsubscribed);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_contact_company_active_idx;"
        ),

        # Note model additional indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_note_author_idx ON crm_app_note (author_id);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_note_author_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_note_contact_idx ON crm_app_note (contact_id);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_note_contact_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_note_is_private_idx ON crm_app_note (is_private);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_note_is_private_idx;"
        ),

        # Task model additional indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_task_created_by_idx ON crm_app_task (created_by_id);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_task_created_by_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_task_due_date_idx ON crm_app_task (due_date);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_task_due_date_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_task_department_idx ON crm_app_task (department);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_task_department_idx;"
        ),

        # Opportunity model additional indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_opportunity_owner_idx ON crm_app_opportunity (owner_id);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_opportunity_owner_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_opportunity_lead_source_idx ON crm_app_opportunity (lead_source);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_opportunity_lead_source_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_opportunity_follow_up_date_idx ON crm_app_opportunity (follow_up_date);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_opportunity_follow_up_date_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_opportunity_created_at_idx ON crm_app_opportunity (created_at);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_opportunity_created_at_idx;"
        ),

        # OpportunityActivity model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_opportunityactivity_opportunity_idx ON crm_app_opportunityactivity (opportunity_id);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_opportunityactivity_opportunity_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_opportunityactivity_user_idx ON crm_app_opportunityactivity (user_id);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_opportunityactivity_user_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_opportunityactivity_activity_type_idx ON crm_app_opportunityactivity (activity_type);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_opportunityactivity_activity_type_idx;"
        ),

        # Contract model additional indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_contract_opportunity_idx ON crm_app_contract (opportunity_id);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_contract_opportunity_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_contract_service_type_idx ON crm_app_contract (service_type);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_contract_service_type_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_contract_contract_type_idx ON crm_app_contract (contract_type);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_contract_contract_type_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_contract_start_date_idx ON crm_app_contract (start_date);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_contract_start_date_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_contract_currency_idx ON crm_app_contract (currency);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_contract_currency_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_contract_expiring_soon_idx ON crm_app_contract (end_date, is_active) WHERE is_active = true;",
            reverse_sql="DROP INDEX IF EXISTS crm_app_contract_expiring_soon_idx;"
        ),

        # Invoice model additional indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_invoice_paid_date_idx ON crm_app_invoice (paid_date);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_invoice_paid_date_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_invoice_currency_idx ON crm_app_invoice (currency);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_invoice_currency_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_invoice_overdue_idx ON crm_app_invoice (due_date, status) WHERE status != 'Paid';",
            reverse_sql="DROP INDEX IF EXISTS crm_app_invoice_overdue_idx;"
        ),

        # Zone model additional indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_zone_platform_status_idx ON crm_app_zone (platform, status);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_zone_platform_status_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_zone_soundtrack_zone_id_idx ON crm_app_zone (soundtrack_zone_id) WHERE soundtrack_zone_id IS NOT NULL AND soundtrack_zone_id != '';",
            reverse_sql="DROP INDEX IF EXISTS crm_app_zone_soundtrack_zone_id_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_zone_last_api_sync_idx ON crm_app_zone (last_api_sync);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_zone_last_api_sync_idx;"
        ),

        # AuditLog model additional indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_auditlog_ip_address_idx ON crm_app_auditlog (ip_address);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_auditlog_ip_address_idx;"
        ),

        # EmailTemplate model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_emailtemplate_department_idx ON crm_app_emailtemplate (department);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_emailtemplate_department_idx;"
        ),

        # EmailLog model additional indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_emaillog_to_email_idx ON crm_app_emaillog (to_email);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_emaillog_to_email_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_emaillog_template_used_idx ON crm_app_emaillog (template_used_id);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_emaillog_template_used_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_emaillog_sent_at_idx ON crm_app_emaillog (sent_at);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_emaillog_sent_at_idx;"
        ),

        # EmailCampaign model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_emailcampaign_start_date_idx ON crm_app_emailcampaign (start_date);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_emailcampaign_start_date_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_emailcampaign_end_date_idx ON crm_app_emailcampaign (end_date);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_emailcampaign_end_date_idx;"
        ),

        # DocumentAttachment model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_documentattachment_contract_idx ON crm_app_documentattachment (contract_id);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_documentattachment_contract_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_documentattachment_invoice_idx ON crm_app_documentattachment (invoice_id);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_documentattachment_invoice_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_documentattachment_is_active_idx ON crm_app_documentattachment (is_active);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_documentattachment_is_active_idx;"
        ),

        # Composite indexes for complex queries
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_company_industry_country_idx ON crm_app_company (industry, country);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_company_industry_country_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_task_assigned_due_status_idx ON crm_app_task (assigned_to_id, due_date, status);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_task_assigned_due_status_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_contract_company_status_end_idx ON crm_app_contract (company_id, status, end_date);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_contract_company_status_end_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_invoice_contract_status_due_idx ON crm_app_invoice (contract_id, status, due_date);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_invoice_contract_status_due_idx;"
        ),

        # Full-text search indexes for PostgreSQL (if using PostgreSQL)
        # These will be ignored on other databases
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_company_name_trgm_idx ON crm_app_company USING gin (name gin_trgm_ops);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_company_name_trgm_idx;",
            state_operations=[]
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_contact_name_trgm_idx ON crm_app_contact USING gin (name gin_trgm_ops);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_contact_name_trgm_idx;",
            state_operations=[]
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS crm_app_contact_email_trgm_idx ON crm_app_contact USING gin (email gin_trgm_ops);",
            reverse_sql="DROP INDEX IF EXISTS crm_app_contact_email_trgm_idx;",
            state_operations=[]
        ),
    ]