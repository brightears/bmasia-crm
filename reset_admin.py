import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bmasia_crm.settings')
django.setup()

from crm_app.models import User

# Reset admin user
try:
    # Delete existing admin if exists
    User.objects.filter(username='admin').delete()
    
    # Create fresh admin user
    admin_user = User.objects.create_superuser(
        username='admin',
        email='admin@bmasia.com',
        password='bmasia123',
        first_name='BMAsia',
        last_name='Admin',
        role='Admin'
    )
    print('✅ Fresh admin user created: admin / bmasia123')
    
except Exception as e:
    print(f'❌ Error: {e}')
    # Try fallback
    try:
        from django.contrib.auth.models import User as BaseUser
        BaseUser.objects.filter(username='admin').delete()
        BaseUser.objects.create_superuser('admin', 'admin@bmasia.com', 'bmasia123')
        print('✅ Fallback admin user created: admin / bmasia123')
    except Exception as e2:
        print(f'❌ Fallback failed: {e2}')