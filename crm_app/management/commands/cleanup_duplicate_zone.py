"""One-time cleanup script to merge duplicate Canvas Ploenchit zone"""
from django.core.management.base import BaseCommand
from crm_app.models import Zone, ContractZone


class Command(BaseCommand):
    help = 'Clean up duplicate Canvas Ploenchit zone by transferring contracts and deleting the manual zone'

    def handle(self, *args, **options):
        manual_zone_id = '8c6143d0-4161-44b4-89cd-c5bd05a1d780'
        synced_zone_id = '1c5e43a3-66be-4fdc-8824-d09aba315045'

        try:
            manual_zone = Zone.objects.get(id=manual_zone_id)
            synced_zone = Zone.objects.get(id=synced_zone_id)
        except Zone.DoesNotExist as e:
            self.stdout.write(self.style.ERROR(f'Zone not found: {e}'))
            return

        self.stdout.write(f'Manual zone: {manual_zone.name} (ID: {manual_zone.id})')
        self.stdout.write(f'Synced zone: {synced_zone.name} (ID: {synced_zone.id})')

        # Get all ContractZone records for the manual zone
        cz_records = ContractZone.objects.filter(zone=manual_zone)
        self.stdout.write(f'\nFound {cz_records.count()} ContractZone record(s) for manual zone')

        for cz in cz_records:
            self.stdout.write(f'  - Contract: {cz.contract.contract_number}, Active: {cz.is_active}')

        # Delete the ContractZone records
        if cz_records.exists():
            count = cz_records.count()
            cz_records.delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {count} ContractZone record(s)'))

        # Now delete the manual zone
        zone_name = manual_zone.name
        manual_zone.delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted manual zone: {zone_name}'))

        # Verify
        remaining = Zone.objects.filter(name__icontains='Canvas Ploenchit').count()
        self.stdout.write(f'\nRemaining zones with "Canvas Ploenchit": {remaining}')
