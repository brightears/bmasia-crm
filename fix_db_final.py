#!/usr/bin/env python3
"""
Final attempt to connect and fix production database
Uses urllib to parse the database URL properly
"""

import psycopg2
from urllib.parse import urlparse
import sys

# Production database URL
DATABASE_URL = "postgresql://bmasia_crm_user:IUEmiG1IFKkzZOsR9HBpYoRGM7zhoI7v@dpg-d3cbikd6ubrc73el0ke0-a.singapore-postgres.render.com:5432/bmasia_crm"

def main():
    print("\n" + "=" * 80)
    print("Production Database Fix: Adding legal_entity_name Column")
    print("=" * 80 + "\n")

    # Parse the database URL
    result = urlparse(DATABASE_URL)
    username = result.username
    password = result.password
    database = result.path[1:]
    hostname = result.hostname
    port = result.port or 5432

    print(f"Connecting to: {hostname}")
    print(f"Database: {database}")
    print(f"Port: {port}\n")

    conn = None
    cursor = None

    try:
        # Try connection without SSL first
        print("Attempt 1: Connecting without SSL...")
        try:
            conn = psycopg2.connect(
                dbname=database,
                user=username,
                password=password,
                host=hostname,
                port=port,
                connect_timeout=10
            )
            print("✓ Connected without SSL\n")
        except Exception as e:
            print(f"✗ Failed: {str(e)[:80]}\n")
            
            # Try with SSL required
            print("Attempt 2: Connecting with SSL required...")
            try:
                conn = psycopg2.connect(
                    dbname=database,
                    user=username,
                    password=password,
                    host=hostname,
                    port=port,
                    sslmode='require',
                    connect_timeout=10
                )
                print("✓ Connected with SSL\n")
            except Exception as e2:
                print(f"✗ Failed: {str(e2)[:80]}\n")
                raise Exception("Could not establish connection with or without SSL")

        if not conn:
            raise Exception("Connection failed")

        cursor = conn.cursor()
        
        # Check current state
        print("Step 1: Checking current database state...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='crm_app_company' 
            AND column_name='legal_entity_name';
        """)
        column_exists = cursor.fetchone() is not None
        
        cursor.execute("""
            SELECT id 
            FROM django_migrations 
            WHERE app='crm_app' 
            AND name='0024_add_legal_entity_name_to_company';
        """)
        migration_exists = cursor.fetchone() is not None
        
        print(f"  Column exists: {'Yes' if column_exists else 'No'}")
        print(f"  Migration recorded: {'Yes' if migration_exists else 'No'}\n")
        
        if not column_exists:
            print("Step 2: Adding column to crm_app_company table...")
            cursor.execute("""
                ALTER TABLE crm_app_company 
                ADD COLUMN legal_entity_name VARCHAR(255) DEFAULT '' NOT NULL;
            """)
            print("  ✓ Column added\n")
        
        if not migration_exists:
            print("Step 3: Recording migration in django_migrations...")
            cursor.execute("""
                INSERT INTO django_migrations (app, name, applied) 
                VALUES ('crm_app', '0024_add_legal_entity_name_to_company', NOW());
            """)
            print("  ✓ Migration recorded\n")
        
        # Commit changes
        print("Step 4: Committing changes...")
        conn.commit()
        print("  ✓ Committed\n")
        
        # Verify
        print("Step 5: Verifying changes...")
        cursor.execute("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns 
            WHERE table_name='crm_app_company' 
            AND column_name='legal_entity_name';
        """)
        result = cursor.fetchone()
        if result:
            print(f"  ✓ Column: {result[0]} ({result[1]}({result[2]}))")
        
        cursor.execute("""
            SELECT applied 
            FROM django_migrations 
            WHERE name='0024_add_legal_entity_name_to_company';
        """)
        result = cursor.fetchone()
        if result:
            print(f"  ✓ Migration applied: {result[0]}")
        
        print("\n" + "=" * 80)
        print("SUCCESS: Database fix completed!")
        print("=" * 80)
        print("\nThe production database now has the legal_entity_name column.")
        print("The 500 error should be resolved.\n")
        
    except Exception as e:
        print("\n" + "=" * 80)
        print("ERROR: Could not complete the fix")
        print("=" * 80)
        print(f"\n{str(e)}\n")
        print("Please use the manual approach documented in PRODUCTION_FIX_INSTRUCTIONS.md")
        print("You can access the database through Render Dashboard.\n")
        if conn:
            try:
                conn.rollback()
                print("Changes rolled back\n")
            except:
                pass
        sys.exit(1)
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            print("Connection closed\n")

if __name__ == '__main__':
    main()
