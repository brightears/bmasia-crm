#!/usr/bin/env python
"""
Mark migrations 0027 and 0028 as applied in production database
WITHOUT actually running them (since tables already exist).
"""
import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bmasia_crm.settings')
django.setup()

from django.db import connection

def mark_migrations_as_applied():
    """Mark migrations 0027 and 0028 as applied in django_migrations table."""
    migrations_to_mark = [
        ('crm_app', '0027_campaignrecipient_alter_emailcampaign_options_and_more'),
        ('crm_app', '0028_alter_emailcampaign_table'),
    ]
    
    with connection.cursor() as cursor:
        # Check current migration state
        cursor.execute("""
            SELECT app, name FROM django_migrations 
            WHERE app = 'crm_app' 
            ORDER BY id DESC 
            LIMIT 5
        """)
        current_migrations = cursor.fetchall()
        print("Current migrations (last 5):")
        for app, name in current_migrations:
            print(f"  - {app}.{name}")
        
        print("\nMarking migrations as applied:")
        for app, name in migrations_to_mark:
            # Check if already applied
            cursor.execute("""
                SELECT COUNT(*) FROM django_migrations 
                WHERE app = %s AND name = %s
            """, [app, name])
            count = cursor.fetchone()[0]
            
            if count > 0:
                print(f"  ✓ {name} - Already applied")
            else:
                # Insert migration record
                cursor.execute("""
                    INSERT INTO django_migrations (app, name, applied)
                    VALUES (%s, %s, NOW())
                """, [app, name])
                print(f"  ✓ {name} - Marked as applied")
        
        # Verify
        print("\nVerifying migration state:")
        cursor.execute("""
            SELECT app, name FROM django_migrations 
            WHERE app = 'crm_app' 
            ORDER BY id DESC 
            LIMIT 5
        """)
        updated_migrations = cursor.fetchall()
        for app, name in updated_migrations:
            print(f"  - {app}.{name}")

if __name__ == '__main__':
    print("=" * 60)
    print("MARKING MIGRATIONS AS APPLIED (NO SQL EXECUTION)")
    print("=" * 60)
    mark_migrations_as_applied()
    print("\n✅ Done! Migrations 0027 and 0028 marked as applied.")
    print("   Tables were created manually via Render shell.")
