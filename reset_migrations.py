#!/usr/bin/env python
"""
Reset all migrations for fresh PostgreSQL deployment
"""
import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bmasia_crm.settings')
django.setup()

from django.core.management import call_command
from django.db import connection

def reset_migrations():
    """Reset all migrations"""
    
    # Check if we're in production
    if 'DATABASE_URL' not in os.environ:
        print("This script should only be run in production with PostgreSQL")
        sys.exit(1)
    
    with connection.cursor() as cursor:
        # Check if django_migrations table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'django_migrations'
            );
        """)
        exists = cursor.fetchone()[0]
        
        if exists:
            print("Clearing migration history...")
            cursor.execute("DELETE FROM django_migrations WHERE app = 'crm_app';")
            print("Migration history cleared.")
    
    print("Running migrations...")
    call_command('migrate', '--fake-initial')
    print("Migrations completed!")

if __name__ == '__main__':
    reset_migrations()