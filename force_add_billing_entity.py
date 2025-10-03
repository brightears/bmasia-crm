#!/usr/bin/env python
"""
Script to manually add the billing_entity column to production database
This bypasses Django migrations and directly alters the PostgreSQL table
"""
import os
import sys
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bmasia_crm.settings')
django.setup()

from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

print("=== Force Add billing_entity Column Script ===\n")

# First, check current state
cursor = connection.cursor()

# Check if column exists
cursor.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name='crm_app_company'
    AND column_name='billing_entity'
""")
column_exists = cursor.fetchone() is not None
print(f"1. Column 'billing_entity' exists: {column_exists}")

if not column_exists:
    print("\n2. Adding billing_entity column to crm_app_company table...")
    try:
        # Add the column with the exact same specification as the migration
        cursor.execute("""
            ALTER TABLE crm_app_company
            ADD COLUMN billing_entity VARCHAR(50)
            NOT NULL
            DEFAULT 'BMAsia Limited'
        """)
        connection.commit()
        print("   ✓ Column added successfully!")

        # Add the check constraint for choices
        cursor.execute("""
            ALTER TABLE crm_app_company
            ADD CONSTRAINT crm_app_company_billing_entity_check
            CHECK (billing_entity IN ('BMAsia Limited', 'BMAsia (Thailand) Co., Ltd.'))
        """)
        connection.commit()
        print("   ✓ Check constraint added successfully!")

    except Exception as e:
        print(f"   ✗ Error adding column: {e}")
        connection.rollback()
        sys.exit(1)
else:
    print("   → Column already exists, skipping...")

# Now ensure the migration is recorded as applied
migration_key = ('crm_app', '0023_company_billing_entity')
recorder = MigrationRecorder(connection)
applied_migrations = recorder.applied_migrations()

print(f"\n3. Checking if migration is recorded as applied...")
if migration_key not in applied_migrations:
    print("   Migration not recorded. Recording it now...")
    try:
        recorder.record_applied('crm_app', '0023_company_billing_entity')
        print("   ✓ Migration recorded successfully!")
    except Exception as e:
        print(f"   ✗ Error recording migration: {e}")
        sys.exit(1)
else:
    print("   → Migration already recorded")

# Final verification
cursor.execute("""
    SELECT column_name, data_type, character_maximum_length, column_default
    FROM information_schema.columns
    WHERE table_name='crm_app_company'
    AND column_name='billing_entity'
""")
result = cursor.fetchone()

print("\n=== Final Verification ===")
if result:
    print(f"✓ Column details:")
    print(f"  - Name: {result[0]}")
    print(f"  - Type: {result[1]}")
    print(f"  - Max Length: {result[2]}")
    print(f"  - Default: {result[3]}")
    print("\n✓ SUCCESS! The billing_entity column is now in the database!")
else:
    print("✗ ERROR: Column still doesn't exist!")
    sys.exit(1)
