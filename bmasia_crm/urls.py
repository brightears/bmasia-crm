"""
URL configuration for bmasia_crm project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from crm_app.admin_setup import create_admin_view
from crm_app.views import debug_soundtrack_api
from django.http import HttpResponse
import subprocess
import os

def reset_admin_view(request):
    """Reset admin user - for troubleshooting"""
    try:
        from crm_app.models import User
        
        # Delete existing admin users
        deleted_count = User.objects.filter(username='admin').delete()[0]
        
        # Create fresh admin user
        admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@bmasia.com',
            password='bmasia123',
            first_name='BMAsia',
            last_name='Admin',
            role='Admin'
        )
        
        return HttpResponse(f'''
        <h2>✅ Admin Reset Successful!</h2>
        <p>Deleted {deleted_count} existing admin users</p>
        <p>Created fresh admin user:</p>
        <strong>Username:</strong> admin<br>
        <strong>Password:</strong> bmasia123<br><br>
        <a href="/admin/" style="background: #1976d2; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Go to Admin Login</a>
        ''')
        
    except Exception as e:
        # Try fallback with Django's built-in User
        try:
            from django.contrib.auth.models import User as BaseUser
            BaseUser.objects.filter(username='admin').delete()
            BaseUser.objects.create_superuser('admin', 'admin@bmasia.com', 'bmasia123')
            return HttpResponse(f'''
            <h2>✅ Fallback Admin Created!</h2>
            <p>Created using Django's base User model:</p>
            <strong>Username:</strong> admin<br>
            <strong>Password:</strong> bmasia123<br><br>
            <a href="/admin/" style="background: #1976d2; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Go to Admin Login</a>
            ''')
        except Exception as e2:
            return HttpResponse(f'❌ Error: {e}<br>❌ Fallback Error: {e2}')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('crm_app.urls')),
    path('api-auth/', include('rest_framework.urls')),
    # Setup endpoint to create admin user
    path('setup-admin/', create_admin_view, name='setup_admin'),
    path('reset-admin/', reset_admin_view, name='reset_admin'),
    path('debug-soundtrack/', debug_soundtrack_api, name='debug_soundtrack'),
    # Redirect root to admin for now
    path('', RedirectView.as_view(url='/admin/', permanent=False)),
]
