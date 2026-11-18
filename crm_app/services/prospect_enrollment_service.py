"""
Auto-enrollment service for prospect sequences.

Handles automatic enrollment of contacts into sales sequences
based on trigger events (new opportunity, stale deal, quote sent).
"""

import logging
from datetime import timedelta

from django.utils import timezone

from crm_app.models import (
    ProspectSequence,
    ProspectEnrollment,
    ProspectStepExecution,
    Opportunity,
    Contact,
)

logger = logging.getLogger(__name__)


class ProspectEnrollmentService:
    """Service for auto-enrolling contacts into prospect sequences"""

    @staticmethod
    def auto_enroll_new_opportunity(opportunity):
        """
        Called when a new Opportunity is created.
        Finds active sequences with trigger_type='new_opportunity'
        whose target_stages include the opportunity's current stage,
        and enrolls the primary contact.
        """
        if not opportunity.company:
            return

        # Find the primary contact for this company
        contact = Contact.objects.filter(
            company=opportunity.company,
            is_primary=True,
        ).first()

        if not contact:
            # Fall back to any contact with email
            contact = Contact.objects.filter(
                company=opportunity.company,
                email__isnull=False,
            ).exclude(email='').first()

        if not contact or not contact.email:
            logger.info(
                f"No enrollable contact for opportunity {opportunity.id} "
                f"({opportunity.company.name}) — skipping auto-enrollment"
            )
            return

        # Find matching sequences
        sequences = ProspectSequence.objects.filter(
            trigger_type='new_opportunity',
            is_active=True,
        ).prefetch_related('steps')

        enrolled_count = 0
        for sequence in sequences:
            # Check if target_stages matches
            if sequence.target_stages and opportunity.stage not in sequence.target_stages:
                continue

            # Check billing_entity filter
            if sequence.billing_entity and opportunity.company.billing_entity != sequence.billing_entity:
                continue

            # Check max enrollments per company
            active_count = ProspectEnrollment.objects.filter(
                sequence=sequence,
                opportunity__company=opportunity.company,
                status='active',
            ).count()
            if active_count >= sequence.max_enrollments_per_company:
                continue

            # Check if already enrolled (same contact + opportunity)
            already_enrolled = ProspectEnrollment.objects.filter(
                sequence=sequence,
                opportunity=opportunity,
                contact=contact,
                status__in=['active', 'completed'],
            ).exists()
            if already_enrolled:
                continue

            # Enroll
            enrollment = ProspectEnrollment.objects.create(
                sequence=sequence,
                opportunity=opportunity,
                contact=contact,
                status='active',
                enrollment_source='auto_trigger',
            )

            # Schedule first step
            first_step = sequence.steps.order_by('step_number').first()
            if first_step:
                ProspectStepExecution.objects.create(
                    enrollment=enrollment,
                    step=first_step,
                    scheduled_for=timezone.now() + timedelta(days=first_step.delay_days),
                )

            enrolled_count += 1
            logger.info(
                f"Auto-enrolled {contact.name} ({contact.email}) in "
                f"'{sequence.name}' for opportunity '{opportunity.name}'"
            )

        return enrolled_count

    @staticmethod
    def auto_enroll_stale_deals():
        """
        Called by the cron job.
        Finds opportunities that have been stale (no stage change)
        for longer than the sequence's stale_days_threshold,
        and enrolls their primary contact in the stale_deal sequence.

        Returns the number of new enrollments created.
        """
        sequences = ProspectSequence.objects.filter(
            trigger_type='stale_deal',
            is_active=True,
        ).prefetch_related('steps')

        if not sequences.exists():
            return 0

        enrolled_count = 0

        for sequence in sequences:
            target_stages = sequence.target_stages or []
            threshold_days = sequence.stale_days_threshold or 14

            # Find stale opportunities
            cutoff = timezone.now() - timedelta(days=threshold_days)

            stale_opps = Opportunity.objects.filter(
                is_active=True,
                stage__in=target_stages if target_stages else ['Contacted', 'Quotation Sent'],
            ).select_related('company')

            # Filter by stage_changed_at or updated_at
            stale_opps = stale_opps.filter(
                **{
                    'stage_changed_at__lte': cutoff,
                }
            ) | stale_opps.filter(
                stage_changed_at__isnull=True,
                updated_at__lte=cutoff,
            )

            # Filter by billing_entity if set
            if sequence.billing_entity:
                stale_opps = stale_opps.filter(
                    company__billing_entity=sequence.billing_entity,
                )

            for opp in stale_opps.distinct():
                # Check max enrollments per company
                active_count = ProspectEnrollment.objects.filter(
                    sequence=sequence,
                    opportunity__company=opp.company,
                    status='active',
                ).count()
                if active_count >= sequence.max_enrollments_per_company:
                    continue

                # Check if this opportunity was already enrolled in this sequence
                already_enrolled = ProspectEnrollment.objects.filter(
                    sequence=sequence,
                    opportunity=opp,
                ).exists()
                if already_enrolled:
                    continue

                # Find primary contact
                contact = Contact.objects.filter(
                    company=opp.company,
                    is_primary=True,
                ).first()
                if not contact:
                    contact = Contact.objects.filter(
                        company=opp.company,
                        email__isnull=False,
                    ).exclude(email='').first()

                if not contact or not contact.email:
                    continue

                # Enroll
                enrollment = ProspectEnrollment.objects.create(
                    sequence=sequence,
                    opportunity=opp,
                    contact=contact,
                    status='active',
                    enrollment_source='auto_trigger',
                )

                first_step = sequence.steps.order_by('step_number').first()
                if first_step:
                    ProspectStepExecution.objects.create(
                        enrollment=enrollment,
                        step=first_step,
                        scheduled_for=timezone.now() + timedelta(days=first_step.delay_days),
                    )

                enrolled_count += 1
                logger.info(
                    f"Auto-enrolled stale deal: {contact.name} in '{sequence.name}' "
                    f"for '{opp.name}' (stale {opp.days_in_stage} days)"
                )

        return enrolled_count

    @staticmethod
    def auto_enroll_quote_sent(quote):
        """
        Called when a Quote status changes to 'Sent'.
        Finds active sequences with trigger_type='quote_sent'
        and enrolls the quote's contact or company's primary contact.
        """
        if not quote.company:
            return 0

        # Use the quote's contact if set, otherwise primary contact
        contact = quote.contact if hasattr(quote, 'contact') and quote.contact else None
        if not contact:
            contact = Contact.objects.filter(
                company=quote.company,
                is_primary=True,
            ).first()
        if not contact:
            contact = Contact.objects.filter(
                company=quote.company,
                email__isnull=False,
            ).exclude(email='').first()

        if not contact or not contact.email:
            return 0

        # Find the opportunity linked to this quote
        opportunity = quote.opportunity
        if not opportunity:
            return 0

        sequences = ProspectSequence.objects.filter(
            trigger_type='quote_sent',
            is_active=True,
        ).prefetch_related('steps')

        enrolled_count = 0
        for sequence in sequences:
            # Check target_stages
            if sequence.target_stages and opportunity.stage not in sequence.target_stages:
                continue

            # Check billing_entity
            if sequence.billing_entity and quote.company.billing_entity != sequence.billing_entity:
                continue

            # Check max enrollments
            active_count = ProspectEnrollment.objects.filter(
                sequence=sequence,
                opportunity__company=quote.company,
                status='active',
            ).count()
            if active_count >= sequence.max_enrollments_per_company:
                continue

            # Check already enrolled
            already_enrolled = ProspectEnrollment.objects.filter(
                sequence=sequence,
                opportunity=opportunity,
                contact=contact,
            ).exists()
            if already_enrolled:
                continue

            enrollment = ProspectEnrollment.objects.create(
                sequence=sequence,
                opportunity=opportunity,
                contact=contact,
                status='active',
                enrollment_source='auto_trigger',
            )

            first_step = sequence.steps.order_by('step_number').first()
            if first_step:
                ProspectStepExecution.objects.create(
                    enrollment=enrollment,
                    step=first_step,
                    scheduled_for=timezone.now() + timedelta(days=first_step.delay_days),
                )

            enrolled_count += 1
            logger.info(
                f"Auto-enrolled quote_sent: {contact.name} in '{sequence.name}' "
                f"for quote '{quote.quote_number}'"
            )

        return enrolled_count
