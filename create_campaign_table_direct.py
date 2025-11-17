#!/usr/bin/env python
"""
Direct SQL approach to create campaign tables.
This bypasses Django migrations entirely.
"""
import os
import psycopg2

# Get database URL from environment
database_url = os.environ.get('DATABASE_URL')

if not database_url:
    print("ERROR: DATABASE_URL environment variable not set")
    exit(1)

print("=" * 70)
print("CREATING CAMPAIGN TABLES DIRECTLY VIA SQL")
print("=" * 70)

try:
    # Connect to database
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    # Check if table exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'crm_app_email_campaign'
        )
    """)
    table_exists = cursor.fetchone()[0]

    if table_exists:
        print("✓ Table crm_app_email_campaign already exists")
    else:
        print("Creating crm_app_email_campaign table...")

        # Create the table
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
                company_id UUID
            )
        """)

        # Add foreign key
        cursor.execute("""
            ALTER TABLE crm_app_email_campaign
            ADD CONSTRAINT crm_app_email_campaign_company_id_fkey
            FOREIGN KEY (company_id)
            REFERENCES crm_app_company(id)
            ON DELETE CASCADE
            DEFERRABLE INITIALLY DEFERRED
        """)

        # Add index
        cursor.execute("""
            CREATE INDEX crm_app_ema_company_c5ff78_idx
            ON crm_app_email_campaign (company_id)
        """)

        conn.commit()
        print("✓ Table created successfully")

    cursor.close()
    conn.close()

    print("=" * 70)
    print("SUCCESS")
    print("=" * 70)

except Exception as e:
    print(f"ERROR: {e}")
    exit(1)
