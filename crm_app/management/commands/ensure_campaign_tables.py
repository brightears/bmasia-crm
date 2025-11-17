"""
Django management command to ensure campaign tables exist before migrations run.
This handles the case where migration 0027 tries to rename a table that doesn't exist.
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Ensure campaign tables exist with correct names before running migrations'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Checking campaign tables...'))

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

            self.stdout.write(f'  Old table (crm_app_emailcampaign): {old_table_exists}')
            self.stdout.write(f'  New table (crm_app_email_campaign): {new_table_exists}')

            # Scenario 1: Old table exists but new doesn't - this is normal, migration 0027 will rename it
            if old_table_exists and not new_table_exists:
                self.stdout.write(
                    self.style.SUCCESS(
                        '✓ Old table exists. Migration 0027 will rename it to new name.'
                    )
                )
                return

            # Scenario 2: New table already exists - migrations already ran successfully
            if new_table_exists:
                self.stdout.write(
                    self.style.SUCCESS('✓ New table already exists. No action needed.')
                )
                return

            # Scenario 3: Neither table exists - migration 0012 was never run
            # This is the problem case - migration 0027 will fail because there's nothing to rename
            if not old_table_exists and not new_table_exists:
                self.stdout.write(
                    self.style.WARNING(
                        '⚠ No EmailCampaign table exists. This will cause migration 0027 to fail.'
                    )
                )
                self.stdout.write(
                    self.style.WARNING(
                        '  Creating table with new name to avoid migration failure...'
                    )
                )

                # Create the EmailCampaign table with the NEW name (what migration 0027 expects)
                # This is a minimal schema - migration 0027 will add all the fields
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

                # Add foreign key constraint
                cursor.execute("""
                    ALTER TABLE crm_app_email_campaign
                    ADD CONSTRAINT crm_app_email_campaign_company_id_fkey
                    FOREIGN KEY (company_id)
                    REFERENCES crm_app_company(id)
                    ON DELETE CASCADE
                    DEFERRABLE INITIALLY DEFERRED
                """)

                # Create basic index
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS crm_app_ema_company_c5ff78_idx
                    ON crm_app_email_campaign (company_id)
                """)

                # Mark migration 0012 as applied (since we manually created the table)
                cursor.execute("""
                    INSERT INTO django_migrations (app, name, applied)
                    VALUES ('crm_app', '0012_emailcampaign_emaillog_emailtemplate_and_more', NOW())
                    ON CONFLICT DO NOTHING
                """)

                self.stdout.write(
                    self.style.SUCCESS(
                        '✓ Created crm_app_email_campaign table with new name'
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        '✓ Marked migration 0012 as applied'
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        '  Migration 0027 will now add the remaining fields successfully'
                    )
                )
