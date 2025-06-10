import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bmasia_crm.settings')
django.setup()

from crm_app.models import User

# Create admin user
username = 'admin'
email = 'admin@bmasia.com'  
password = 'bmasia123'

# Check if user exists
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(
        username=username,
        email=email,
        password=password,
        first_name='BMAsia',
        last_name='Admin',
        role='Admin'
    )
    print(f'Admin user created: {username}')
else:
    print('Admin user already exists')