"""
Custom middleware for development
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.utils.deprecation import MiddlewareMixin

User = get_user_model()


class DevelopmentAuthMiddleware(MiddlewareMixin):
    """
    Middleware to bypass authentication during development
    """
    def process_request(self, request):
        # Only apply in DEBUG mode and for admin URLs
        if settings.DEBUG and request.path.startswith('/admin/'):
            # If user is not authenticated, auto-login as superuser
            if not request.user.is_authenticated:
                try:
                    # Get or create a superuser for development
                    admin_user, created = User.objects.get_or_create(
                        email='admin@bmasia.com',
                        defaults={
                            'first_name': 'Admin',
                            'last_name': 'User',
                            'role': 'Admin',
                            'is_staff': True,
                            'is_superuser': True,
                            'is_active': True,
                        }
                    )
                    if created:
                        admin_user.set_password('bmasia123')
                        admin_user.save()
                    
                    # Auto-login the user
                    login(request, admin_user, backend='django.contrib.auth.backends.ModelBackend')
                except Exception:
                    pass  # Ignore errors, let normal auth flow handle it
        
        return None