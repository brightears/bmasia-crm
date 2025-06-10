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
from django.http import HttpResponse
import subprocess
import os

def reset_admin_view(request):
    """Reset admin user - for troubleshooting"""
    try:
        # Run the reset script
        result = subprocess.run(['python', 'reset_admin.py'], 
                              capture_output=True, text=True, 
                              cwd=os.path.dirname(__file__))
        return HttpResponse(f'''
        <h2>Admin Reset Result:</h2>
        <pre>{result.stdout}</pre>
        <pre>{result.stderr}</pre>
        <br>
        <a href="/admin/" style="background: #1976d2; color: white; padding: 10px 20px; text-decoration: none;">Try Admin Login</a>
        ''')
    except Exception as e:
        return HttpResponse(f'Error: {e}')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('crm_app.urls')),
    path('api-auth/', include('rest_framework.urls')),
    # Setup endpoint to create admin user
    path('setup-admin/', create_admin_view, name='setup_admin'),
    path('reset-admin/', reset_admin_view, name='reset_admin'),
    # Redirect root to admin for now
    path('', RedirectView.as_view(url='/admin/', permanent=False)),
]
