#!/usr/bin/env python3
"""
Auto-create admin user for BMAsia CRM
Run this after deployment to create the admin user
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bmasia_crm.settings')
sys.path.append('/opt/render/project/src')

django.setup()

from django.contrib.auth import get_user_model

def create_admin_user():
    User = get_user_model()
    
    # Check if admin user already exists
    if User.objects.filter(username='admin').exists():
        print("✅ Admin user already exists!")
        return
    
    # Create admin user
    admin_user = User.objects.create_user(
        username='admin',
        email='admin@bmasia.com',
        password='bmasia123',
        first_name='BMAsia',
        last_name='Admin',
        role='Admin',
        is_staff=True,
        is_superuser=True,
        is_active=True
    )
    
    print("✅ Admin user created successfully!")
    print("Username: admin")
    print("Password: bmasia123")
    print("You can now login at: https://bmasia-crm.onrender.com/admin")

if __name__ == "__main__":
    create_admin_user()