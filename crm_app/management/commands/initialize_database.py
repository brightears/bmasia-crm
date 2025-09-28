"""
Management command to initialize database with migrations and superuser
Run with: python manage.py initialize_database
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Initialize database with migrations and create superuser'

    def handle(self, *args, **options):
        self.stdout.write('Starting database initialization...')

        # Run migrations
        self.stdout.write('Running migrations...')
        try:
            call_command('migrate', '--noinput')
            self.stdout.write(self.style.SUCCESS('✓ Migrations completed successfully'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Migration failed: {str(e)}'))
            return

        # Create superuser
        User = get_user_model()
        if not User.objects.filter(username='admin').exists():
            self.stdout.write('Creating admin superuser...')
            try:
                User.objects.create_superuser(
                    username='admin',
                    email='admin@bmasiamusic.com',
                    password='bmasia123'
                )
                self.stdout.write(self.style.SUCCESS('✓ Admin user created successfully'))
                self.stdout.write('  Username: admin')
                self.stdout.write('  Password: bmasia123')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Failed to create admin: {str(e)}'))
        else:
            self.stdout.write(self.style.SUCCESS('✓ Admin user already exists'))

        # Create initial email templates
        self.stdout.write('Setting up email templates...')
        try:
            call_command('create_email_templates')
            self.stdout.write(self.style.SUCCESS('✓ Email templates created'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'⚠ Email templates setup skipped: {str(e)}'))

        self.stdout.write(self.style.SUCCESS('\n✓ Database initialization complete!'))
        self.stdout.write('You can now log in at /admin/ with admin/bmasia123')