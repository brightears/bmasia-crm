"""
Management command to initialize database with migrations and superuser
Run with: python manage.py initialize_database

The admin password comes from ADMIN_INITIAL_PASSWORD or an interactive
prompt. It is resolved before anything else runs, and the command refuses
to start when neither is available.
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth import get_user_model

from crm_app.management.admin_password import add_no_input_argument, resolve_admin_password


class Command(BaseCommand):
    help = 'Initialize database with migrations and create superuser'

    def add_arguments(self, parser):
        add_no_input_argument(parser)

    def handle(self, *args, **options):
        admin_password = resolve_admin_password(interactive=options['interactive'])
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
                    password=admin_password,
                )
                self.stdout.write(self.style.SUCCESS('✓ Admin user created successfully (username: admin)'))
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
        self.stdout.write('You can now log in at /admin/ as admin with the password you supplied.')