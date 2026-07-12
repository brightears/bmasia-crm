"""Signals for CRM app"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import Company, Contract, QuoteLineItem
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Company)
def sync_soundtrack_zones_on_save(sender, instance, created, **kwargs):
    """Automatically sync zones when Soundtrack account ID is added or changed"""
    if instance.soundtrack_account_id:
        original = getattr(instance, '_original_soundtrack_account_id', None)
        changed = instance.soundtrack_account_id != original
        if created or changed:
            from .services.soundtrack_api import soundtrack_api
            try:
                synced, errors = soundtrack_api.sync_company_zones(instance)
                if synced > 0:
                    logger.info(f"Auto-synced {synced} zones for {instance.name}")
            except Exception as e:
                logger.error(f"Error auto-syncing zones for {instance.name}: {str(e)}")
    instance._original_soundtrack_account_id = instance.soundtrack_account_id


@receiver(post_save, sender=Contract)
def handle_contract_termination(sender, instance, created, **kwargs):
    """
    When a contract is 'Cancelled', automatically:
    1. Close all active ContractZone relationships (set end_date, is_active=False)
    2. Mark all zones as 'cancelled'

    Fix 2026-07-02: gate was 'Terminated', which is NOT a valid Contract status
    (valid: Draft/Sent/Active/Renewed/Expired/Cancelled) — so this never fired and zones
    were never released on cancellation. Idempotent: the active-links filter + the status
    guard below make repeat saves a no-op.
    """
    # Only run for existing contracts (not new ones)
    if created:
        return

    # Only run when the contract is Cancelled
    if instance.status != 'Cancelled':
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


@receiver(post_delete, sender=QuoteLineItem)
def resync_quote_total_on_delete(sender, instance, **kwargs):
    """Re-sync the parent quote's totals when a line item is deleted, so a quote's stated total
    always matches its remaining lines on every write path (self-audit 2026-07-02)."""
    from .models import Quote
    if instance.quote_id and Quote.objects.filter(pk=instance.quote_id).exists():
        instance.resync_quote_total()