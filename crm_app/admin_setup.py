from django.http import HttpResponse
from django.contrib.auth import get_user_model

def create_admin_view(request):
    """Simple view to create admin user - for setup only"""
    User = get_user_model()
    
    if User.objects.filter(username='admin').exists():
        return HttpResponse('✅ Admin user already exists!<br>Username: admin<br>Password: bmasia123<br><a href="/admin/">Go to Admin</a>')
    
    try:
        admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@bmasia.com',
            password='bmasia123',
            first_name='BMAsia',
            last_name='Admin',
            role='Admin'
        )
        
        return HttpResponse('''
        ✅ Admin user created successfully!<br><br>
        <strong>Username:</strong> admin<br>
        <strong>Password:</strong> bmasia123<br><br>
        <a href="/admin/" style="background: #1976d2; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Go to Admin Interface</a>
        ''')
        
    except Exception as e:
        return HttpResponse(f'❌ Error creating admin user: {e}')