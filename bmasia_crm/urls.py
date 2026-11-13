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
from crm_app.login_throttle import throttled_obtain_auth_token
from crm_app.rene_mcp_server import RenePhase2MCPView
from crm_app.views import email_tracking_pixel

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('crm_app.urls')),  # API endpoints under /api/
    path('api-auth/', include('rest_framework.urls')),
    path(
        'mcp/rene-phase2/',
        RenePhase2MCPView.as_view(),
        name='rene_phase2_mcp',
    ),
    path('', include('mcp_server.urls')),  # MCP server at /mcp/
    path('api-token-auth/', throttled_obtain_auth_token, name='api_token_auth'),  # DRF token auth (rate limited)
    # SECURITY 2026-07-02: removed unauthenticated setup-admin/reset-admin routes — they granted full
    # superuser takeover with a fixed password. Use the `createadmin` / `reset_admin` management commands.
    # Email open tracking pixel (unauthenticated - called by email clients)
    path('t/<str:token>/', email_tracking_pixel, name='email_tracking_pixel'),
    # For now, redirect root to admin until React frontend is properly deployed
    path('', RedirectView.as_view(url='/admin/', permanent=False)),
]
