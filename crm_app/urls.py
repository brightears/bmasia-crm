from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from . import views, admin_views

# Create a router and register our viewsets
router = DefaultRouter()
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'companies', views.CompanyViewSet, basename='company')
router.register(r'contacts', views.ContactViewSet, basename='contact')
router.register(r'notes', views.NoteViewSet, basename='note')
router.register(r'tasks', views.TaskViewSet, basename='task')
router.register(r'opportunities', views.OpportunityViewSet, basename='opportunity')
router.register(r'opportunity-activities', views.OpportunityActivityViewSet, basename='opportunityactivity')
router.register(r'contracts', views.ContractViewSet, basename='contract')
router.register(r'invoices', views.InvoiceViewSet, basename='invoice')
router.register(r'audit-logs', views.AuditLogViewSet, basename='auditlog')
router.register(r'dashboard', views.DashboardViewSet, basename='dashboard')
router.register(r'auth', views.AuthViewSet, basename='auth')

# The API URLs are now determined automatically by the router.
urlpatterns = [
    path('api/v1/', include(router.urls)),
    path('api/auth/token/', obtain_auth_token, name='api_token_auth'),
    
    # Admin custom views
    path('admin/send-email/', admin_views.send_email_view, name='admin_send_email'),
    path('admin/send-email/<uuid:template_id>/', admin_views.send_email_view, name='admin_send_email_template'),
    path('admin/send-email/company/<uuid:company_id>/', admin_views.send_email_view, name='admin_send_email_company'),
    path('admin/bulk-email/<uuid:template_id>/', admin_views.preview_bulk_email_view, name='admin_bulk_email'),
]