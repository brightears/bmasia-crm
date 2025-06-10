from django.apps import AppConfig


class CrmAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'crm_app'
    
    def ready(self):
        # Import signal to create admin user after migration
        from django.db.models.signals import post_migrate
        from django.dispatch import receiver
        from django.contrib.auth import get_user_model
        
        @receiver(post_migrate, sender=self)
        def create_admin_user(sender, **kwargs):
            """Create admin user after migration"""
            User = get_user_model()
            if not User.objects.filter(username='admin').exists():
                try:
                    User.objects.create_superuser(
                        username='admin',
                        email='admin@bmasia.com',
                        password='bmasia123',
                        first_name='BMAsia',
                        last_name='Admin',
                        role='Admin'
                    )
                    print('✅ Admin user created: admin / bmasia123')
                except Exception as e:
                    print(f'❌ Failed to create admin user: {e}')
