"""Signals for CRM app"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Company
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