#!/usr/bin/env python
"""
Fix PostgreSQL migration issues by dropping and recreating all tables
"""
import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bmasia_crm.settings')
django.setup()

from django.core.management import call_command
from django.db import connection

def fix_migrations():
    """Drop all crm_app tables and recreate"""
    
    # Check if we're in production
    if 'DATABASE_URL' not in os.environ:
        print("This script should only be run in production with PostgreSQL")
        sys.exit(1)
    
    with connection.cursor() as cursor:
        print("Dropping all crm_app tables...")
        
        # Get all table names that start with crm_app
        cursor.execute("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename LIKE 'crm_app_%';
        """)
        
        tables = cursor.fetchall()
        
        # Drop each table
        for table in tables:
            table_name = table[0]
            print(f"Dropping table {table_name}...")
            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE;')
        
        # Clear migration history for crm_app
        cursor.execute("DELETE FROM django_migrations WHERE app = 'crm_app';")
        print("Cleared migration history")
    
    print("Running migrations fresh...")
    call_command('migrate', 'crm_app')
    print("Migrations completed successfully!")

if __name__ == '__main__':
    fix_migrations()