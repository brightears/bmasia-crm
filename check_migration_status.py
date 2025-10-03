#!/usr/bin/env python
"""
Script to check migration status and manually add the billing_entity column if needed
"""
import os
import sys
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bmasia_crm.settings')
django.setup()

from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

# Check if migration is recorded as applied
recorder = MigrationRecorder(connection)
applied_migrations = recorder.applied_migrations()

migration_key = ('crm_app', '0023_company_billing_entity')
print(f"\n=== Migration Status Check ===")
print(f"Looking for migration: {migration_key}")
print(f"Is migration recorded as applied? {migration_key in applied_migrations}")

# Check if column actually exists in database
print(f"\n=== Database Column Check ===")
cursor = connection.cursor()
cursor.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name='crm_app_company'
    AND column_name='billing_entity'
""")
result = cursor.fetchone()
print(f"Does billing_entity column exist in database? {result is not None}")

if migration_key in applied_migrations and result is None:
    print("\n⚠️  PROBLEM DETECTED:")
    print("Migration is marked as applied but column doesn't exist!")
    print("This can happen if the migration failed but Django recorded it anyway.")
    print("\nSolution: We need to manually add the column or fake-reverse the migration.")
elif migration_key not in applied_migrations and result is None:
    print("\n✓ Migration has not been applied yet. Running it now should work.")
elif result is not None:
    print("\n✓ Column exists. Everything is good!")
