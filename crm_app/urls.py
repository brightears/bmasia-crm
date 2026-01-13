from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
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
router.register(r'quotes', views.QuoteViewSet, basename='quote')
router.register(r'audit-logs', views.AuditLogViewSet, basename='auditlog')
router.register(r'dashboard', views.DashboardViewSet, basename='dashboard')
router.register(r'campaigns', views.CampaignViewSet, basename='campaign')
router.register(r'automation', views.AutomationViewSet, basename='automation')
router.register(r'email-templates', views.EmailTemplateViewSet, basename='emailtemplate')
router.register(r'email-sequences', views.EmailSequenceViewSet, basename='emailsequence')
router.register(r'sequence-steps', views.SequenceStepViewSet, basename='sequencestep')
router.register(r'sequence-enrollments', views.SequenceEnrollmentViewSet, basename='sequenceenrollment')
router.register(r'sequence-executions', views.SequenceStepExecutionViewSet, basename='sequencestepexecution')
router.register(r'segments', views.CustomerSegmentViewSet, basename='segment')
router.register(r'tickets', views.TicketViewSet, basename='ticket')
router.register(r'ticket-comments', views.TicketCommentViewSet, basename='ticketcomment')
router.register(r'ticket-attachments', views.TicketAttachmentViewSet, basename='ticketattachment')

# Knowledge Base routes
router.register(r'kb/categories', views.KBCategoryViewSet, basename='kb-category')
router.register(r'kb/tags', views.KBTagViewSet, basename='kb-tag')
router.register(r'kb/articles', views.KBArticleViewSet, basename='kb-article')
router.register(r'kb/article-views', views.KBArticleViewViewSet, basename='kb-article-view')
router.register(r'kb/article-ratings', views.KBArticleRatingViewSet, basename='kb-article-rating')
router.register(r'kb/article-relations', views.KBArticleRelationViewSet, basename='kb-article-relation')
router.register(r'kb/article-attachments', views.KBArticleAttachmentViewSet, basename='kb-article-attachment')
router.register(r'kb/ticket-articles', views.TicketKBArticleViewSet, basename='kb-ticket-article')

# Equipment Management routes - Equipment types removed, replaced by Device model
router.register(r'devices', views.DeviceViewSet, basename='device')
router.register(r'zones', views.ZoneViewSet, basename='zone')

# Static Documents routes
router.register(r'static-documents', views.StaticDocumentViewSet, basename='static-document')

# Contract Content Management routes
router.register(r'contract-templates', views.ContractTemplateViewSet, basename='contract-template')
router.register(r'service-package-items', views.ServicePackageItemViewSet, basename='service-package-item')
router.register(r'corporate-pdf-templates', views.CorporatePdfTemplateViewSet, basename='corporate-pdf-template')
router.register(r'contract-documents', views.ContractDocumentViewSet, basename='contract-document')

# Settings routes
router.register(r'seasonal-trigger-dates', views.SeasonalTriggerDateViewSet, basename='seasonal-trigger-date')

# Revenue Dashboard routes
router.register(r'revenue', views.RevenueViewSet, basename='revenue')

# AR Aging routes
router.register(r'ar-aging', views.ARAgingViewSet, basename='ar-aging')

# The API URLs are now determined automatically by the router.
urlpatterns = [
    path('v1/', include(router.urls)),

    # Authentication endpoints
    path('v1/auth/login/', views.AuthViewSet.as_view({'post': 'login'}), name='auth_login'),
    path('v1/auth/refresh/', views.AuthViewSet.as_view({'post': 'refresh'}), name='auth_refresh'),
    path('v1/auth/logout/', views.AuthViewSet.as_view({'post': 'logout'}), name='auth_logout'),
    path('v1/auth/me/', views.AuthViewSet.as_view({'get': 'me'}), name='auth_me'),

    # JWT token endpoints (fallback)
    path('v1/jwt/token/', TokenObtainPairView.as_view(), name='jwt_token_obtain_pair'),
    path('v1/jwt/token/refresh/', TokenRefreshView.as_view(), name='jwt_token_refresh'),
    path('v1/jwt/token/verify/', TokenVerifyView.as_view(), name='jwt_token_verify'),

    # Legacy token auth
    path('auth/token/', obtain_auth_token, name='api_token_auth'),

    # Admin custom views
    path('admin/send-email/', admin_views.send_email_view, name='admin_send_email'),
    path('admin/send-email/<uuid:template_id>/', admin_views.send_email_view, name='admin_send_email_template'),
    path('admin/send-email/company/<uuid:company_id>/', admin_views.send_email_view, name='admin_send_email_company'),
    path('admin/bulk-email/<uuid:template_id>/', admin_views.preview_bulk_email_view, name='admin_bulk_email'),

    # Email preview views
    path('admin/preview-email/', admin_views.preview_email_view, name='admin_preview_email'),
    path('admin/preview-email/<uuid:template_id>/', admin_views.preview_email_view, name='admin_preview_email_template'),
    path('admin/preview-email/company/<uuid:company_id>/', admin_views.preview_email_view, name='admin_preview_email_company'),
    path('admin/preview-template/<uuid:template_id>/', admin_views.preview_template_view, name='admin_preview_template'),
    path('admin/send-test-email/', admin_views.send_test_email_view, name='admin_send_test_email'),
    # Database initialization endpoint (one-time use)
    path('initialize-database/', views.initialize_database, name='initialize_database'),
]