"""
Auto-enrollment service for automatically enrolling contacts in email sequences
based on triggers like contract expiry, invoice overdue, etc.

This service handles the automatic enrollment logic for the Email Automations system.
It processes different trigger types (renewal, payment, quarterly) and creates
appropriate sequence enrollments when conditions are met.
"""
from datetime import date, timedelta
from django.db.models import Q
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class AutoEnrollmentService:
    """Service for processing automatic sequence enrollments."""

    def process_all_triggers(self):
        """
        Process all auto-enrollment triggers.

        Returns:
            dict: Summary of enrollments created per trigger type
        """
        results = {
            'renewal': self.process_renewal_triggers(),
            'payment': self.process_payment_triggers(),
            'quarterly': self.process_quarterly_triggers(),
        }

        total_enrolled = sum(results.values())
        logger.info(f"Auto-enrollment complete: {total_enrolled} total enrollments created")

        return results

    def process_renewal_triggers(self):
        """
        Auto-enroll contacts when contracts reach the trigger days before expiry.

        For each active auto_renewal sequence:
        1. Find contracts expiring in X days (based on sequence steps)
        2. Check if contact already enrolled for this contract
        3. Create enrollment if not already enrolled

        Returns:
            int: Number of enrollments created
        """
        from crm_app.models import EmailSequence, SequenceEnrollment, Contract, SequenceStep

        enrolled_count = 0

        # Find all active auto_renewal sequences
        # Note: Assumes EmailSequence has sequence_type field (will be added in migration)
        sequences = EmailSequence.objects.filter(
            sequence_type='auto_renewal',
            status='active'
        )

        for sequence in sequences:
            # Get the first step to determine trigger timing
            first_step = sequence.steps.order_by('step_number').first()
            if not first_step or not first_step.delay_days:
                logger.warning(f"Sequence {sequence.name} has no valid first step, skipping")
                continue

            # The delay_days on first step indicates when to enroll
            # e.g., if first step has delay_days=30, enroll 30 days before expiry
            trigger_days = first_step.delay_days
            target_date = date.today() + timedelta(days=trigger_days)

            # Find contracts expiring on the target date
            # Note: Contract model uses 'Active' (capital A) for status
            contracts = Contract.objects.filter(
                end_date=target_date,
                status='Active'
            ).select_related('company')

            logger.info(f"Found {contracts.count()} contracts expiring on {target_date} for sequence {sequence.name}")

            for contract in contracts:
                # Check if already enrolled for this contract
                # Note: Assumes SequenceEnrollment has trigger_entity_type and trigger_entity_id fields
                existing = SequenceEnrollment.objects.filter(
                    sequence=sequence,
                    trigger_entity_type='contract',
                    trigger_entity_id=str(contract.id)
                ).exists()

                if existing:
                    logger.debug(f"Contract {contract.contract_number} already enrolled in {sequence.name}")
                    continue

                # Get primary contact from company
                contact = contract.company.contacts.filter(
                    is_active=True
                ).order_by('-is_primary_contact').first()

                if not contact:
                    logger.warning(f"No active contact for contract {contract.contract_number} (company: {contract.company.name})")
                    continue

                # Create enrollment
                try:
                    enrollment = SequenceEnrollment.objects.create(
                        sequence=sequence,
                        contact=contact,
                        company=contract.company,
                        status='active',
                        enrollment_source='auto_trigger',
                        trigger_entity_type='contract',
                        trigger_entity_id=str(contract.id),
                        current_step_number=1
                    )
                    enrolled_count += 1
                    logger.info(f"Auto-enrolled {contact.email} in {sequence.name} for contract {contract.contract_number}")

                    # Schedule first step execution
                    self._schedule_next_step(enrollment)

                except Exception as e:
                    logger.error(f"Failed to enroll contact {contact.email} in {sequence.name}: {str(e)}")

        return enrolled_count

    def process_payment_triggers(self):
        """
        Auto-enroll contacts when invoices become overdue.

        Looks for invoices that became overdue based on the sequence's
        first step delay_days configuration.

        Returns:
            int: Number of enrollments created
        """
        from crm_app.models import EmailSequence, SequenceEnrollment, Invoice

        enrolled_count = 0

        sequences = EmailSequence.objects.filter(
            sequence_type='auto_payment',
            status='active'
        )

        for sequence in sequences:
            first_step = sequence.steps.order_by('step_number').first()
            if not first_step:
                logger.warning(f"Sequence {sequence.name} has no steps, skipping")
                continue

            # Days overdue to trigger (e.g., 7 days overdue)
            days_overdue = first_step.delay_days or 7
            target_date = date.today() - timedelta(days=days_overdue)

            # Find invoices that became overdue on target date
            invoices = Invoice.objects.filter(
                due_date=target_date,
                status__in=['Sent', 'Overdue']
            ).exclude(
                status='Paid'
            ).select_related('contract__company')

            logger.info(f"Found {invoices.count()} invoices overdue as of {target_date} for sequence {sequence.name}")

            for invoice in invoices:
                existing = SequenceEnrollment.objects.filter(
                    sequence=sequence,
                    trigger_entity_type='invoice',
                    trigger_entity_id=str(invoice.id)
                ).exists()

                if existing:
                    logger.debug(f"Invoice {invoice.invoice_number} already enrolled in {sequence.name}")
                    continue

                # Get billing contact or primary contact
                company = invoice.contract.company
                contact = company.contacts.filter(
                    is_active=True
                ).filter(
                    Q(is_billing_contact=True) | Q(is_primary_contact=True)
                ).first()

                if not contact:
                    contact = company.contacts.filter(is_active=True).first()

                if not contact:
                    logger.warning(f"No active contact for invoice {invoice.invoice_number} (company: {company.name})")
                    continue

                try:
                    enrollment = SequenceEnrollment.objects.create(
                        sequence=sequence,
                        contact=contact,
                        company=company,
                        status='active',
                        enrollment_source='auto_trigger',
                        trigger_entity_type='invoice',
                        trigger_entity_id=str(invoice.id),
                        current_step_number=1
                    )
                    enrolled_count += 1
                    logger.info(f"Auto-enrolled {contact.email} in {sequence.name} for invoice {invoice.invoice_number}")

                    # Schedule first step execution
                    self._schedule_next_step(enrollment)

                except Exception as e:
                    logger.error(f"Failed to enroll contact {contact.email} in {sequence.name}: {str(e)}")

        return enrolled_count

    def process_quarterly_triggers(self):
        """
        Auto-enroll companies for quarterly check-ins.

        Enrolls companies with active contracts that haven't been checked
        in the last 90 days.

        Returns:
            int: Number of enrollments created
        """
        from crm_app.models import EmailSequence, SequenceEnrollment, Company, Contract

        enrolled_count = 0

        sequences = EmailSequence.objects.filter(
            sequence_type='auto_quarterly',
            status='active'
        )

        for sequence in sequences:
            # Find companies with active contracts
            # Note: Contract model uses 'Active' (capital A) for status
            companies_with_contracts = Company.objects.filter(
                contracts__status='Active'
            ).distinct()

            ninety_days_ago = timezone.now() - timedelta(days=90)

            logger.info(f"Processing {companies_with_contracts.count()} companies for quarterly check-in sequence {sequence.name}")

            for company in companies_with_contracts:
                # Check if enrolled in last 90 days
                recent_enrollment = SequenceEnrollment.objects.filter(
                    sequence=sequence,
                    company=company,
                    enrolled_at__gte=ninety_days_ago
                ).exists()

                if recent_enrollment:
                    logger.debug(f"Company {company.name} enrolled in last 90 days, skipping")
                    continue

                # Get primary contact
                contact = company.contacts.filter(
                    is_active=True
                ).order_by('-is_primary_contact', '-is_decision_maker').first()

                if not contact:
                    logger.warning(f"No active contact for company {company.name}")
                    continue

                try:
                    enrollment = SequenceEnrollment.objects.create(
                        sequence=sequence,
                        contact=contact,
                        company=company,
                        status='active',
                        enrollment_source='auto_trigger',
                        trigger_entity_type='company',
                        trigger_entity_id=str(company.id),
                        current_step_number=1
                    )
                    enrolled_count += 1
                    logger.info(f"Auto-enrolled {contact.email} in {sequence.name} for quarterly check-in (company: {company.name})")

                    # Schedule first step execution
                    self._schedule_next_step(enrollment)

                except Exception as e:
                    logger.error(f"Failed to enroll contact {contact.email} in {sequence.name}: {str(e)}")

        return enrolled_count

    def _schedule_next_step(self, enrollment):
        """
        Schedule the next step execution for an enrollment.

        This creates a SequenceStepExecution record with the appropriate
        scheduled_for timestamp based on the step's delay_days.

        Args:
            enrollment: SequenceEnrollment instance
        """
        from crm_app.models import SequenceStepExecution

        try:
            # Get the next step to execute
            next_step = enrollment.sequence.steps.filter(
                step_number=enrollment.current_step_number,
                is_active=True
            ).first()

            if not next_step:
                logger.warning(f"No active step {enrollment.current_step_number} found for enrollment {enrollment.id}")
                return

            # Calculate when to send this step
            if enrollment.current_step_number == 1:
                # First step - schedule based on enrollment time + delay
                scheduled_for = enrollment.enrolled_at + timedelta(days=next_step.delay_days)
            else:
                # Subsequent steps - schedule based on previous step + delay
                previous_execution = SequenceStepExecution.objects.filter(
                    enrollment=enrollment,
                    step__step_number=enrollment.current_step_number - 1
                ).order_by('-sent_at').first()

                if previous_execution and previous_execution.sent_at:
                    scheduled_for = previous_execution.sent_at + timedelta(days=next_step.delay_days)
                else:
                    # Fallback: use enrolled_at + cumulative delays
                    total_delay = sum([
                        s.delay_days for s in enrollment.sequence.steps.filter(
                            step_number__lte=enrollment.current_step_number
                        )
                    ])
                    scheduled_for = enrollment.enrolled_at + timedelta(days=total_delay)

            # Create the step execution record
            SequenceStepExecution.objects.create(
                enrollment=enrollment,
                step=next_step,
                scheduled_for=scheduled_for,
                status='scheduled'
            )

            logger.debug(f"Scheduled step {next_step.step_number} for enrollment {enrollment.id} at {scheduled_for}")

        except Exception as e:
            logger.error(f"Failed to schedule next step for enrollment {enrollment.id}: {str(e)}")

    def manual_enroll(self, sequence_id, contact_ids, company_id=None):
        """
        Manually enroll contacts in a sequence.

        This is used when users manually add contacts to a sequence
        through the admin interface or API.

        Args:
            sequence_id: UUID of the EmailSequence
            contact_ids: List of Contact UUIDs to enroll
            company_id: Optional UUID of the Company (if enrolling company contacts)

        Returns:
            dict: Summary with enrolled count and any errors
        """
        from crm_app.models import EmailSequence, Contact, Company, SequenceEnrollment

        try:
            sequence = EmailSequence.objects.get(id=sequence_id)
        except EmailSequence.DoesNotExist:
            return {'success': False, 'error': 'Sequence not found'}

        if sequence.status != 'active':
            return {'success': False, 'error': 'Sequence is not active'}

        company = None
        if company_id:
            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                pass

        enrolled = []
        errors = []

        for contact_id in contact_ids:
            try:
                contact = Contact.objects.get(id=contact_id, is_active=True)

                # Check if already enrolled
                existing = SequenceEnrollment.objects.filter(
                    sequence=sequence,
                    contact=contact
                ).exists()

                if existing:
                    errors.append(f"{contact.email} is already enrolled")
                    continue

                # Create enrollment
                enrollment = SequenceEnrollment.objects.create(
                    sequence=sequence,
                    contact=contact,
                    company=company or contact.company,
                    status='active',
                    enrollment_source='manual',
                    current_step_number=1
                )

                # Schedule first step
                self._schedule_next_step(enrollment)

                enrolled.append(contact.email)
                logger.info(f"Manually enrolled {contact.email} in {sequence.name}")

            except Contact.DoesNotExist:
                errors.append(f"Contact {contact_id} not found")
            except Exception as e:
                errors.append(f"Error enrolling {contact_id}: {str(e)}")

        return {
            'success': True,
            'enrolled': enrolled,
            'enrolled_count': len(enrolled),
            'errors': errors
        }


# Singleton instance for easy import
auto_enrollment_service = AutoEnrollmentService()
