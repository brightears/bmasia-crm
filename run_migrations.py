#!/usr/bin/env python
"""
Quick script to run migrations
Can be executed from Render shell
"""

import os
import sys
import django

if __name__ == "__main__":
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bmasia_crm.settings')
    django.setup()
    
    from django.core.management import execute_from_command_line
    
    print("Running migrations...")
    execute_from_command_line(['manage.py', 'migrate'])
    
    print("\nCreating email templates...")
    try:
        execute_from_command_line(['manage.py', 'create_email_templates'])
    except Exception as e:
        print(f"Could not create templates: {e}")
    
    print("\nMigrations complete!")