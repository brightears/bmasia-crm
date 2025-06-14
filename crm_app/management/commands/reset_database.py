from django.core.management.base import BaseCommand
from django.db import connection
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Reset database by dropping all crm_app tables and rerunning migrations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reset without confirmation',
        )

    def handle(self, *args, **options):
        if not options['force']:
            confirm = input("This will DELETE ALL DATA in crm_app tables. Are you sure? (yes/no): ")
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operation cancelled.'))
                return

        with connection.cursor() as cursor:
            self.stdout.write('Dropping all crm_app tables...')
            
            # Get all table names that start with crm_app
            cursor.execute("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename LIKE 'crm_app_%';
            """)
            
            tables = cursor.fetchall()
            
            if not tables:
                self.stdout.write(self.style.WARNING('No crm_app tables found.'))
            else:
                # Drop each table
                for table in tables:
                    table_name = table[0]
                    self.stdout.write(f'Dropping table {table_name}...')
                    cursor.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE;')
            
            # Clear migration history for crm_app
            self.stdout.write('Clearing migration history...')
            cursor.execute("DELETE FROM django_migrations WHERE app = 'crm_app';")
            
        self.stdout.write(self.style.SUCCESS('Tables dropped successfully!'))
        
        # Run migrations
        self.stdout.write('Running migrations...')
        call_command('migrate', 'crm_app')
        
        self.stdout.write(self.style.SUCCESS('Database reset complete!'))