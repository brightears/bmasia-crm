#!/usr/bin/env python
"""
Quick script to fix the admin user's role from Sales to Admin
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bmasia_crm.settings')
django.setup()

from crm_app.models import User

# Update admin user role
try:
    admin_user = User.objects.get(username='admin')
    print(f"Current role: {admin_user.role}")
    admin_user.role = 'Admin'
    admin_user.save()
    print(f"Updated role to: {admin_user.role}")
    print("✅ Admin user role updated successfully!")
except User.DoesNotExist:
    print("❌ Admin user not found")
except Exception as e:
    print(f"❌ Error: {e}")