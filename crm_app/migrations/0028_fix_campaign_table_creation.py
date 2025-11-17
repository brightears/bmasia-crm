# Generated manually to fix campaign table issue
from django.db import migrations, connection


def check_and_create_campaign_table(apps, schema_editor):
    """
    Check if campaign tables exist and create them if needed.
    This fixes the issue where migration 0027 tries to rename a non-existent table.
    """
    with connection.cursor() as cursor:
        # Check if new table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'crm_app_email_campaign'
            )
        """)
        new_table_exists = cursor.fetchone()[0]

        # Check if old table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'crm_app_emailcampaign'
            )
        """)
        old_table_exists = cursor.fetchone()[0]

        print(f"Old table exists: {old_table_exists}, New table exists: {new_table_exists}")

        # If new table already exists, we're done
        if new_table_exists:
            print("New campaign table already exists, skipping creation")
            return

        # If old table exists, rename it (this is what migration 0027 was supposed to do)
        if old_table_exists:
            print("Renaming old campaign table to new name")
            cursor.execute("ALTER TABLE crm_app_emailcampaign RENAME TO crm_app_email_campaign")
            return

        # Neither table exists - create it fresh with the correct name
        print("Creating campaign table from scratch")
        cursor.execute("""
            CREATE TABLE crm_app_email_campaign (
                id UUID PRIMARY KEY,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
                name VARCHAR(100) NOT NULL,
                campaign_type VARCHAR(20) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT true,
                start_date DATE,
                end_date DATE,
                emails_sent INTEGER NOT NULL DEFAULT 0,
                last_email_sent TIMESTAMP WITH TIME ZONE,
                stop_on_reply BOOLEAN NOT NULL DEFAULT true,
                replied BOOLEAN NOT NULL DEFAULT false,
                company_id UUID,
                CONSTRAINT crm_app_email_campaign_company_id_fkey
                    FOREIGN KEY (company_id)
                    REFERENCES crm_app_company(id)
                    ON DELETE CASCADE
                    DEFERRABLE INITIALLY DEFERRED
            )
        """)

        cursor.execute("""
            CREATE INDEX crm_app_ema_company_c5ff78_idx
            ON crm_app_email_campaign (company_id)
        """)

        print("Campaign table created successfully")


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0027_campaignrecipient_and_more'),
    ]

    operations = [
        migrations.RunPython(check_and_create_campaign_table, reverse_code=migrations.RunPython.noop),
    ]
