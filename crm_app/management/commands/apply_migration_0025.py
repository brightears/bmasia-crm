"""
Django management command to manually apply migration 0025
Run with: python manage.py apply_migration_0025
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Manually apply migration 0025 to add smtp_email and smtp_password fields'

    def handle(self, *args, **options):
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.WARNING("APPLYING MIGRATION 0025 MANUALLY"))
        self.stdout.write("=" * 70)
        
        with connection.cursor() as cursor:
            # Check if columns already exist
            self.stdout.write("\n1. Checking if columns already exist...")
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'auth_user'
                AND column_name IN ('smtp_email', 'smtp_password')
            """)
            existing = [row[0] for row in cursor.fetchall()]
            
            if len(existing) == 2:
                self.stdout.write(self.style.SUCCESS("   ✓ Both columns already exist!"))
            else:
                # Add smtp_email column
                if 'smtp_email' not in existing:
                    self.stdout.write("\n2. Adding smtp_email column...")
                    cursor.execute("""
                        ALTER TABLE auth_user
                        ADD COLUMN smtp_email VARCHAR(254) NULL
                    """)
                    self.stdout.write(self.style.SUCCESS("   ✓ smtp_email column added"))
                else:
                    self.stdout.write("\n2. smtp_email already exists, skipping...")
                
                # Add smtp_password column
                if 'smtp_password' not in existing:
                    self.stdout.write("\n3. Adding smtp_password column...")
                    cursor.execute("""
                        ALTER TABLE auth_user
                        ADD COLUMN smtp_password VARCHAR(255) NULL
                    """)
                    self.stdout.write(self.style.SUCCESS("   ✓ smtp_password column added"))
                else:
                    self.stdout.write("\n3. smtp_password already exists, skipping...")
            
            # Record migration in django_migrations table
            self.stdout.write("\n4. Recording migration in django_migrations...")
            cursor.execute("""
                SELECT COUNT(*) FROM django_migrations
                WHERE app = 'crm_app'
                AND name = '0025_user_smtp_email_user_smtp_password'
            """)
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO django_migrations (app, name, applied)
                    VALUES ('crm_app', '0025_user_smtp_email_user_smtp_password', NOW())
                """)
                self.stdout.write(self.style.SUCCESS("   ✓ Migration recorded"))
            else:
                self.stdout.write(self.style.SUCCESS("   ✓ Migration already recorded"))
            
            # Verify columns exist
            self.stdout.write("\n5. Verification:")
            cursor.execute("""
                SELECT column_name, data_type, character_maximum_length, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'auth_user'
                AND column_name IN ('smtp_email', 'smtp_password')
                ORDER BY column_name
            """)
            results = cursor.fetchall()
            
            for col_name, data_type, max_len, nullable in results:
                self.stdout.write(f"   ✓ {col_name}: {data_type}({max_len}), nullable={nullable}")
        
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("✓ MIGRATION 0025 COMPLETED SUCCESSFULLY"))
        self.stdout.write("=" * 70)
