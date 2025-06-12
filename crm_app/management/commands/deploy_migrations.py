"""
Management command to handle migrations during deployment
Can be added to Render's build command
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Run migrations and create initial email templates'

    def handle(self, *args, **options):
        self.stdout.write('Running database migrations...')
        
        try:
            # Run migrations
            call_command('migrate', verbosity=2)
            self.stdout.write(self.style.SUCCESS('✓ Migrations completed successfully'))
            
            # Create initial email templates
            self.stdout.write('\nCreating initial email templates...')
            call_command('create_email_templates')
            self.stdout.write(self.style.SUCCESS('✓ Email templates created'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during deployment: {str(e)}'))
            raise