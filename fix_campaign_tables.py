#!/usr/bin/env python
"""
Standalone script to ensure campaign tables exist before migrations run.
This fixes the issue where migration 0027 tries to rename a table that doesn't exist.
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bmasia_crm.settings')
django.setup()

from django.db import connection

def fix_campaign_tables():
    print("=" * 70)
    print("FIXING CAMPAIGN TABLES")
    print("=" * 70)

    with connection.cursor() as cursor:
        # Check if old table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'crm_app_emailcampaign'
            )
        """)
        old_table_exists = cursor.fetchone()[0]

        # Check if new table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'crm_app_email_campaign'
            )
        """)
        new_table_exists = cursor.fetchone()[0]

        print(f"Old table (crm_app_emailcampaign): {old_table_exists}")
        print(f"New table (crm_app_email_campaign): {new_table_exists}")

        # Scenario 1: Old table exists - this is normal, migration 0027 will rename it
        if old_table_exists and not new_table_exists:
            print("✓ Old table exists. Migration 0027 will rename it.")
            return

        # Scenario 2: New table already exists - already fixed
        if new_table_exists:
            print("✓ New table already exists. No action needed.")
            return

        # Scenario 3: Neither table exists - CREATE IT
        if not old_table_exists and not new_table_exists:
            print("⚠ No EmailCampaign table exists!")
            print("Creating table with new name...")

            try:
                # Create the EmailCampaign table with the NEW name
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS crm_app_email_campaign (
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
                        company_id UUID
                    )
                """)
                print("✓ Created crm_app_email_campaign table")

                # Add foreign key constraint
                cursor.execute("""
                    ALTER TABLE crm_app_email_campaign
                    ADD CONSTRAINT crm_app_email_campaign_company_id_fkey
                    FOREIGN KEY (company_id)
                    REFERENCES crm_app_company(id)
                    ON DELETE CASCADE
                    DEFERRABLE INITIALLY DEFERRED
                """)
                print("✓ Added foreign key constraint")

                # Create basic index
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS crm_app_ema_company_c5ff78_idx
                    ON crm_app_email_campaign (company_id)
                """)
                print("✓ Created index")

                # Mark migration 0012 as applied (since we manually created the table)
                cursor.execute("""
                    INSERT INTO django_migrations (app, name, applied)
                    VALUES ('crm_app', '0012_emailcampaign_emaillog_emailtemplate_and_more', NOW())
                    ON CONFLICT DO NOTHING
                """)
                print("✓ Marked migration 0012 as applied")

                print("✓ SUCCESS: Campaign table created")
                print("Migration 0027 will now add the remaining fields")

            except Exception as e:
                print(f"✗ ERROR: {e}")
                raise

    print("=" * 70)

if __name__ == '__main__':
    fix_campaign_tables()
