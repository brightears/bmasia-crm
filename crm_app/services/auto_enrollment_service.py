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

# Country mapping for seasonal campaigns
# Note: Use exact country names as stored in Company.country field
SEASONAL_COUNTRY_MAP = {
    'auto_seasonal_christmas': ['ALL'],
    'auto_seasonal_valentines': ['ALL'],
    # CNY: ALL Asian countries (major CNY celebrations across Asia)
    'auto_seasonal_cny': [
        'Thailand', 'Singapore', 'Malaysia', 'Hong Kong', 'China', 'Taiwan', 'Vietnam',
        'Japan', 'South Korea', 'Philippines', 'Indonesia', 'Myanmar', 'Cambodia',
        'Laos', 'Brunei', 'Macau', 'Mongolia', 'North Korea'
    ],
    'auto_seasonal_songkran': ['Thailand'],
    'auto_seasonal_loy_krathong': ['Thailand'],  # Thailand only
    # Ramadan: Middle Eastern countries + Muslim-majority SE Asian countries
    'auto_seasonal_ramadan': [
        'UAE', 'Saudi Arabia', 'Qatar', 'Kuwait', 'Bahrain', 'Oman',
        'Malaysia', 'Indonesia', 'Brunei',  # SE Asian Muslim-majority
        'Jordan', 'Lebanon', 'Egypt', 'Iraq', 'Iran', 'Turkey', 'Pakistan', 'Bangladesh'
    ],
    'auto_seasonal_singapore_nd': ['Singapore'],
    # Diwali: Hindu-majority and significant Hindu populations
    'auto_seasonal_diwali': [
        'India', 'Nepal', 'Singapore', 'Malaysia', 'Sri Lanka', 'Mauritius', 'Fiji'
    ],
    # Mid-Autumn Festival: Chinese/Vietnamese communities
    'auto_seasonal_mid_autumn': [
        'China', 'Vietnam', 'Taiwan', 'Hong Kong', 'Macau', 'Singapore', 'Malaysia'
    ],
    # Eid al-Fitr: End of Ramadan celebration (Indonesia's biggest holiday)
    'auto_seasonal_eid_fitr': [
        'Indonesia', 'Malaysia', 'Brunei', 'Singapore',
        'UAE', 'Saudi Arabia', 'Qatar', 'Kuwait', 'Bahrain', 'Oman',
        'Jordan', 'Lebanon', 'Egypt', 'Iraq', 'Iran', 'Turkey', 'Pakistan', 'Bangladesh'
    ],
}

# Fixed trigger dates (month, day) - sent 2 weeks before holiday
SEASONAL_TRIGGER_DATES = {
    'auto_seasonal_christmas': (10, 15),    # Oct 15 (2 months before Dec 25)
    'auto_seasonal_valentines': (1, 31),    # Jan 31 (2 weeks before Feb 14)
    'auto_seasonal_songkran': (3, 29),      # Mar 29 (2 weeks before Apr 13)
    'auto_seasonal_singapore_nd': (7, 26),  # Jul 26 (2 weeks before Aug 9)
    # Variable dates - loaded from SeasonalTriggerDate model (Settings page)
    'auto_seasonal_cny': 'variable',
    'auto_seasonal_loy_krathong': 'variable',
    'auto_seasonal_ramadan': 'variable',
    'auto_seasonal_diwali': 'variable',
    'auto_seasonal_mid_autumn': 'variable',
    'auto_seasonal_eid_fitr': 'variable',
}


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
            'seasonal': self.process_seasonal_triggers(),
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
            # Only include contracts that have renewal reminders enabled
            contracts = Contract.objects.filter(
                end_date=target_date,
                status='Active',
                send_renewal_reminders=True
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
                # Exclude contacts who have opted out of emails or renewal emails specifically
                contact = contract.company.contacts.filter(
                    is_active=True,
                    receives_notifications=True,
                    receives_renewal_emails=True,
                    unsubscribed=False
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
                # Exclude contacts who have opted out of emails or payment emails specifically
                company = invoice.contract.company
                contact = company.contacts.filter(
                    is_active=True,
                    receives_notifications=True,
                    receives_payment_emails=True,
                    unsubscribed=False
                ).filter(
                    Q(is_billing_contact=True) | Q(is_primary_contact=True)
                ).first()

                if not contact:
                    # Fallback to any active contact who hasn't opted out of payment emails
                    contact = company.contacts.filter(
                        is_active=True,
                        receives_notifications=True,
                        receives_payment_emails=True,
                        unsubscribed=False
                    ).first()

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
        Auto-enroll contacts for quarterly check-ins based on contract start date.

        Enrolls contacts on the 90/180/270/360 day anniversaries of their
        contract start date (and every subsequent 90-day milestone).

        Returns:
            int: Number of enrollments created
        """
        from crm_app.models import EmailSequence, SequenceEnrollment, Contract

        today = date.today()
        enrolled_count = 0

        # Get all active contracts
        contracts = Contract.objects.filter(
            status='Active'
        ).select_related('company')

        logger.info(f"Processing {contracts.count()} active contracts for quarterly triggers")

        for contract in contracts:
            if not contract.start_date:
                logger.debug(f"Contract {contract.contract_number} has no start_date, skipping")
                continue

            days_since_start = (today - contract.start_date).days

            # Check if today is a quarterly milestone (90, 180, 270, 360, etc.)
            # Only process if > 0 days (not on start date itself)
            if days_since_start > 0 and days_since_start % 90 == 0:
                quarter_number = days_since_start // 90

                logger.info(f"Contract {contract.contract_number} reached Q{quarter_number} milestone ({days_since_start} days since start)")

                # Get active quarterly sequence
                sequence = EmailSequence.objects.filter(
                    sequence_type='auto_quarterly',
                    status='active'
                ).first()

                if not sequence:
                    logger.debug("No active auto_quarterly sequence found")
                    continue

                # Check if already enrolled for this specific quarter
                # Use trigger_entity_id to track which quarters have been processed
                already_enrolled = SequenceEnrollment.objects.filter(
                    sequence=sequence,
                    trigger_entity_type='contract_quarter',
                    trigger_entity_id=f"{contract.id}_Q{quarter_number}"
                ).exists()

                if already_enrolled:
                    logger.debug(f"Contract {contract.contract_number} Q{quarter_number} already enrolled, skipping")
                    continue

                # Get primary contact (respecting opt-out and quarterly email preference)
                contact = contract.company.contacts.filter(
                    is_active=True,
                    receives_notifications=True,
                    receives_quarterly_emails=True,
                    unsubscribed=False
                ).order_by('-is_primary_contact', '-is_decision_maker').first()

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
                        trigger_entity_type='contract_quarter',
                        trigger_entity_id=f"{contract.id}_Q{quarter_number}",
                        current_step_number=1
                    )

                    # Schedule first step
                    self._schedule_next_step(enrollment)
                    enrolled_count += 1

                    logger.info(f"Auto-enrolled {contact.email} in {sequence.name} for Q{quarter_number} check-in (contract: {contract.contract_number})")

                except Exception as e:
                    logger.error(f"Failed to enroll contact {contact.email} in {sequence.name}: {str(e)}")

        return enrolled_count

    def process_seasonal_triggers(self):
        """
        Auto-enroll contacts for seasonal campaigns based on:
        - Company country
        - Active contract status
        - seasonal_emails_enabled flag (if False, skip)
        """
        from crm_app.models import EmailSequence, SequenceEnrollment, Company

        today = date.today()
        enrolled_count = 0

        for sequence_type, countries in SEASONAL_COUNTRY_MAP.items():
            trigger_config = SEASONAL_TRIGGER_DATES.get(sequence_type)

            # Handle variable dates (CNY, Ramadan, Loy Krathong)
            if trigger_config == 'variable':
                # Try to load from SeasonalTriggerDate model
                try:
                    from crm_app.models import SeasonalTriggerDate
                    trigger_date_obj = SeasonalTriggerDate.objects.filter(
                        holiday_type=sequence_type,
                        year=today.year
                    ).first()
                    if not trigger_date_obj:
                        logger.debug(f"No trigger date set for {sequence_type} in {today.year}")
                        continue
                    if today != trigger_date_obj.trigger_date:
                        continue
                except Exception as e:
                    logger.debug(f"SeasonalTriggerDate not available: {e}")
                    continue
            else:
                # Fixed date - check if today matches (month, day)
                trigger_month, trigger_day = trigger_config
                if today.month != trigger_month or today.day != trigger_day:
                    continue

            logger.info(f"Processing seasonal trigger: {sequence_type}")

            # Get active sequence for this type
            sequence = EmailSequence.objects.filter(
                sequence_type=sequence_type,
                status='active'
            ).first()

            if not sequence:
                logger.debug(f"No active sequence for {sequence_type}")
                continue

            # Build company filter
            company_filter = Q(
                contracts__status='Active',
                is_active=True
            )

            # Check seasonal opt-out if field exists
            if hasattr(Company, 'seasonal_emails_enabled'):
                company_filter &= Q(seasonal_emails_enabled=True)

            # Filter by country (unless 'ALL')
            if 'ALL' not in countries:
                company_filter &= Q(country__in=countries)

            companies = Company.objects.filter(company_filter).distinct()
            logger.info(f"Found {companies.count()} eligible companies for {sequence_type}")

            for company in companies:
                # Get eligible contact (respecting opt-out and seasonal email preference)
                contact = company.contacts.filter(
                    is_active=True,
                    receives_notifications=True,
                    receives_seasonal_emails=True,
                    unsubscribed=False
                ).order_by('-is_primary_contact', '-is_decision_maker').first()

                if not contact:
                    continue

                # Deduplicate: Check not already enrolled this year
                year_key = f"{sequence_type}_{today.year}"
                already_enrolled = SequenceEnrollment.objects.filter(
                    sequence=sequence,
                    company=company,
                    trigger_entity_type='seasonal',
                    trigger_entity_id=year_key
                ).exists()

                if already_enrolled:
                    continue

                try:
                    enrollment = SequenceEnrollment.objects.create(
                        sequence=sequence,
                        contact=contact,
                        company=company,
                        status='active',
                        enrollment_source='auto_trigger',
                        trigger_entity_type='seasonal',
                        trigger_entity_id=year_key,
                        current_step_number=1
                    )
                    self._schedule_next_step(enrollment)
                    enrolled_count += 1
                    logger.info(f"Enrolled {contact.email} for {sequence_type}")
                except Exception as e:
                    logger.error(f"Failed to enroll {contact.email} for {sequence_type}: {e}")

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
                contact = Contact.objects.get(
                    id=contact_id,
                    is_active=True,
                    receives_notifications=True,
                    unsubscribed=False
                )

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
                errors.append(f"Contact {contact_id} not found or has opted out of emails")
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
