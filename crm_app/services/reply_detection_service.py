"""
Reply Detection Service for BMAsia CRM
Polls IMAP inbox for prospect replies, classifies them, and triggers auto-actions.
Uses Python stdlib imaplib + email — no additional packages needed.
"""

import email
import imaplib
import logging
import re
from datetime import timedelta
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class ReplyDetectionService:
    """Detects replies to prospect sequence emails via IMAP polling"""

    # Rule-based classification patterns (checked before AI)
    OOO_PATTERNS = [
        r'out of office', r'automatic reply', r'auto-?reply', r'i am away',
        r'on vacation', r'on leave', r'currently unavailable', r'away from',
        r'will be back', r'return on', r'absence', r'autoreply',
    ]
    UNSUBSCRIBE_PATTERNS = [
        r'unsubscribe', r'remove me', r'stop emailing', r'opt out',
        r'do not contact', r'take me off', r'stop sending',
    ]
    MEETING_PATTERNS = [
        r"let'?s meet", r'schedule a call', r'book a time', r'calendar',
        r'set up a meeting', r'available for a call', r'happy to chat',
        r'let me know.{0,20}time', r'when are you free',
    ]
    BOUNCE_PATTERNS = [
        r'delivery failed', r'undeliverable', r'mailbox full',
        r'address rejected', r'user unknown', r'does not exist',
        r'mail delivery subsystem', r'mailer-daemon',
    ]

    def __init__(self):
        self.imap_host = getattr(settings, 'PROSPECT_IMAP_HOST', 'imap.gmail.com')
        self.reply_email = getattr(settings, 'PROSPECT_REPLY_EMAIL', '')
        self.imap_password = getattr(settings, 'PROSPECT_REPLY_IMAP_PASSWORD', '')

    @property
    def is_configured(self):
        return bool(self.reply_email and self.imap_password)

    def check_for_replies(self, dry_run=False, lookback_hours=24):
        """
        Main entry point — poll IMAP for replies to prospect sequence emails.

        Returns:
            dict with counts: {detected, matched, classified, actions_taken}
        """
        if not self.is_configured:
            logger.error("Reply detection not configured — missing PROSPECT_REPLY_EMAIL or PROSPECT_REPLY_IMAP_PASSWORD")
            return {'detected': 0, 'matched': 0, 'classified': 0, 'actions_taken': 0}

        stats = {'detected': 0, 'matched': 0, 'classified': 0, 'actions_taken': 0}

        try:
            conn = imaplib.IMAP4_SSL(self.imap_host, 993)
            conn.login(self.reply_email, self.imap_password)
            conn.select('INBOX')

            # Search for recent emails (last N hours)
            since_date = (timezone.now() - timedelta(hours=lookback_hours)).strftime('%d-%b-%Y')
            _, message_ids = conn.search(None, f'(SINCE {since_date})')

            if not message_ids[0]:
                logger.info("No recent emails found in IMAP inbox")
                conn.logout()
                return stats

            email_ids = message_ids[0].split()
            logger.info(f"Found {len(email_ids)} emails in last {lookback_hours}h")

            for email_id in email_ids:
                try:
                    self._process_email(conn, email_id, stats, dry_run)
                except Exception as e:
                    logger.error(f"Error processing IMAP email {email_id}: {e}")

            conn.logout()

        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP connection error: {e}")
        except Exception as e:
            logger.error(f"Reply detection failed: {e}")

        return stats

    def _process_email(self, conn, email_id, stats, dry_run):
        """Process a single email from IMAP"""
        from crm_app.models import ProspectReply

        _, msg_data = conn.fetch(email_id, '(RFC822)')
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        # Extract headers
        message_id = msg.get('Message-ID', '').strip()
        in_reply_to = msg.get('In-Reply-To', '').strip()
        references = msg.get('References', '').strip()
        from_header = msg.get('From', '')
        subject = self._decode_header(msg.get('Subject', ''))
        date_header = msg.get('Date', '')

        _, from_email = parseaddr(from_header)
        if not from_email:
            return

        # Skip our own emails
        if from_email.lower() == self.reply_email.lower():
            return

        # Dedup — skip if already processed
        if not message_id:
            return
        if ProspectReply.objects.filter(imap_message_id=message_id).exists():
            return

        stats['detected'] += 1

        # Extract body text
        body_text = self._extract_body(msg)

        # Parse received date
        try:
            received_at = parsedate_to_datetime(date_header)
            if timezone.is_naive(received_at):
                received_at = timezone.make_aware(received_at)
        except Exception:
            received_at = timezone.now()

        # Match to outbound email
        outbound_log, enrollment = self._match_to_outbound(
            in_reply_to, references, from_email, subject
        )

        if not enrollment:
            logger.debug(f"No matching enrollment for reply from {from_email}: {subject}")
            return

        stats['matched'] += 1
        logger.info(f"Matched reply from {from_email} to enrollment {enrollment.id}")

        # Classify
        classification, confidence, method = self._classify_reply(subject, body_text)
        stats['classified'] += 1

        if dry_run:
            logger.info(
                f"[DRY RUN] Would create reply: from={from_email}, "
                f"classification={classification} ({confidence:.0%}), "
                f"enrollment={enrollment.id}"
            )
            return

        # Create ProspectReply record
        reply = ProspectReply.objects.create(
            enrollment=enrollment,
            email_log=outbound_log,
            imap_message_id=message_id,
            from_email=from_email,
            subject=subject[:500],
            body_text=body_text[:5000],
            received_at=received_at,
            classification=classification,
            classification_confidence=confidence,
            classification_method=method,
            needs_human_review=(confidence < 0.80),
        )

        # Execute auto-actions
        actions = self._execute_auto_actions(reply, enrollment)
        if actions:
            stats['actions_taken'] += 1

    def _match_to_outbound(self, in_reply_to, references, from_email, subject):
        """
        Match an inbound reply to an outbound EmailLog using 3-tier strategy.

        Returns:
            (EmailLog or None, ProspectEnrollment or None)
        """
        from crm_app.models import EmailLog, ProspectEnrollment

        # Tier 1: In-Reply-To header → direct match
        if in_reply_to:
            log = EmailLog.objects.filter(
                message_id=in_reply_to,
                email_type='sequence',
            ).select_related('contact').first()
            if log:
                enrollment = self._get_enrollment_from_log(log)
                if enrollment:
                    return log, enrollment

        # Tier 2: References header chain
        if references:
            ref_ids = references.split()
            for ref_id in ref_ids:
                ref_id = ref_id.strip()
                if not ref_id:
                    continue
                log = EmailLog.objects.filter(
                    message_id=ref_id,
                    email_type='sequence',
                ).select_related('contact').first()
                if log:
                    enrollment = self._get_enrollment_from_log(log)
                    if enrollment:
                        return log, enrollment

        # Tier 3: Subject-line fallback — strip Re:/Fwd: and match recent emails
        clean_subject = re.sub(r'^(Re|Fwd|FW):\s*', '', subject, flags=re.IGNORECASE).strip()
        if clean_subject and from_email:
            # Look for recent sequence emails to this contact
            recent_log = EmailLog.objects.filter(
                email_type='sequence',
                status='sent',
                to_email__iexact=from_email,
                subject__icontains=clean_subject[:100],
                created_at__gte=timezone.now() - timedelta(days=30),
            ).order_by('-created_at').first()
            if recent_log:
                enrollment = self._get_enrollment_from_log(recent_log)
                if enrollment:
                    return recent_log, enrollment

        return None, None

    def _get_enrollment_from_log(self, email_log):
        """Get the ProspectEnrollment linked to an EmailLog via ProspectStepExecution"""
        execution = email_log.prospect_executions.select_related('enrollment').first()
        if execution:
            return execution.enrollment

        # Fallback: find enrollment by contact + company
        from crm_app.models import ProspectEnrollment
        if email_log.contact:
            return ProspectEnrollment.objects.filter(
                contact=email_log.contact,
                status__in=['active', 'paused'],
            ).order_by('-enrolled_at').first()
        return None

    def _classify_reply(self, subject, body_text):
        """
        Classify a reply using rule-based patterns first, then AI fallback.

        Returns:
            (classification, confidence, method)
        """
        text = f"{subject}\n{body_text}".lower()

        # Rule-based classification (fast, high confidence)
        if self._matches_patterns(text, self.BOUNCE_PATTERNS):
            return 'bounce', 0.95, 'rule'

        if self._matches_patterns(text, self.OOO_PATTERNS):
            return 'out_of_office', 0.95, 'rule'

        if self._matches_patterns(text, self.UNSUBSCRIBE_PATTERNS):
            return 'unsubscribe', 0.95, 'rule'

        if self._matches_patterns(text, self.MEETING_PATTERNS):
            return 'meeting_request', 0.90, 'rule'

        # AI classification for ambiguous replies
        return self._classify_with_ai(subject, body_text)

    def _matches_patterns(self, text, patterns):
        """Check if text matches any of the given regex patterns"""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _classify_with_ai(self, subject, body_text):
        """Use Claude Haiku to classify ambiguous replies"""
        try:
            from crm_app.services.ai_service import MODEL_SIMPLE, HAS_ANTHROPIC
            if not HAS_ANTHROPIC:
                return 'unclassified', 0.0, 'none'

            import anthropic
            api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
            if not api_key:
                return 'unclassified', 0.0, 'none'

            client = anthropic.Anthropic(api_key=api_key)
            prompt = f"""Classify this email reply from a sales prospect. Return ONLY a JSON object with "classification" and "confidence" (0.0-1.0).

Classifications:
- "interested": Shows interest in the product/service, wants to learn more
- "not_interested": Declines, not interested, bad timing
- "question": Asks a question about pricing, features, etc.
- "objection": Raises concerns or objections
- "meeting_request": Wants to schedule a call or meeting
- "referral": Redirects to another person
- "other": Doesn't fit any category

Email Subject: {subject}
Email Body:
{body_text[:1500]}

Respond with ONLY valid JSON, no other text. Example: {{"classification": "interested", "confidence": 0.85}}"""

            response = client.messages.create(
                model=MODEL_SIMPLE,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
            )

            result_text = response.content[0].text.strip()
            # Parse JSON response
            import json
            result = json.loads(result_text)
            classification = result.get('classification', 'unclassified')
            confidence = float(result.get('confidence', 0.5))

            # Validate classification
            valid = [
                'interested', 'not_interested', 'question', 'objection',
                'meeting_request', 'referral', 'other',
            ]
            if classification not in valid:
                classification = 'other'

            return classification, confidence, 'ai'

        except Exception as e:
            logger.error(f"AI classification failed: {e}")
            return 'unclassified', 0.0, 'none'

    def _execute_auto_actions(self, reply, enrollment):
        """Execute automatic actions based on reply classification"""
        from crm_app.models import Task, ProspectEnrollment

        actions_taken = False
        classification = reply.classification
        contact = enrollment.contact
        opportunity = enrollment.opportunity
        company = opportunity.company

        # Cross-company stop — pause ALL active enrollments for this company
        company_enrollments = ProspectEnrollment.objects.filter(
            opportunity__company=company,
            status='active',
        ).exclude(id=enrollment.id)

        if classification in ('interested', 'meeting_request'):
            # Pause enrollment as replied
            self._pause_enrollment(enrollment, 'reply_received', 'replied')
            self._pause_related_enrollments(company_enrollments)
            reply.enrollment_paused = True

            # Advance stage if still early
            if opportunity.stage == 'Contacted':
                opportunity.stage = 'Quotation Sent'
                opportunity.save(update_fields=['stage', 'stage_changed_at'])
                reply.stage_updated = True

            # Create follow-up task
            task = Task.objects.create(
                title=f"Follow up: {contact.first_name} {contact.last_name} replied — {classification.replace('_', ' ')}",
                description=f"Prospect replied to sequence email.\n\nSubject: {reply.subject}\n\nReply excerpt:\n{reply.body_text[:500]}",
                task_type='Follow-up',
                status='To Do',
                company=company,
                contact=contact,
                opportunity=opportunity,
                due_date=timezone.now().date() + timedelta(days=1),
            )
            reply.task_created = task
            actions_taken = True

        elif classification == 'not_interested':
            self._pause_enrollment(enrollment, 'reply_received', 'replied')
            self._pause_related_enrollments(company_enrollments)
            reply.enrollment_paused = True

            task = Task.objects.create(
                title=f"Review: {contact.first_name} {contact.last_name} — not interested",
                description=f"Prospect declined.\n\nSubject: {reply.subject}\n\nReply:\n{reply.body_text[:500]}",
                task_type='Follow-up',
                status='To Do',
                company=company,
                contact=contact,
                opportunity=opportunity,
                due_date=timezone.now().date() + timedelta(days=1),
            )
            reply.task_created = task
            actions_taken = True

        elif classification == 'out_of_office':
            self._pause_enrollment(enrollment, 'out_of_office', 'paused')
            reply.enrollment_paused = True

            task = Task.objects.create(
                title=f"Resume sequence: {contact.first_name} {contact.last_name} is OOO",
                description=f"Contact is out of office. Resume sequence when they return.\n\n{reply.body_text[:500]}",
                task_type='Follow-up',
                status='To Do',
                company=company,
                contact=contact,
                opportunity=opportunity,
                due_date=timezone.now().date() + timedelta(days=7),
            )
            reply.task_created = task
            actions_taken = True

        elif classification == 'unsubscribe':
            enrollment.status = 'cancelled'
            enrollment.cancelled_at = timezone.now()
            enrollment.save(update_fields=['status', 'cancelled_at'])
            self._pause_related_enrollments(company_enrollments)
            reply.enrollment_paused = True

            # Disable notifications for this contact
            contact.receives_notifications = False
            contact.save(update_fields=['receives_notifications'])
            actions_taken = True

        elif classification in ('question', 'objection'):
            self._pause_enrollment(enrollment, 'reply_received', 'replied')
            self._pause_related_enrollments(company_enrollments)
            reply.enrollment_paused = True

            task = Task.objects.create(
                title=f"Reply needed: {contact.first_name} {contact.last_name} — {classification}",
                description=f"Prospect has a {classification}. Please respond.\n\nSubject: {reply.subject}\n\nReply:\n{reply.body_text[:500]}",
                task_type='Follow-up',
                status='To Do',
                company=company,
                contact=contact,
                opportunity=opportunity,
                due_date=timezone.now().date(),
            )
            reply.task_created = task
            actions_taken = True

        elif classification == 'referral':
            self._pause_enrollment(enrollment, 'reply_received', 'replied')
            self._pause_related_enrollments(company_enrollments)
            reply.enrollment_paused = True

            task = Task.objects.create(
                title=f"Referral: {contact.first_name} {contact.last_name} redirected",
                description=f"Prospect referred to someone else. Review and re-target.\n\nReply:\n{reply.body_text[:500]}",
                task_type='Follow-up',
                status='To Do',
                company=company,
                contact=contact,
                opportunity=opportunity,
                due_date=timezone.now().date() + timedelta(days=1),
            )
            reply.task_created = task
            actions_taken = True

        elif classification == 'bounce':
            enrollment.status = 'cancelled'
            enrollment.cancelled_at = timezone.now()
            enrollment.save(update_fields=['status', 'cancelled_at'])
            reply.enrollment_paused = True
            logger.warning(f"Bounce detected for {contact.email} — enrollment cancelled")
            actions_taken = True

        else:
            # unclassified / other
            self._pause_enrollment(enrollment, 'reply_received', 'replied')
            self._pause_related_enrollments(company_enrollments)
            reply.enrollment_paused = True
            reply.needs_human_review = True

            task = Task.objects.create(
                title=f"Review reply from {contact.first_name} {contact.last_name}",
                description=f"Unclassified reply needs review.\n\nSubject: {reply.subject}\n\nReply:\n{reply.body_text[:500]}",
                task_type='Follow-up',
                status='To Do',
                company=company,
                contact=contact,
                opportunity=opportunity,
                due_date=timezone.now().date(),
            )
            reply.task_created = task
            actions_taken = True

        reply.save()
        return actions_taken

    def _pause_enrollment(self, enrollment, pause_reason, status='replied'):
        """Pause a single enrollment"""
        enrollment.status = status
        enrollment.paused_at = timezone.now()
        enrollment.pause_reason = pause_reason
        enrollment.save(update_fields=['status', 'paused_at', 'pause_reason'])

    def _pause_related_enrollments(self, enrollments_qs):
        """Pause all related active enrollments (cross-company stop)"""
        for enr in enrollments_qs:
            enr.status = 'paused'
            enr.paused_at = timezone.now()
            enr.pause_reason = 'reply_received'
            enr.save(update_fields=['status', 'paused_at', 'pause_reason'])

    def _decode_header(self, header_value):
        """Decode an email header that may be encoded"""
        if not header_value:
            return ''
        decoded_parts = decode_header(header_value)
        parts = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                parts.append(part.decode(charset or 'utf-8', errors='replace'))
            else:
                parts.append(part)
        return ''.join(parts)

    def _extract_body(self, msg):
        """Extract plain text body from email message"""
        body = ''
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == 'text/plain':
                    try:
                        charset = part.get_content_charset() or 'utf-8'
                        body = part.get_payload(decode=True).decode(charset, errors='replace')
                        break
                    except Exception:
                        pass
            # If no plain text, try HTML
            if not body:
                for part in msg.walk():
                    if part.get_content_type() == 'text/html':
                        try:
                            charset = part.get_content_charset() or 'utf-8'
                            html = part.get_payload(decode=True).decode(charset, errors='replace')
                            body = re.sub(r'<[^>]+>', '', html)
                            break
                        except Exception:
                            pass
        else:
            try:
                charset = msg.get_content_charset() or 'utf-8'
                body = msg.get_payload(decode=True).decode(charset, errors='replace')
            except Exception:
                pass
        return body.strip()
