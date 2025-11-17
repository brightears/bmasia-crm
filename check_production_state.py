#!/usr/bin/env python
"""
Diagnostic script to check production database state for campaigns.
Run this with: python check_production_state.py
"""
import os
import psycopg2

# Get database URL from environment
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    print("ERROR: DATABASE_URL not set")
    exit(1)

print("Connecting to production database...")
conn = psycopg2.connect(database_url)
cursor = conn.cursor()

print("\n=== Checking Applied Migrations ===")
cursor.execute("""
    SELECT app, name FROM django_migrations 
    WHERE app = 'crm_app' AND name LIKE '%campaign%'
    ORDER BY id
""")
migrations = cursor.fetchall()
if migrations:
    for app, name in migrations:
        print(f"  ✓ {name}")
else:
    print("  No campaign migrations applied")

print("\n=== Checking Tables ===")
cursor.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name LIKE '%campaign%'
    ORDER BY table_name
""")
tables = cursor.fetchall()
if tables:
    for (table_name,) in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"  ✓ {table_name} ({count} rows)")
else:
    print("  No campaign tables found")

print("\n=== Checking EmailCampaign Model Table ===")
for table_name in ['crm_app_emailcampaign', 'crm_app_email_campaign']:
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
    """, (table_name,))
    exists = cursor.fetchone()[0]
    if exists:
        cursor.execute(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        columns = cursor.fetchall()
        print(f"\n  Table: {table_name}")
        print(f"  Columns: {len(columns)}")
        for col_name, col_type in columns[:10]:  # Show first 10
            print(f"    - {col_name} ({col_type})")
        if len(columns) > 10:
            print(f"    ... and {len(columns) - 10} more")
    else:
        print(f"  ✗ {table_name} - does not exist")

cursor.close()
conn.close()
print("\n=== Done ===")
