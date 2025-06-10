from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Create admin user for BMAsia CRM'

    def handle(self, *args, **options):
        User = get_user_model()
        
        # Check if admin user already exists
        if User.objects.filter(username='admin').exists():
            self.stdout.write(
                self.style.SUCCESS('✅ Admin user already exists!')
            )
            return
        
        # Create admin user
        try:
            admin_user = User.objects.create_superuser(
                username='admin',
                email='admin@bmasia.com',
                password='bmasia123',
                first_name='BMAsia',
                last_name='Admin'
            )
            # Set role for our custom user model
            admin_user.role = 'Admin'
            admin_user.save()
            
            self.stdout.write(
                self.style.SUCCESS('✅ Admin user created successfully!')
            )
            self.stdout.write('Username: admin')
            self.stdout.write('Password: bmasia123')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error creating admin user: {e}')
            )