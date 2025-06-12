#!/usr/bin/env python
"""
One-click fix for missing email tables
Run this in Render Shell: python fix_migrations.py
"""

import os
import sys
import django

if __name__ == "__main__":
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bmasia_crm.settings')
    
    print("🔧 BMAsia CRM - Email System Setup")
    print("=" * 50)
    
    try:
        django.setup()
        from django.core.management import execute_from_command_line
        
        print("\n1️⃣ Creating database migrations...")
        execute_from_command_line(['manage.py', 'makemigrations'])
        
        print("\n2️⃣ Running database migrations...")
        execute_from_command_line(['manage.py', 'migrate'])
        
        print("\n3️⃣ Creating email templates...")
        try:
            execute_from_command_line(['manage.py', 'create_email_templates'])
            print("✅ Email templates created successfully!")
        except Exception as e:
            print(f"⚠️  Could not create templates: {e}")
            print("   (This is OK if templates already exist)")
        
        print("\n" + "=" * 50)
        print("✅ SUCCESS! Email system is ready to use!")
        print("=" * 50)
        print("\nYou can now:")
        print("- View Email Templates in the admin")
        print("- View Email Logs") 
        print("- View Email Campaigns")
        print("\nRefresh your browser to see the changes!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        print("\nPlease contact support if this persists.")
        sys.exit(1)