"""
Database diagnostic command to check migration status and table structure.
Run with: python manage.py diagnose_db
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Diagnose database migration status and table structure'

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write("DATABASE DIAGNOSIS")
        self.stdout.write("=" * 80)
        self.stdout.write(f"Database: {connection.settings_dict['NAME']}")
        self.stdout.write(f"Host: {connection.settings_dict['HOST']}")
        self.stdout.write(f"User: {connection.settings_dict['USER']}\n")
        
        with connection.cursor() as cursor:
            # Check PostgreSQL version
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            self.stdout.write(f"PostgreSQL Version: {version[:80]}...\n")
            
            # Check migrations
            self.stdout.write("=" * 80)
            self.stdout.write("1. MIGRATION STATUS")
            self.stdout.write("=" * 80)
            
            cursor.execute("SELECT COUNT(*) FROM django_migrations;")
            total_count = cursor.fetchone()[0]
            self.stdout.write(f"Total migrations: {total_count}\n")
            
            # Get last 25 crm_app migrations
            cursor.execute("""
                SELECT name, applied 
                FROM django_migrations 
                WHERE app = 'crm_app'
                ORDER BY applied DESC
                LIMIT 25;
            """)
            migrations = cursor.fetchall()
            
            self.stdout.write("Last 25 crm_app migrations:")
            self.stdout.write("-" * 80)
            migration_0025_found = False
            for name, applied in migrations:
                marker = ">>> " if "0025" in name else "    "
                self.stdout.write(f"{marker}{name:<60} {applied}")
                if "0025" in name:
                    migration_0025_found = True
            
            self.stdout.write("")
            if migration_0025_found:
                self.stdout.write(self.style.SUCCESS("✓ Migration 0025 IS APPLIED"))
            else:
                self.stdout.write(self.style.ERROR("✗ Migration 0025 NOT FOUND"))
            
            # Get latest migration
            cursor.execute("""
                SELECT name, applied 
                FROM django_migrations 
                WHERE app = 'crm_app'
                ORDER BY applied DESC
                LIMIT 1;
            """)
            latest = cursor.fetchone()
            self.stdout.write(f"\nLatest migration: {latest[0]} ({latest[1]})")
            
            # Check auth_user table
            self.stdout.write("\n" + "=" * 80)
            self.stdout.write("2. AUTH_USER TABLE STRUCTURE")
            self.stdout.write("=" * 80)
            
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' 
                AND table_name = 'auth_user'
                ORDER BY ordinal_position;
            """)
            columns = cursor.fetchall()
            
            smtp_email_found = False
            smtp_password_found = False
            
            self.stdout.write(f"Total columns: {len(columns)}\n")
            for col_name, data_type, is_nullable in columns:
                marker = ""
                if col_name == 'smtp_email':
                    smtp_email_found = True
                    marker = " ← SMTP EMAIL"
                elif col_name == 'smtp_password':
                    smtp_password_found = True
                    marker = " ← SMTP PASSWORD"
                self.stdout.write(f"  {col_name:<30} {data_type:<20} NULL: {is_nullable}{marker}")
            
            # Summary
            self.stdout.write("\n" + "=" * 80)
            self.stdout.write("3. DIAGNOSIS SUMMARY")
            self.stdout.write("=" * 80)
            self.stdout.write(f"smtp_email column exists: {smtp_email_found}")
            self.stdout.write(f"smtp_password column exists: {smtp_password_found}\n")
            
            if not smtp_email_found:
                self.stdout.write(self.style.ERROR("PROBLEM CONFIRMED: smtp_email column is MISSING"))
                self.stdout.write("\nRoot Cause:")
                self.stdout.write("  Migration 0025 NOT applied to this database")
                self.stdout.write("\nSolution:")
                self.stdout.write("  Run: python manage.py migrate crm_app 0025")
                self.stdout.write("  Or:  python manage.py migrate")
            else:
                self.stdout.write(self.style.SUCCESS("✓ SMTP columns exist"))
                self.stdout.write("\nIf you're seeing errors, check:")
                self.stdout.write("  1. Correct DATABASE_URL is set")
                self.stdout.write("  2. Application restarted after migration")
                self.stdout.write("  3. No connection pooling issues")
            
            self.stdout.write("\n" + "=" * 80)
