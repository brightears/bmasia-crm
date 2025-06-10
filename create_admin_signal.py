from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth import get_user_model

@receiver(post_migrate)
def create_admin_user(sender, **kwargs):
    """Create admin user after migration"""
    if sender.name == 'crm_app':
        User = get_user_model()
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@bmasia.com',
                password='bmasia123',
                first_name='BMAsia',
                last_name='Admin',
                role='Admin'
            )
            print('✅ Admin user created: admin / bmasia123')