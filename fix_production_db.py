#!/usr/bin/env python3
"""
Script to apply the legal_entity_name migration to production database.
"""

import psycopg2
import sys

# Production database URL
DATABASE_URL = "postgresql://bmasia_crm_user:IUEmiG1IFKkzZOsR9HBpYoRGM7zhoI7v@dpg-d3cbikd6ubrc73el0ke0-a.singapore-postgres.render.com:5432/bmasia_crm?sslmode=require"

def main():
    print("\n" + "=" * 80)
    print("Production Database Migration: Adding legal_entity_name column")
    print("=" * 80 + "\n")

    conn = None
    cursor = None

    try:
        # Connect to the database
        print("Connecting to production database...")
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        print("✓ Connected successfully\n")
        
        # Check if column already exists
        print("Step 1: Checking if column already exists...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='crm_app_company' 
            AND column_name='legal_entity_name';
        """)
        column_exists = cursor.fetchone() is not None
        
        if column_exists:
            print("  ⚠ Column 'legal_entity_name' already exists\n")
        else:
            print("  → Column does not exist, will create it\n")
            
            # Add the column
            print("Step 2: Adding column to crm_app_company table...")
            cursor.execute("""
                ALTER TABLE crm_app_company 
                ADD COLUMN legal_entity_name VARCHAR(255) DEFAULT '' NOT NULL;
            """)
            print("  ✓ Column added successfully\n")
        
        # Check if migration is already recorded
        print("Step 3: Checking migration record...")
        cursor.execute("""
            SELECT id 
            FROM django_migrations 
            WHERE app='crm_app' 
            AND name='0024_add_legal_entity_name_to_company';
        """)
        migration_exists = cursor.fetchone() is not None
        
        if migration_exists:
            print("  ⚠ Migration already recorded in django_migrations\n")
        else:
            print("  → Recording migration in django_migrations table...")
            cursor.execute("""
                INSERT INTO django_migrations (app, name, applied) 
                VALUES ('crm_app', '0024_add_legal_entity_name_to_company', NOW());
            """)
            print("  ✓ Migration recorded successfully\n")
        
        # Commit the transaction
        print("Step 4: Committing changes...")
        conn.commit()
        print("  ✓ All changes committed\n")
        
        # Verify the changes
        print("Step 5: Verifying final state...")
        cursor.execute("""
            SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name='crm_app_company' 
            AND column_name='legal_entity_name';
        """)
        result = cursor.fetchone()
        
        if result:
            print("  ✓ Column details:")
            print(f"      Name: {result[0]}")
            print(f"      Type: {result[1]}({result[2]})")
            print(f"      Nullable: {result[3]}")
            print(f"      Default: {result[4]}")
        
        cursor.execute("""
            SELECT id, applied 
            FROM django_migrations 
            WHERE app='crm_app' 
            AND name='0024_add_legal_entity_name_to_company';
        """)
        migration_result = cursor.fetchone()
        
        if migration_result:
            print(f"\n  ✓ Migration record:")
            print(f"      ID: {migration_result[0]}")
            print(f"      Applied: {migration_result[1]}")
        
        print("\n" + "=" * 80)
        print("SUCCESS: Migration completed successfully!")
        print("=" * 80)
        print("\nThe production database is now in sync with the application code.")
        print("The 500 error should be resolved.\n")
        
    except psycopg2.Error as e:
        print("\n" + "=" * 80)
        print("DATABASE ERROR")
        print("=" * 80)
        print(f"\nError Type: {type(e).__name__}")
        print(f"Error Code: {e.pgcode if hasattr(e, 'pgcode') else 'N/A'}")
        print(f"Message: {str(e)}\n")
        if conn:
            conn.rollback()
            print("Changes rolled back\n")
        sys.exit(1)
        
    except Exception as e:
        print("\n" + "=" * 80)
        print("UNEXPECTED ERROR")
        print("=" * 80)
        print(f"\nError: {str(e)}\n")
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
            print("\nChanges rolled back\n")
        sys.exit(1)
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            print("Database connection closed\n")

if __name__ == '__main__':
    main()
