"""
Django management command to diagnose campaign table status in production database.
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


class Command(BaseCommand):
    help = 'Check campaign table status and applied migrations'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('CAMPAIGN TABLES DIAGNOSTIC'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

        # Check applied migrations
        self.stdout.write('\n' + self.style.HTTP_INFO('1. APPLIED MIGRATIONS:'))
        self.stdout.write('-' * 70)

        campaign_migrations = MigrationRecorder.Migration.objects.filter(
            app='crm_app',
            name__in=['0012_emailtemplate_emailcampaign',
                     '0025_alter_emailtemplate_body_html_and_more',
                     '0025_user_smtp_email_user_smtp_password',
                     '0026_merge_20251114_1416',
                     '0027_campaignrecipient_and_more']
        ).order_by('name')

        if campaign_migrations.exists():
            for mig in campaign_migrations:
                self.stdout.write(self.style.SUCCESS(f'✓ {mig.name} - Applied at {mig.applied}'))
        else:
            self.stdout.write(self.style.WARNING('  No campaign-related migrations found'))

        # Check all migrations from 0012 onwards
        self.stdout.write('\n' + self.style.HTTP_INFO('2. ALL MIGRATIONS FROM 0012 ONWARDS:'))
        self.stdout.write('-' * 70)

        all_recent = MigrationRecorder.Migration.objects.filter(
            app='crm_app',
            name__gte='0012'
        ).order_by('name')

        for mig in all_recent:
            self.stdout.write(f'  {mig.name}')

        # Check if tables exist
        self.stdout.write('\n' + self.style.HTTP_INFO('3. DATABASE TABLES CHECK:'))
        self.stdout.write('-' * 70)

        with connection.cursor() as cursor:
            # Get all table names
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name LIKE '%campaign%'
                ORDER BY table_name
            """)
            tables = cursor.fetchall()

            if tables:
                self.stdout.write(self.style.SUCCESS('  Found campaign-related tables:'))
                for table in tables:
                    self.stdout.write(f'    ✓ {table[0]}')
            else:
                self.stdout.write(self.style.ERROR('  ✗ No campaign-related tables found'))

            # Check for specific expected tables
            expected_tables = [
                'crm_app_emailcampaign',     # Old Django auto-generated name
                'crm_app_email_campaign',    # New explicit name from migration 0027
                'crm_app_campaign_recipient', # New table from migration 0027
            ]

            self.stdout.write('\n' + self.style.HTTP_INFO('4. EXPECTED TABLES STATUS:'))
            self.stdout.write('-' * 70)

            for table_name in expected_tables:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'public'
                        AND table_name = %s
                    )
                """, [table_name])
                exists = cursor.fetchone()[0]

                if exists:
                    # Get column count
                    cursor.execute("""
                        SELECT COUNT(*)
                        FROM information_schema.columns
                        WHERE table_name = %s
                    """, [table_name])
                    col_count = cursor.fetchone()[0]

                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ {table_name} (exists, {col_count} columns)')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'  ✗ {table_name} (MISSING)')
                    )

        # Diagnosis
        self.stdout.write('\n' + self.style.HTTP_INFO('5. DIAGNOSIS:'))
        self.stdout.write('=' * 70)

        migration_0027_applied = MigrationRecorder.Migration.objects.filter(
            app='crm_app',
            name='0027_campaignrecipient_and_more'
        ).exists()

        migration_0026_applied = MigrationRecorder.Migration.objects.filter(
            app='crm_app',
            name='0026_merge_20251114_1416'
        ).exists()

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'crm_app_email_campaign'
                )
            """)
            new_table_exists = cursor.fetchone()[0]

            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'crm_app_emailcampaign'
                )
            """)
            old_table_exists = cursor.fetchone()[0]

        if migration_0027_applied and new_table_exists:
            self.stdout.write(self.style.SUCCESS('✓ Campaign system is properly configured'))
            self.stdout.write('  - Migration 0027 is applied')
            self.stdout.write('  - Table crm_app_email_campaign exists')
            self.stdout.write('\n  RECOMMENDATION: No action needed')

        elif not migration_0026_applied:
            self.stdout.write(self.style.ERROR('✗ Migration 0026 (merge) NOT applied'))
            self.stdout.write('  RECOMMENDATION: Deploy to apply migrations 0026 and 0027')

        elif not migration_0027_applied and not old_table_exists and not new_table_exists:
            self.stdout.write(self.style.ERROR('✗ Campaign tables never created'))
            self.stdout.write('  - Migration 0027 NOT applied')
            self.stdout.write('  - No campaign tables exist')
            self.stdout.write('\n  RECOMMENDATION: Deploy to apply migration 0027')

        elif old_table_exists and not new_table_exists:
            self.stdout.write(self.style.WARNING('⚠ Old table exists but not renamed'))
            self.stdout.write('  - Table crm_app_emailcampaign exists (old name)')
            self.stdout.write('  - Table crm_app_email_campaign missing (new name)')
            self.stdout.write('\n  RECOMMENDATION: Apply migration 0027 to rename table')

        else:
            self.stdout.write(self.style.WARNING('⚠ Unexpected state'))
            self.stdout.write(f'  - Migration 0026 applied: {migration_0026_applied}')
            self.stdout.write(f'  - Migration 0027 applied: {migration_0027_applied}')
            self.stdout.write(f'  - Old table exists: {old_table_exists}')
            self.stdout.write(f'  - New table exists: {new_table_exists}')
            self.stdout.write('\n  RECOMMENDATION: Review manually')

        self.stdout.write('\n' + self.style.SUCCESS('=' * 70))
