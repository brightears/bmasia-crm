"""
Management command to process prospect sequence enrollments.
Runs via cron job every 20 minutes.

For each active enrollment:
1. Find pending step executions that are due
2. Execute the action (send email, create AI draft, create task, update stage)
3. Schedule the next step or mark sequence as complete
"""

import re
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
import logging

from crm_app.models import (
    ProspectEnrollment,
    ProspectStepExecution,
    ProspectSequenceStep,
    AIEmailDraft,
    Task,
    EmailLog,
)
from crm_app.services.email_service import email_service
from crm_app.services.ai_service import AIEmailService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process prospect sequence enrollments — execute due steps'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without executing',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Process even outside business hours',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        now = timezone.now()

        self.stdout.write(f"Processing prospect sequences at {now}")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no actions will be taken"))

        # Check business hours (9 AM - 5 PM Bangkok = UTC+7)
        bangkok_hour = (now.hour + 7) % 24
        if not force and not (9 <= bangkok_hour < 17):
            self.stdout.write(self.style.WARNING(
                f"Outside business hours (Bangkok: {bangkok_hour}:00). Use --force to override."
            ))
            return

        ai_service = AIEmailService()

        # 1. Expire old AI drafts (24h TTL)
        expired_count = self._expire_old_drafts(now, dry_run)

        # 2. Process due step executions
        due_executions = ProspectStepExecution.objects.filter(
            status='pending',
            scheduled_for__lte=now,
            enrollment__status='active',
        ).select_related(
            'enrollment', 'enrollment__sequence', 'enrollment__opportunity',
            'enrollment__opportunity__company', 'enrollment__contact', 'step',
        ).order_by('scheduled_for')

        processed = 0
        errors = 0

        for execution in due_executions:
            try:
                if dry_run:
                    self.stdout.write(
                        f"  Would process: {execution.step} for "
                        f"{execution.enrollment.contact} "
                        f"(opp: {execution.enrollment.opportunity})"
                    )
                    processed += 1
                    continue

                self._process_execution(execution, ai_service, now)
                processed += 1

            except Exception as e:
                errors += 1
                logger.error(f"Error processing execution {execution.id}: {e}")
                execution.status = 'failed'
                execution.error_message = str(e)[:1000]
                execution.executed_at = now
                execution.save(update_fields=['status', 'error_message', 'executed_at'])

        self.stdout.write(self.style.SUCCESS(
            f"Done: {processed} processed, {errors} errors, {expired_count} drafts expired"
        ))

    def _expire_old_drafts(self, now, dry_run):
        """Expire AI drafts past their TTL"""
        expired_drafts = AIEmailDraft.objects.filter(
            status='pending_review',
            expires_at__lt=now,
        ).select_related('execution')

        count = expired_drafts.count()
        if count and not dry_run:
            for draft in expired_drafts:
                draft.status = 'expired'
                draft.save(update_fields=['status'])
                # Also mark the execution as expired
                draft.execution.status = 'expired'
                draft.execution.executed_at = now
                draft.execution.save(update_fields=['status', 'executed_at'])
                # Schedule next step so sequence continues
                self._schedule_next_step(draft.execution)

            logger.info(f"Expired {count} AI drafts past TTL")

        return count

    def _process_execution(self, execution, ai_service, now):
        """Process a single step execution"""
        step = execution.step
        enrollment = execution.enrollment
        contact = enrollment.contact
        opportunity = enrollment.opportunity

        action_type = step.action_type

        if action_type == 'email':
            self._send_template_email(execution, contact, opportunity, step, now)
        elif action_type == 'ai_email':
            self._create_ai_draft(execution, contact, opportunity, step, ai_service, now)
        elif action_type == 'task':
            self._create_task(execution, contact, opportunity, step, now)
        elif action_type == 'stage_update':
            self._update_stage(execution, opportunity, step, now)

    def _send_template_email(self, execution, contact, opportunity, step, now):
        """Send a template-based email (non-AI)"""
        company = opportunity.company

        # Render templates with context
        ctx = self._build_template_context(contact, opportunity, company)
        subject = self._render_template(step.email_subject_template, ctx)
        body_html = self._render_template(step.email_body_template, ctx)
        body_text = re.sub(r'<[^>]+>', '', body_html)

        if not contact.email:
            execution.status = 'failed'
            execution.error_message = 'Contact has no email address'
            execution.executed_at = now
            execution.save(update_fields=['status', 'error_message', 'executed_at'])
            return

        success, message = email_service.send_email(
            to_email=contact.email,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            company=company,
            contact=contact,
            email_type='sequence',
        )

        execution.executed_at = now
        if success:
            execution.status = 'sent'
            # Update enrollment current_step
            enrollment = execution.enrollment
            enrollment.current_step = step.step_number
            enrollment.save(update_fields=['current_step'])
            self._schedule_next_step(execution)
        else:
            execution.status = 'failed'
            execution.error_message = message
        execution.save(update_fields=['status', 'executed_at', 'error_message'])

    def _create_ai_draft(self, execution, contact, opportunity, step, ai_service, now):
        """Generate AI email and create a draft for approval"""
        if not ai_service.is_available:
            # Fall back to template if AI is unavailable
            logger.warning("AI service unavailable, falling back to template email")
            if step.email_subject_template and step.email_body_template:
                self._send_template_email(execution, contact, opportunity, step, now)
            else:
                execution.status = 'failed'
                execution.error_message = 'AI service unavailable and no template fallback'
                execution.executed_at = now
                execution.save(update_fields=['status', 'error_message', 'executed_at'])
            return

        # Build email history context
        email_history = []
        recent_logs = EmailLog.objects.filter(
            contact=contact,
            status='sent',
        ).order_by('-created_at')[:5]
        for log in recent_logs:
            email_history.append({
                'subject': log.subject,
                'sent_date': log.created_at.strftime('%Y-%m-%d'),
            })

        result = ai_service.generate_prospect_email(
            opportunity=opportunity,
            contact=contact,
            step=step,
            context={'email_history': email_history},
        )

        if not result:
            execution.status = 'failed'
            execution.error_message = 'AI generation returned None'
            execution.executed_at = now
            execution.save(update_fields=['status', 'error_message', 'executed_at'])
            return

        # Store AI draft on execution
        execution.ai_draft_subject = result['subject']
        execution.ai_draft_body = result['body_html']
        execution.status = 'pending_approval'
        execution.save(update_fields=['ai_draft_subject', 'ai_draft_body', 'status'])

        # Create AIEmailDraft for the approval queue
        AIEmailDraft.objects.create(
            execution=execution,
            subject=result['subject'],
            body_html=result['body_html'],
            expires_at=now + timedelta(hours=24),
        )

        logger.info(f"AI draft created for {contact.email} — pending approval")

    def _create_task(self, execution, contact, opportunity, step, now):
        """Create a CRM task"""
        company = opportunity.company
        ctx = self._build_template_context(contact, opportunity, company)
        title = self._render_template(step.task_title_template, ctx) or f"Follow up with {contact.name}"

        task = Task.objects.create(
            title=title,
            description=f"Auto-created by sequence: {step.sequence.name} (Step {step.step_number})",
            task_type=step.task_type or 'Follow-up',
            priority='Medium',
            status='To Do',
            related_company=company,
            related_contact=contact,
            related_opportunity=opportunity,
            assigned_to=opportunity.owner,
            due_date=timezone.now().date() + timedelta(days=1),
        )

        execution.task_created = task
        execution.status = 'sent'
        execution.executed_at = now
        execution.save(update_fields=['task_created', 'status', 'executed_at'])

        enrollment = execution.enrollment
        enrollment.current_step = step.step_number
        enrollment.save(update_fields=['current_step'])

        self._schedule_next_step(execution)
        logger.info(f"Task created: {title}")

    def _update_stage(self, execution, opportunity, step, now):
        """Update opportunity stage"""
        if step.stage_to_set:
            opportunity.stage = step.stage_to_set
            opportunity.save()
            logger.info(f"Opportunity {opportunity.id} stage updated to {step.stage_to_set}")

        execution.status = 'sent'
        execution.executed_at = now
        execution.save(update_fields=['status', 'executed_at'])

        enrollment = execution.enrollment
        enrollment.current_step = step.step_number
        enrollment.save(update_fields=['current_step'])

        self._schedule_next_step(execution)

    def _schedule_next_step(self, execution):
        """Schedule the next step in the sequence, or mark enrollment as complete"""
        enrollment = execution.enrollment
        current_step = execution.step

        # Find next step
        next_step = ProspectSequenceStep.objects.filter(
            sequence=enrollment.sequence,
            step_number__gt=current_step.step_number,
        ).order_by('step_number').first()

        if next_step:
            scheduled_for = timezone.now() + timedelta(days=next_step.delay_days)
            ProspectStepExecution.objects.create(
                enrollment=enrollment,
                step=next_step,
                scheduled_for=scheduled_for,
            )
            logger.info(f"Next step {next_step.step_number} scheduled for {scheduled_for}")
        else:
            # Sequence complete
            enrollment.status = 'completed'
            enrollment.completed_at = timezone.now()
            enrollment.save(update_fields=['status', 'completed_at'])
            logger.info(f"Enrollment {enrollment.id} completed")

    def _build_template_context(self, contact, opportunity, company):
        """Build variable context for template rendering"""
        return {
            'contact_name': contact.name if contact else '',
            'contact_first_name': contact.first_name if contact else '',
            'contact_title': contact.title or '',
            'company_name': company.name if company else '',
            'opportunity_stage': opportunity.stage if opportunity else '',
            'opportunity_value': str(opportunity.expected_value or '') if opportunity else '',
        }

    def _render_template(self, template_str, context):
        """Simple {{variable}} template rendering"""
        if not template_str:
            return template_str
        result = template_str
        for key, value in context.items():
            result = result.replace('{{' + key + '}}', str(value))
        return result
