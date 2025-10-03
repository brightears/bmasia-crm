#!/usr/bin/env python
"""
Script to run pending migrations on production database
This can be executed manually on Render to fix the billing_entity column issue
"""
import os
import sys
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bmasia_crm.settings')
django.setup()

from django.core.management import execute_from_command_line

if __name__ == '__main__':
    print("Running database migrations...")
    execute_from_command_line(['manage.py', 'migrate'])
    print("Migrations completed successfully!")
