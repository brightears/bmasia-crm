#!/usr/bin/env python
"""Direct script to reset database - can be run from shell"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bmasia_crm.settings')
django.setup()

from django.db import connection
from django.core.management import call_command

print("This will DROP ALL crm_app tables and data!")
confirm = input("Type 'yes' to continue: ")

if confirm.lower() != 'yes':
    print("Cancelled.")
    sys.exit(0)

with connection.cursor() as cursor:
    print("Fetching crm_app tables...")
    
    # Get all table names that start with crm_app
    cursor.execute("""
        SELECT tablename FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename LIKE 'crm_app_%';
    """)
    
    tables = cursor.fetchall()
    
    if not tables:
        print("No crm_app tables found.")
    else:
        print(f"Found {len(tables)} tables to drop")
        
        # Drop each table
        for table in tables:
            table_name = table[0]
            print(f"Dropping {table_name}...")
            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE;')
    
    # Clear migration history
    print("Clearing migration history...")
    cursor.execute("DELETE FROM django_migrations WHERE app = 'crm_app';")
    print("Done!")

print("\nRunning migrations...")
call_command('migrate', 'crm_app', verbosity=2)

print("\nCreating superuser...")
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@bmasiamusic.com', 'BMAsia2024!')
    print("Superuser created: admin / BMAsia2024!")
else:
    print("Superuser already exists")

print("\nCreating email templates...")
call_command('create_email_templates')

print("\nDatabase reset complete! The app should now work properly.")