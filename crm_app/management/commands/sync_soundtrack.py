"""Management command to sync Soundtrack zones and check offline alerts"""
from django.core.management.base import BaseCommand
from crm_app.services.soundtrack_api import soundtrack_api
from crm_app.services.offline_alert_service import offline_alert_service


class Command(BaseCommand):
    help = 'Sync all Soundtrack zones and check for offline alerts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=str,
            help='Sync zones for a specific company ID only',
        )
        parser.add_argument(
            '--skip-alerts',
            action='store_true',
            help='Skip offline alert checking after sync',
        )

    def handle(self, *args, **options):
        company_id = options.get('company_id')
        skip_alerts = options.get('skip_alerts', False)

        if company_id:
            # Sync single company
            from crm_app.models import Company
            try:
                company = Company.objects.get(id=company_id)
                if not company.soundtrack_account_id:
                    self.stdout.write(
                        self.style.ERROR(f'Company "{company.name}" has no Soundtrack account ID configured')
                    )
                    return

                self.stdout.write(f'Starting Soundtrack zone sync for {company.name}...')
                synced, errors = soundtrack_api.sync_company_zones(company)
                self.stdout.write(
                    self.style.SUCCESS(f'Synced {synced} zones for {company.name}, {errors} errors')
                )
            except Company.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Company with ID {company_id} not found')
                )
        else:
            # Sync all companies
            self.stdout.write('Starting Soundtrack zone sync for all companies...')
            synced, errors = soundtrack_api.sync_all_zones()
            self.stdout.write(
                self.style.SUCCESS(f'Synced {synced} zones across all companies, {errors} errors')
            )

        # Check for offline alerts (unless skipped)
        if not skip_alerts:
            self.stdout.write('Checking for offline zones and sending alerts...')
            alerts_created, notifications_sent = offline_alert_service.check_and_alert()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Offline check complete: {alerts_created} new alerts, {notifications_sent} notifications sent'
                )
            )
