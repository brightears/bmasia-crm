#!/usr/bin/env python3
"""
Apply migration 0025 to production database manually
Adds smtp_email and smtp_password fields to auth_user table
"""
import psycopg2
import sys

# Database connection details
DB_CONFIG = {
    'host': 'dpg-d3cbikd6ubrc73el0ke0-a.singapore-postgres.render.com',
    'port': 5432,
    'user': 'bmasia_crm_user',
    'password': 'IUEmiG1IFKkzZOsR9HBpYoRGM7zhoI7v',
    'database': 'bmasia_crm',
    'sslmode': 'require'
}

# SQL to apply migration 0025
SQL_COMMANDS = [
    # Add smtp_email column
    '''ALTER TABLE auth_user 
       ADD COLUMN IF NOT EXISTS smtp_email VARCHAR(254) NULL;''',
    
    # Add smtp_password column
    '''ALTER TABLE auth_user 
       ADD COLUMN IF NOT EXISTS smtp_password VARCHAR(255) NULL;''',
    
    # Insert migration record to prevent duplicate runs
    '''INSERT INTO django_migrations (app, name, applied)
       VALUES ('crm_app', '0025_user_smtp_email_user_smtp_password', NOW())
       ON CONFLICT DO NOTHING;'''
]

VERIFICATION_SQL = '''
SELECT column_name, data_type, character_maximum_length, is_nullable
FROM information_schema.columns
WHERE table_name = 'auth_user' 
AND column_name IN ('smtp_email', 'smtp_password')
ORDER BY column_name;
'''

def main():
    print("=" * 70)
    print("PRODUCTION DATABASE MIGRATION - MIGRATION 0025")
    print("=" * 70)
    print(f"\nConnecting to: {DB_CONFIG['host']}")
    print(f"Database: {DB_CONFIG['database']}")
    print(f"User: {DB_CONFIG['user']}")
    print()

    conn = None  # Initialize to avoid UnboundLocalError
    try:
        # Connect to database
        print("Establishing connection...")
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False  # Use transactions for safety
        cursor = conn.cursor()
        print("✓ Connected successfully\n")
        
        # Apply each SQL command
        print("Applying migration SQL commands:")
        print("-" * 70)
        
        for i, sql in enumerate(SQL_COMMANDS, 1):
            print(f"\n[{i}/{len(SQL_COMMANDS)}] Executing:")
            print(f"    {sql[:60]}..." if len(sql) > 60 else f"    {sql}")
            
            try:
                cursor.execute(sql)
                print(f"    ✓ Success")
            except Exception as e:
                print(f"    ✗ Error: {e}")
                if "already exists" in str(e) or "duplicate key" in str(e):
                    print(f"    (This is OK - column/record already exists)")
                else:
                    raise
        
        # Commit transaction
        print("\n" + "=" * 70)
        print("Committing transaction...")
        conn.commit()
        print("✓ Transaction committed successfully\n")
        
        # Verify columns exist
        print("=" * 70)
        print("VERIFICATION: Checking new columns exist")
        print("=" * 70)
        cursor.execute(VERIFICATION_SQL)
        results = cursor.fetchall()
        
        if results:
            print("\n✓ New columns found in auth_user table:\n")
            print(f"{'Column Name':<20} {'Type':<15} {'Max Length':<12} {'Nullable'}")
            print("-" * 70)
            for row in results:
                col_name, data_type, max_len, nullable = row
                print(f"{col_name:<20} {data_type:<15} {str(max_len):<12} {nullable}")
        else:
            print("\n✗ WARNING: Columns not found after migration!")
            sys.exit(1)
        
        # Close connection
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 70)
        print("✓ MIGRATION 0025 APPLIED SUCCESSFULLY")
        print("=" * 70)
        print("\nNext steps:")
        print("1. Test login at https://bmasia-crm.onrender.com")
        print("2. Verify no 'column does not exist' errors")
        print("3. Check Django admin for SMTP configuration fields")
        print()
        
        return 0
        
    except psycopg2.Error as e:
        print(f"\n✗ DATABASE ERROR: {e}")
        print(f"\nDetails: {e.pgerror if hasattr(e, 'pgerror') else 'No details available'}")
        if conn:
            conn.rollback()
            print("Transaction rolled back")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        if conn:
            conn.rollback()
            print("Transaction rolled back")
        sys.exit(1)

if __name__ == '__main__':
    sys.exit(main())
