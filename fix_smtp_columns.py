#!/usr/bin/env python
"""
Direct SQL fix for missing smtp_email and smtp_password columns.
This is safe as it only adds columns that should already exist.
"""
import os
import psycopg2

# Get database URL from environment
database_url = os.environ.get('DATABASE_URL')

if not database_url:
    print("ERROR: DATABASE_URL environment variable not set")
    exit(1)

print("=" * 70)
print("ADDING SMTP COLUMNS TO auth_user TABLE")
print("=" * 70)

try:
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    # Check if smtp_email column exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'auth_user'
            AND column_name = 'smtp_email'
        )
    """)
    smtp_email_exists = cursor.fetchone()[0]

    # Check if smtp_password column exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'auth_user'
            AND column_name = 'smtp_password'
        )
    """)
    smtp_password_exists = cursor.fetchone()[0]

    if smtp_email_exists and smtp_password_exists:
        print("✓ Both smtp_email and smtp_password columns already exist")
    else:
        if not smtp_email_exists:
            print("Adding smtp_email column...")
            cursor.execute("""
                ALTER TABLE auth_user
                ADD COLUMN IF NOT EXISTS smtp_email VARCHAR(254) NULL
            """)
            print("✓ smtp_email column added")

        if not smtp_password_exists:
            print("Adding smtp_password column...")
            cursor.execute("""
                ALTER TABLE auth_user
                ADD COLUMN IF NOT EXISTS smtp_password VARCHAR(255) NULL
            """)
            print("✓ smtp_password column added")

        conn.commit()

    # Also check/add the soundtrack_offline_alerts_enabled column to company
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'crm_app_company'
            AND column_name = 'soundtrack_offline_alerts_enabled'
        )
    """)
    alerts_enabled_exists = cursor.fetchone()[0]

    if not alerts_enabled_exists:
        print("Adding soundtrack_offline_alerts_enabled column to company...")
        cursor.execute("""
            ALTER TABLE crm_app_company
            ADD COLUMN IF NOT EXISTS soundtrack_offline_alerts_enabled BOOLEAN DEFAULT TRUE
        """)
        conn.commit()
        print("✓ soundtrack_offline_alerts_enabled column added")
    else:
        print("✓ soundtrack_offline_alerts_enabled column already exists")

    # Check/add receives_soundtrack_alerts column to contact
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'crm_app_contact'
            AND column_name = 'receives_soundtrack_alerts'
        )
    """)
    receives_alerts_exists = cursor.fetchone()[0]

    if not receives_alerts_exists:
        print("Adding receives_soundtrack_alerts column to contact...")
        cursor.execute("""
            ALTER TABLE crm_app_contact
            ADD COLUMN IF NOT EXISTS receives_soundtrack_alerts BOOLEAN DEFAULT FALSE
        """)
        conn.commit()
        print("✓ receives_soundtrack_alerts column added")
    else:
        print("✓ receives_soundtrack_alerts column already exists")

    # Check/create ZoneOfflineAlert table
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'crm_app_zoneofflinealert'
        )
    """)
    table_exists = cursor.fetchone()[0]

    if not table_exists:
        print("Creating crm_app_zoneofflinealert table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crm_app_zoneofflinealert (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                detected_at TIMESTAMP WITH TIME ZONE NOT NULL,
                resolved_at TIMESTAMP WITH TIME ZONE NULL,
                is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
                first_notification_sent BOOLEAN NOT NULL DEFAULT FALSE,
                first_notification_at TIMESTAMP WITH TIME ZONE NULL,
                last_notification_at TIMESTAMP WITH TIME ZONE NULL,
                notification_count INTEGER NOT NULL DEFAULT 0,
                zone_id UUID NOT NULL REFERENCES crm_app_zone(id) ON DELETE CASCADE
            )
        """)
        # Create the many-to-many table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crm_app_zoneofflinealert_notified_contacts (
                id SERIAL PRIMARY KEY,
                zoneofflinealert_id INTEGER NOT NULL REFERENCES crm_app_zoneofflinealert(id) ON DELETE CASCADE,
                contact_id UUID NOT NULL REFERENCES crm_app_contact(id) ON DELETE CASCADE,
                UNIQUE(zoneofflinealert_id, contact_id)
            )
        """)
        conn.commit()
        print("✓ crm_app_zoneofflinealert tables created")
    else:
        print("✓ crm_app_zoneofflinealert table already exists")

    cursor.close()
    conn.close()

    print("=" * 70)
    print("SUCCESS - All columns and tables verified/created")
    print("=" * 70)

except Exception as e:
    print(f"ERROR: {e}")
    exit(1)
