#!/usr/bin/env python
"""
Run Django migrations on production database
"""
import os
import sys
import django

# Set production database URL
os.environ['DATABASE_URL'] = 'postgresql://bmasia_crm_user:IUEmiG1IFKkzZOsR9HBpYoRGM7zhoI7v@dpg-d3cbikd6ubrc73el0ke0-a/bmasia_crm'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bmasia_crm.settings')

# Setup Django
django.setup()

# Import migration command
from django.core.management import call_command

print("=" * 60)
print("Running migrations on PRODUCTION database")
print("Database: bmasia_crm on Render PostgreSQL")
print("=" * 60)

try:
    # Run migrations
    call_command('migrate', '--noinput', verbosity=2)
    print("\n✅ Migrations completed successfully!")
except Exception as e:
    print(f"\n❌ Migration failed: {e}")
    sys.exit(1)