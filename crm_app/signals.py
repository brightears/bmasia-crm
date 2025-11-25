"""Signals for CRM app"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Company, Contract
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Company)
def sync_soundtrack_zones_on_save(sender, instance, created, **kwargs):
    """Automatically sync zones when Soundtrack account ID is added or changed"""
    if instance.soundtrack_account_id:
        # Check if this is a new account ID or if it changed
        if created or (not created and instance.tracker.has_changed('soundtrack_account_id')):
            from .services.soundtrack_api import soundtrack_api
            try:
                synced, errors = soundtrack_api.sync_company_zones(instance)
                if synced > 0:
                    logger.info(f"Auto-synced {synced} zones for {instance.name}")
            except Exception as e:
                logger.error(f"Error auto-syncing zones for {instance.name}: {str(e)}")


@receiver(post_save, sender=Contract)
def handle_contract_termination(sender, instance, created, **kwargs):
    """
    When contract status changes to 'Terminated', automatically:
    1. Close all active ContractZone relationships (set end_date, is_active=False)
    2. Mark all zones as 'cancelled'

    This ensures data integrity and automatic sync between contracts and zones.
    """
    # Only run for existing contracts (not new ones)
    if created:
        return

    # Only run if status is Terminated
    if instance.status != 'Terminated':
        return

    today = timezone.now().date()

    # Get all active ContractZone links for this contract
    active_links = instance.contract_zones.filter(is_active=True)

    for link in active_links:
        # Close the ContractZone relationship
        link.end_date = today
        link.is_active = False
        link.save(update_fields=['end_date', 'is_active'])

        # Mark zone as cancelled (if not already cancelled)
        if link.zone.status != 'cancelled':
            link.zone.mark_as_cancelled()
            logger.info(f"Marked zone {link.zone.name} as cancelled due to contract {instance.contract_number} termination")