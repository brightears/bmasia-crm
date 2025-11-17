"""
Show which migrations have been applied.
"""
from django.core.management.base import BaseCommand
from django.db.migrations.recorder import MigrationRecorder


class Command(BaseCommand):
    help = 'Show applied migrations for crm_app'

    def handle(self, *args, **options):
        migrations = MigrationRecorder.Migration.objects.filter(
            app='crm_app'
        ).order_by('name')

        self.stdout.write("Applied migrations:")
        for mig in migrations:
            self.stdout.write(f"  {mig.name}")

        self.stdout.write(f"\nTotal: {migrations.count()} migrations applied")
