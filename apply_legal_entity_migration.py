#!/usr/bin/env python3
"""
Script to apply the legal_entity_name migration to production database.
This adds the missing column and marks the migration as applied.
"""

import psycopg2
from psycopg2 import sql
import sys
from datetime import datetime

# Production database credentials
DB_CONFIG = {
    'host': 'dpg-d3cbikd6ubrc73el0ke0-a.singapore-postgres.render.com',
    'port': 5432,
    'user': 'bmasia_crm_user',
    'password': 'IUEmiG1IFKkzZOsR9HBpYoRGM7zhoI7v',
    'database': 'bmasia_crm',
    'sslmode': 'require'
}

def main():
    print("=" * 80)
    print("Production Database Migration: Adding legal_entity_name column")
    print("=" * 80)
    print(f"Connecting to: {DB_CONFIG['host']}")
    print(f"Database: {DB_CONFIG['database']}")
    print()

    conn = None
    cursor = None

    try:
        # Connect to the database
        print("Connecting to database...")
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        cursor = conn.cursor()
        print("✓ Connected successfully")
        print()
        
        # Check if column already exists
        print("Checking if column already exists...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='crm_app_company' 
            AND column_name='legal_entity_name';
        """)
        column_exists = cursor.fetchone() is not None
        
        if column_exists:
            print("⚠ Column 'legal_entity_name' already exists in crm_app_company table")
        else:
            print("Column does not exist, proceeding with creation...")
            print()
            
            # Add the column
            print("Executing: ALTER TABLE crm_app_company ADD COLUMN legal_entity_name...")
            cursor.execute("""
                ALTER TABLE crm_app_company 
                ADD COLUMN legal_entity_name VARCHAR(255) DEFAULT '' NOT NULL;
            """)
            print("✓ Column added successfully")
        
        print()
        
        # Check if migration is already recorded
        print("Checking if migration is already recorded...")
        cursor.execute("""
            SELECT id 
            FROM django_migrations 
            WHERE app='crm_app' 
            AND name='0024_add_legal_entity_name_to_company';
        """)
        migration_exists = cursor.fetchone() is not None
        
        if migration_exists:
            print("⚠ Migration '0024_add_legal_entity_name_to_company' is already recorded")
        else:
            print("Recording migration in django_migrations table...")
            cursor.execute("""
                INSERT INTO django_migrations (app, name, applied) 
                VALUES ('crm_app', '0024_add_legal_entity_name_to_company', NOW());
            """)
            print("✓ Migration recorded successfully")
        
        print()
        
        # Verify the changes
        print("Verifying changes...")
        cursor.execute("""
            SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name='crm_app_company' 
            AND column_name='legal_entity_name';
        """)
        result = cursor.fetchone()
        
        if result:
            print("✓ Column verification:")
            print(f"  - Name: {result[0]}")
            print(f"  - Type: {result[1]}")
            print(f"  - Max Length: {result[2]}")
            print(f"  - Nullable: {result[3]}")
            print(f"  - Default: {result[4]}")
        else:
            print("✗ Column verification failed!")
            raise Exception("Column was not created")
        
        print()
        
        # Check migration status
        cursor.execute("""
            SELECT id, applied 
            FROM django_migrations 
            WHERE app='crm_app' 
            AND name='0024_add_legal_entity_name_to_company';
        """)
        migration_result = cursor.fetchone()
        
        if migration_result:
            print("✓ Migration status:")
            print(f"  - ID: {migration_result[0]}")
            print(f"  - Applied: {migration_result[1]}")
        else:
            print("✗ Migration record not found!")
            raise Exception("Migration was not recorded")
        
        # Commit the transaction
        print()
        print("Committing changes...")
        conn.commit()
        print("✓ All changes committed successfully")
        
        print()
        print("=" * 80)
        print("SUCCESS: Migration completed successfully!")
        print("=" * 80)
        print()
        print("Summary:")
        print("  - Column 'legal_entity_name' is present in crm_app_company table")
        print("  - Migration '0024_add_legal_entity_name_to_company' is recorded")
        print("  - Database is now in sync with the application code")
        print()
        
    except psycopg2.Error as e:
        print()
        print("=" * 80)
        print("ERROR: Database error occurred")
        print("=" * 80)
        print(f"Error code: {e.pgcode}")
        print(f"Error message: {e.pgerror}")
        print()
        if conn:
            conn.rollback()
            print("Changes rolled back")
        sys.exit(1)
        
    except Exception as e:
        print()
        print("=" * 80)
        print("ERROR: Unexpected error occurred")
        print("=" * 80)
        print(f"Error: {str(e)}")
        print()
        if conn:
            conn.rollback()
            print("Changes rolled back")
        sys.exit(1)
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            print("Database connection closed")

if __name__ == '__main__':
    main()
