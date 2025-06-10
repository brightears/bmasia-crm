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

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    django.setup()
    from django.contrib.auth import get_user_model
    
    def create_admin_user():
        User = get_user_model()
        
        # Check if any admin user already exists
        if User.objects.filter(is_superuser=True).exists():
            print("✅ Admin user already exists!")
            return
        
        # Create admin user using create_superuser
        try:
            admin_user = User.objects.create_superuser(
                username='admin',
                email='admin@bmasia.com',
                password='bmasia123',
                first_name='BMAsia',
                last_name='Admin'
            )
            # Set additional fields for our custom user model
            admin_user.role = 'Admin'
            admin_user.save()
            
            print("✅ Admin user created successfully!")
            print("Username: admin")
            print("Password: bmasia123")
            print("You can now login at the admin interface")
            
        except Exception as e:
            print(f"❌ Error creating admin user: {e}")
            # Fallback: try creating basic superuser
            try:
                from django.contrib.auth.models import User as BaseUser
                if not BaseUser.objects.filter(username='admin').exists():
                    BaseUser.objects.create_superuser('admin', 'admin@bmasia.com', 'bmasia123')
                    print("✅ Fallback admin user created!")
            except Exception as e2:
                print(f"❌ Fallback also failed: {e2}")
    
    if __name__ == "__main__":
        create_admin_user()
        
except Exception as e:
    print(f"❌ Django setup failed: {e}")
    print("Continuing without admin user creation...")