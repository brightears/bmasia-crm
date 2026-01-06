#!/usr/bin/env python
"""
Direct SQL fix for migrations 0046 and 0047 - Zone Management Improvements
Applies missing columns and tables directly via SQL to avoid migration dependencies.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bmasia_crm.settings')
django.setup()

from django.db import connection

def apply_fixes():
    with connection.cursor() as cursor:
        print("Checking and applying zone management migration fixes...")

        # Migration 0046 - Add soundtrack_offline_alerts_enabled to Company
        try:
            cursor.execute("""
                ALTER TABLE crm_app_company
                ADD COLUMN IF NOT EXISTS soundtrack_offline_alerts_enabled BOOLEAN DEFAULT TRUE
            """)
            print("✓ Company.soundtrack_offline_alerts_enabled column added (or already exists)")
        except Exception as e:
            print(f"  Company.soundtrack_offline_alerts_enabled: {e}")

        # Migration 0046 - Add receives_soundtrack_alerts to Contact
        try:
            cursor.execute("""
                ALTER TABLE crm_app_contact
                ADD COLUMN IF NOT EXISTS receives_soundtrack_alerts BOOLEAN DEFAULT FALSE
            """)
            print("✓ Contact.receives_soundtrack_alerts column added (or already exists)")
        except Exception as e:
            print(f"  Contact.receives_soundtrack_alerts: {e}")

        # Migration 0046 - Create ZoneOfflineAlert table
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS crm_app_zoneofflinealert (
                    id BIGSERIAL PRIMARY KEY,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    detected_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    resolved_at TIMESTAMP WITH TIME ZONE NULL,
                    is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
                    first_notification_sent BOOLEAN NOT NULL DEFAULT FALSE,
                    first_notification_at TIMESTAMP WITH TIME ZONE NULL,
                    last_notification_at TIMESTAMP WITH TIME ZONE NULL,
                    notification_count INTEGER NOT NULL DEFAULT 0,
                    zone_id BIGINT NOT NULL REFERENCES crm_app_zone(id) ON DELETE CASCADE
                )
            """)
            print("✓ ZoneOfflineAlert table created (or already exists)")
        except Exception as e:
            print(f"  ZoneOfflineAlert table: {e}")

        # Create the M2M table for ZoneOfflineAlert notified_contacts
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS crm_app_zoneofflinealert_notified_contacts (
                    id BIGSERIAL PRIMARY KEY,
                    zoneofflinealert_id BIGINT NOT NULL REFERENCES crm_app_zoneofflinealert(id) ON DELETE CASCADE,
                    contact_id BIGINT NOT NULL REFERENCES crm_app_contact(id) ON DELETE CASCADE,
                    UNIQUE (zoneofflinealert_id, contact_id)
                )
            """)
            print("✓ ZoneOfflineAlert M2M table created (or already exists)")
        except Exception as e:
            print(f"  ZoneOfflineAlert M2M table: {e}")

        # Migration 0047 - Add soundtrack_account_id to Contract
        try:
            cursor.execute("""
                ALTER TABLE crm_app_contract
                ADD COLUMN IF NOT EXISTS soundtrack_account_id VARCHAR(100) DEFAULT ''
            """)
            print("✓ Contract.soundtrack_account_id column added (or already exists)")
        except Exception as e:
            print(f"  Contract.soundtrack_account_id: {e}")

        # Migration 0047 - Add is_orphaned to Zone
        try:
            cursor.execute("""
                ALTER TABLE crm_app_zone
                ADD COLUMN IF NOT EXISTS is_orphaned BOOLEAN DEFAULT FALSE
            """)
            print("✓ Zone.is_orphaned column added (or already exists)")
        except Exception as e:
            print(f"  Zone.is_orphaned: {e}")

        # Migration 0047 - Add orphaned_at to Zone
        try:
            cursor.execute("""
                ALTER TABLE crm_app_zone
                ADD COLUMN IF NOT EXISTS orphaned_at TIMESTAMP WITH TIME ZONE NULL
            """)
            print("✓ Zone.orphaned_at column added (or already exists)")
        except Exception as e:
            print(f"  Zone.orphaned_at: {e}")

        # Record migrations as applied (if not already recorded)
        migrations_to_record = [
            ('0046_soundtrack_offline_alerts', 'crm_app'),
            ('0047_zone_management_improvements', 'crm_app'),
        ]

        for migration_name, app in migrations_to_record:
            try:
                cursor.execute("""
                    INSERT INTO django_migrations (app, name, applied)
                    SELECT %s, %s, NOW()
                    WHERE NOT EXISTS (
                        SELECT 1 FROM django_migrations WHERE app = %s AND name = %s
                    )
                """, [app, migration_name, app, migration_name])
                if cursor.rowcount > 0:
                    print(f"✓ Recorded migration {migration_name}")
                else:
                    print(f"  Migration {migration_name} already recorded")
            except Exception as e:
                print(f"  Recording {migration_name}: {e}")

        print("\nZone management migration fixes complete!")

if __name__ == '__main__':
    apply_fixes()
