"""Test Soundtrack API integration"""
from django.core.management.base import BaseCommand
from crm_app.models import Company
from crm_app.services.soundtrack_api import soundtrack_api
import json


class Command(BaseCommand):
    help = 'Test Soundtrack API connection and fetch zones'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--account-id',
            type=str,
            help='Soundtrack account ID to test',
        )
        parser.add_argument(
            '--company-name',
            type=str,
            help='Company name to test',
        )
    
    def handle(self, *args, **options):
        account_id = options.get('account_id')
        company_name = options.get('company_name')
        
        if account_id:
            # Test with provided account ID
            self.stdout.write(f"Testing Soundtrack API with account ID: {account_id}")
            
            # Test account details
            self.stdout.write("\n1. Testing account details fetch...")
            account_data = soundtrack_api.get_account_details(account_id)
            if account_data:
                self.stdout.write(self.style.SUCCESS(f"✓ Account found: {json.dumps(account_data, indent=2)}"))
            else:
                self.stdout.write(self.style.ERROR("✗ Could not fetch account details"))
            
            # Test zones fetch
            self.stdout.write("\n2. Testing zones fetch...")
            zones = soundtrack_api.get_account_zones(account_id)
            if zones:
                self.stdout.write(self.style.SUCCESS(f"✓ Found {len(zones)} zones:"))
                for zone in zones:
                    self.stdout.write(f"   - {zone.get('name', 'Unknown')}: {zone.get('status', 'Unknown status')}")
            else:
                self.stdout.write(self.style.ERROR("✗ Could not fetch zones"))
        
        elif company_name:
            # Test with existing company
            try:
                company = Company.objects.get(name=company_name)
                if not company.soundtrack_account_id:
                    self.stdout.write(self.style.ERROR(f"Company '{company_name}' has no Soundtrack account ID"))
                    return
                
                self.stdout.write(f"Testing sync for company: {company_name}")
                synced, errors = soundtrack_api.sync_company_zones(company)
                
                if synced > 0:
                    self.stdout.write(self.style.SUCCESS(f"✓ Successfully synced {synced} zones"))
                    
                    # Show zone status
                    for zone in company.zones.all():
                        self.stdout.write(f"   - {zone.name}: {zone.get_status_display()}")
                else:
                    self.stdout.write(self.style.ERROR(f"✗ No zones synced, {errors} errors"))
                    
            except Company.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Company '{company_name}' not found"))
        
        else:
            # Show API configuration status
            self.stdout.write("Soundtrack API Configuration:")
            self.stdout.write(f"API Token: {'✓ Set' if soundtrack_api.api_token else '✗ Not set'}")
            self.stdout.write(f"Client ID: {'✓ Set' if soundtrack_api.client_id else '✗ Not set'}")
            self.stdout.write(f"Client Secret: {'✓ Set' if soundtrack_api.client_secret else '✗ Not set'}")
            
            # Test with Hilton Pattaya if exists
            self.stdout.write("\nTesting with Hilton Pattaya account ID...")
            test_account_id = "QWNjb3VudCwsMXN4N242NTZyeTgv"
            zones = soundtrack_api.get_account_zones(test_account_id)
            if zones:
                self.stdout.write(self.style.SUCCESS(f"✓ API is working! Found {len(zones)} zones"))
            else:
                self.stdout.write(self.style.ERROR("✗ Could not connect to API"))