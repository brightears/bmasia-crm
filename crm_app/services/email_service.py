"""
Email Service for BMAsia CRM
Handles all email sending functionality including templates, campaigns, and tracking
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import pytz

from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.urls import reverse
from django.db.models import Q

from crm_app.models import (
    EmailTemplate, EmailLog, EmailCampaign,
    Contact, Company, Contract, Invoice, DocumentAttachment,
    EmailSequence, SequenceStep, SequenceEnrollment, SequenceStepExecution
)

logger = logging.getLogger(__name__)


class EmailService:
    """Main email service for sending automated emails"""
    
    def __init__(self):
        self.timezone = pytz.timezone(settings.BUSINESS_TIMEZONE)
        self.business_hours_start = settings.BUSINESS_HOURS_START
        self.business_hours_end = settings.BUSINESS_HOURS_END
    
    def is_business_hours(self, target_timezone: str = None) -> bool:
        """Check if current time is within business hours"""
        tz = pytz.timezone(target_timezone) if target_timezone else self.timezone
        now = datetime.now(tz)
        
        # Skip weekends
        if now.weekday() in [5, 6]:  # Saturday, Sunday
            return False
        
        # Check business hours
        return self.business_hours_start <= now.hour < self.business_hours_end
    
    def get_from_email(self, department: str = None) -> str:
        """Get appropriate from email based on department

        Routing:
        - Sales (Contracts, Quotations) → nikki.h@bmasiamusic.com
        - Finance (Invoices, Payment reminders) → pom@bmasiamusic.com
        - Tech Support → keith@bmasiamusic.com
        - Music Design (Seasonal campaigns) → production@bmasiamusic.com
        - Admin (Quarterly follow-ups, Renewals) → norbert@bmasiamusic.com
        """
        department_emails = {
            'Sales': settings.SALES_EMAIL,
            'Finance': settings.FINANCE_EMAIL,
            'Tech': settings.SUPPORT_EMAIL,
            'Music': settings.MUSIC_DESIGN_EMAIL,
            'Admin': settings.ADMIN_EMAIL,
        }

        return department_emails.get(department, settings.DEFAULT_FROM_EMAIL)

    def _get_sequence_sender(self, sequence_type: str) -> str:
        """Get appropriate sender email based on sequence type.

        Routing:
        - Seasonal campaigns (Christmas, CNY, Diwali, etc.) → production@bmasiamusic.com
        - Renewal reminders → nikki.h@bmasiamusic.com (Sales)
        - Payment reminders → pom@bmasiamusic.com (Finance)
        - Quarterly check-ins → norbert@bmasiamusic.com (Default)
        - Manual sequences → norbert@bmasiamusic.com (Default)
        """
        # Seasonal campaigns - all auto_seasonal_* types
        if sequence_type.startswith('auto_seasonal'):
            return settings.MUSIC_DESIGN_EMAIL  # production@bmasiamusic.com

        # Renewal reminders
        if sequence_type == 'auto_renewal':
            return settings.SALES_EMAIL  # nikki.h@bmasiamusic.com

        # Payment reminders
        if sequence_type == 'auto_payment':
            return settings.FINANCE_EMAIL  # pom@bmasiamusic.com

        # Quarterly check-ins and manual sequences use default
        return settings.DEFAULT_FROM_EMAIL  # norbert@bmasiamusic.com

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: str,
        from_email: str = None,
        cc_emails: List[str] = None,
        company: Company = None,
        contact: Contact = None,
        email_type: str = 'manual',
        template: EmailTemplate = None,
        contract: Contract = None,
        invoice: Invoice = None,
        reply_to: str = None,
        attachments: List[DocumentAttachment] = None,
        smtp_connection = None
    ) -> Tuple[bool, str]:
        """
        Send an email and log it
        Returns: (success: bool, message: str)

        Args:
            smtp_connection: Optional custom SMTP connection (for per-user SMTP)
        """
        if not from_email:
            from_email = settings.DEFAULT_FROM_EMAIL

        # Create email log entry
        email_log = EmailLog.objects.create(
            company=company,
            contact=contact,
            email_type=email_type,
            template_used=template,
            from_email=from_email,
            to_email=to_email,
            cc_emails=','.join(cc_emails) if cc_emails else '',
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            contract=contract,
            invoice=invoice,
            status='pending'
        )

        try:
            # Create email message
            msg = EmailMultiAlternatives(
                subject=subject,
                body=body_text,
                from_email=from_email,
                to=[to_email],
                cc=cc_emails or [],
                reply_to=[reply_to] if reply_to else None,
                connection=smtp_connection
            )
            
            # Add HTML version
            msg.attach_alternative(body_html, "text/html")
            
            # Add tracking headers
            msg.extra_headers['X-BMAsia-Email-ID'] = str(email_log.id)
            msg.extra_headers['List-Unsubscribe'] = self._get_unsubscribe_url(contact)
            
            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    try:
                        msg.attach_file(attachment.file.path)
                        logger.info(f"Attached file: {attachment.name}")
                    except Exception as e:
                        logger.warning(f"Failed to attach file {attachment.name}: {e}")
            
            # Send email
            msg.send(fail_silently=False)
            
            # Mark as sent
            email_log.mark_as_sent()
            
            # Associate attachments with email log
            if attachments:
                email_log.attachments.set(attachments)
            
            logger.info(f"Email sent successfully to {to_email} - Type: {email_type}")
            return True, "Email sent successfully"
            
        except Exception as e:
            error_msg = str(e)
            email_log.mark_as_failed(error_msg)
            logger.error(f"Failed to send email to {to_email}: {error_msg}")
            return False, f"Failed to send email: {error_msg}"
    
    def send_template_email(
        self,
        template_type: str,
        contact: Contact,
        context: Dict,
        email_type: str = None,
        **kwargs
    ) -> Tuple[bool, str]:
        """Send email using a template"""
        # Check if contact can receive emails
        if contact.unsubscribed or not contact.receives_notifications:
            return False, "Contact has unsubscribed or notifications disabled"
        
        # Get template
        try:
            template = EmailTemplate.objects.get(
                template_type=template_type,
                language=contact.preferred_language,
                is_active=True
            )
        except EmailTemplate.DoesNotExist:
            # Fallback to English
            try:
                template = EmailTemplate.objects.get(
                    template_type=template_type,
                    language='en',
                    is_active=True
                )
            except EmailTemplate.DoesNotExist:
                return False, f"No active template found for {template_type}"
        
        # Add default context
        context.update({
            'contact_name': contact.name,
            'company_name': contact.company.name,
            'unsubscribe_url': self._get_unsubscribe_url(contact),
            'current_year': datetime.now().year,
        })
        
        # Render template
        rendered = template.render(context)
        
        # Get from email based on template department
        from_email = self.get_from_email(template.department)
        
        # Send email
        return self.send_email(
            to_email=contact.email,
            subject=rendered['subject'],
            body_html=rendered['body_html'],
            body_text=rendered['body_text'],
            from_email=from_email,
            company=contact.company,
            contact=contact,
            email_type=email_type or template_type.split('_')[0],
            template=template,
            **kwargs
        )
    
    def _get_unsubscribe_url(self, contact: Contact) -> str:
        """Generate unsubscribe URL for contact"""
        if contact and contact.unsubscribe_token:
            # This would need to be implemented with proper URL routing
            return f"{settings.SITE_URL}/unsubscribe/{contact.unsubscribe_token}/"
        return ""
    
    def send_renewal_reminders(self) -> Dict[str, int]:
        """Send renewal reminders for contracts expiring soon"""
        if not self.is_business_hours():
            logger.info("Skipping renewal reminders - outside business hours")
            return {'skipped': 0}
        
        results = {
            'sent': 0,
            'failed': 0,
            'skipped': 0
        }
        
        # Define reminder schedule
        reminder_days = [30, 14, 7, 2]
        
        for days in reminder_days:
            # Find contracts expiring in X days
            target_date = timezone.now().date() + timedelta(days=days)
            
            contracts = Contract.objects.filter(
                status='Active',
                end_date=target_date,
                is_active=True
            ).select_related('company')
            
            for contract in contracts:
                # Check if we already have an active campaign
                campaign = EmailCampaign.objects.filter(
                    contract=contract,
                    campaign_type='renewal_sequence',
                    is_active=True
                ).first()
                
                if not campaign:
                    # Create new campaign
                    campaign = EmailCampaign.objects.create(
                        name=f"Renewal Reminder - {contract.contract_number}",
                        campaign_type='renewal_sequence',
                        company=contract.company,
                        contract=contract,
                        start_date=timezone.now().date(),
                        end_date=contract.end_date
                    )
                
                # Check if we should send email today
                if days == 30:
                    template_type = 'renewal_30_days'
                elif days == 14:
                    template_type = 'renewal_14_days'
                elif days == 7:
                    template_type = 'renewal_7_days'
                else:
                    template_type = 'renewal_urgent'
                
                # Get contacts to notify
                contacts = contract.company.contacts.filter(
                    is_active=True,
                    receives_notifications=True,
                    unsubscribed=False
                ).filter(
                    Q(contact_type__in=['Primary', 'Decision Maker']) |
                    Q(notification_types__contains='renewal')
                )
                
                for contact in contacts:
                    context = {
                        'contract': contract,
                        'days_until_expiry': days,
                        'contract_value': f"{contract.currency} {contract.value:,.2f}",
                        'monthly_value': f"{contract.currency} {contract.monthly_value:,.2f}",
                        'start_date': contract.start_date.strftime('%B %d, %Y'),
                        'end_date': contract.end_date.strftime('%B %d, %Y'),
                    }
                    
                    success, message = self.send_template_email(
                        template_type=template_type,
                        contact=contact,
                        context=context,
                        email_type='renewal',
                        contract=contract
                    )
                    
                    if success:
                        results['sent'] += 1
                        campaign.emails_sent += 1
                        campaign.last_email_sent = timezone.now()
                        campaign.save()
                    else:
                        results['failed'] += 1
                        logger.error(f"Failed to send renewal reminder: {message}")
        
        return results
    
    def send_payment_reminders(self) -> Dict[str, int]:
        """Send payment reminders for overdue invoices"""
        if not self.is_business_hours():
            logger.info("Skipping payment reminders - outside business hours")
            return {'skipped': 0}
        
        results = {
            'sent': 0,
            'failed': 0,
            'skipped': 0
        }
        
        # Find overdue invoices
        overdue_invoices = Invoice.objects.filter(
            status__in=['Sent', 'Overdue'],
            due_date__lt=timezone.now().date()
        ).select_related('contract__company')
        
        for invoice in overdue_invoices:
            days_overdue = (timezone.now().date() - invoice.due_date).days
            
            # Determine which reminder to send
            if days_overdue >= 14 and not invoice.second_reminder_sent:
                template_type = 'payment_reminder_14_days'
                invoice.second_reminder_sent = True
            elif days_overdue >= 7 and not invoice.first_reminder_sent:
                template_type = 'payment_reminder_7_days'
                invoice.first_reminder_sent = True
            elif days_overdue >= 21:
                template_type = 'payment_overdue'
            else:
                results['skipped'] += 1
                continue
            
            # Update invoice status
            if invoice.status != 'Overdue':
                invoice.status = 'Overdue'
            invoice.save()
            
            # Get billing contacts
            contacts = invoice.contract.company.contacts.filter(
                is_active=True,
                receives_notifications=True,
                unsubscribed=False
            ).filter(
                Q(contact_type='Billing') |
                Q(notification_types__contains='payment')
            )
            
            for contact in contacts:
                context = {
                    'invoice': invoice,
                    'days_overdue': days_overdue,
                    'invoice_amount': f"{invoice.currency} {invoice.total_amount:,.2f}",
                    'due_date': invoice.due_date.strftime('%B %d, %Y'),
                    'company_name': invoice.contract.company.name,
                }
                
                success, message = self.send_template_email(
                    template_type=template_type,
                    contact=contact,
                    context=context,
                    email_type='payment',
                    invoice=invoice
                )
                
                if success:
                    results['sent'] += 1
                else:
                    results['failed'] += 1
        
        return results
    
    def send_quarterly_checkins(self) -> Dict[str, int]:
        """Send quarterly check-in emails"""
        results = {
            'sent': 0,
            'failed': 0,
            'skipped': 0
        }

        # Find companies due for quarterly check-in
        three_months_ago = timezone.now().date() - timedelta(days=90)

        companies = Company.objects.filter(
            is_active=True,
            contracts__is_active=True,
            contracts__status='Active'
        ).exclude(
            email_logs__email_type='quarterly',
            email_logs__created_at__gte=three_months_ago
        ).distinct()

        for company in companies:
            # Get contacts for quarterly updates
            contacts = company.contacts.filter(
                is_active=True,
                receives_notifications=True,
                unsubscribed=False
            ).filter(
                Q(contact_type='Primary') |
                Q(notification_types__contains='quarterly')
            )

            for contact in contacts:
                context = {
                    'company': company,
                    'zone_count': company.zones.count(),
                    'active_zones': company.zones.filter(status='online').count(),
                }

                success, message = self.send_template_email(
                    template_type='quarterly_checkin',
                    contact=contact,
                    context=context,
                    email_type='quarterly'
                )

                if success:
                    results['sent'] += 1
                else:
                    results['failed'] += 1

        return results

    def send_quote_email(
        self,
        quote_id,
        recipients=None,
        subject=None,
        body=None,
        sender='admin',
        request=None
    ) -> Tuple[bool, str]:
        """
        Send quote email with PDF attachment

        Args:
            quote_id: ID of the quote to send
            recipients: List of email addresses (optional, defaults to company contacts)
            subject: Custom subject line (optional, uses template if not provided)
            body: Custom body text (optional, uses template if not provided)
            sender: Sender key from EMAIL_SENDERS config (legacy, will be replaced by request.user)
            request: HTTP request object (for per-user SMTP authentication)

        Returns:
            Tuple of (success: bool, message: str)
        """
        from crm_app.models import Quote
        from django.conf import settings
        from django.core.mail import get_connection
        import io

        # Get quote
        try:
            quote = Quote.objects.select_related('company', 'contact').get(id=quote_id)
        except Quote.DoesNotExist:
            return False, f"Quote with ID {quote_id} not found"

        # Get recipients
        if not recipients:
            recipients = list(quote.company.contacts.filter(
                email__isnull=False,
                is_active=True
            ).values_list('email', flat=True))

        if not recipients:
            return False, "No recipients found for this quote"

        # Get user's SMTP configuration (per-user SMTP)
        smtp_connection = None
        if request and request.user.is_authenticated:
            user_smtp = request.user.get_smtp_config()
            if user_smtp:
                # Use user's own SMTP credentials
                try:
                    smtp_connection = get_connection(
                        host=user_smtp['host'],
                        port=user_smtp['port'],
                        username=user_smtp['email'],
                        password=user_smtp['password'],
                        use_tls=user_smtp['use_tls'],
                    )
                    from_email = user_smtp['email']
                    sender_name = request.user.get_full_name() or request.user.username
                except Exception as e:
                    logger.error(f"Failed to create user SMTP connection: {e}")
                    # Fall back to default
                    sender_config = settings.EMAIL_SENDERS.get(sender, settings.EMAIL_SENDERS['admin'])
                    from_email = f"{sender_config['display']} <{sender_config['email']}>"
                    sender_name = sender_config['name']
            else:
                # User has no SMTP configured, use default
                sender_config = settings.EMAIL_SENDERS.get(sender, settings.EMAIL_SENDERS['admin'])
                from_email = f"{sender_config['display']} <{sender_config['email']}>"
                sender_name = sender_config['name']
        else:
            # No authenticated user, use legacy sender config
            sender_config = settings.EMAIL_SENDERS.get(sender, settings.EMAIL_SENDERS['admin'])
            from_email = f"{sender_config['display']} <{sender_config['email']}>"
            sender_name = sender_config['name']

        # Prepare context for template
        context = {
            'company_name': quote.company.legal_entity_name or quote.company.name,
            'contact_name': quote.contact.name if quote.contact else 'Valued Customer',
            'document_number': quote.quote_number,
            'amount': f"{quote.currency} {quote.total_value:,.2f}",
            'valid_until': quote.valid_until.strftime('%B %d, %Y'),
            'sender_name': sender_name,
            'current_year': datetime.now().year,
        }

        # Use template if subject/body not provided
        if not subject or not body:
            try:
                template = EmailTemplate.objects.get(
                    template_type='quote_send',
                    is_active=True
                )
                rendered = template.render(context)
                if not subject:
                    subject = rendered['subject']
                if not body:
                    body = rendered['body_text']
                    body_html = rendered['body_html']
            except EmailTemplate.DoesNotExist:
                # Fallback to default
                if not subject:
                    subject = f"Quote {quote.quote_number} from BMAsia Music"
                if not body:
                    body = f"Dear {context['contact_name']},\n\nPlease find attached quote {quote.quote_number} for {context['company_name']}.\n\nTotal Amount: {context['amount']}\nValid Until: {context['valid_until']}\n\nBest regards,\n{context['sender_name']}\nBMAsia Music"
                    body_html = body.replace('\n', '<br/>')
        else:
            body_html = body.replace('\n', '<br/>')

        # Generate PDF
        try:
            from django.test import RequestFactory
            from rest_framework.request import Request as DRFRequest
            from crm_app.views import QuoteViewSet
            from django.contrib.auth.models import AnonymousUser

            factory = RequestFactory()
            django_request = factory.get(f'/api/quotes/{quote.id}/pdf/')
            django_request.user = AnonymousUser()

            # Wrap in DRF Request to get query_params
            request = DRFRequest(django_request)

            viewset = QuoteViewSet()
            viewset.request = request
            viewset.kwargs = {'pk': quote.id}
            viewset.action = 'pdf'

            pdf_response = viewset.pdf(request, pk=quote.id)
            pdf_data = pdf_response.content
            pdf_filename = f"Quote_{quote.quote_number}.pdf"
        except Exception as e:
            logger.error(f"Failed to generate PDF for quote {quote.quote_number}: {e}")
            return False, f"Failed to generate PDF: {str(e)}"

        # Send to each recipient
        success_count = 0
        error_messages = []
        for recipient in recipients:
            try:
                # Find contact for this email
                contact = quote.company.contacts.filter(email=recipient).first()

                # Create email message
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=body,
                    from_email=from_email,
                    to=[recipient],
                    connection=smtp_connection
                )

                # Add HTML version
                msg.attach_alternative(body_html, "text/html")

                # Attach PDF
                msg.attach(pdf_filename, pdf_data, 'application/pdf')

                # Add tracking headers
                msg.extra_headers['X-BMAsia-Email-ID'] = f'quote_{quote.id}'
                if contact:
                    msg.extra_headers['List-Unsubscribe'] = self._get_unsubscribe_url(contact)

                # Send email
                msg.send(fail_silently=False)

                # Determine actual from_email for logging (extract from display format if needed)
                log_from_email = from_email
                if '<' in from_email and '>' in from_email:
                    log_from_email = from_email.split('<')[1].split('>')[0]

                # Log email
                email_log = EmailLog.objects.create(
                    company=quote.company,
                    contact=contact,
                    email_type='manual',
                    from_email=log_from_email,
                    to_email=recipient,
                    subject=subject,
                    body_html=body_html,
                    body_text=body,
                    status='sent',
                    sent_at=timezone.now()
                )

                success_count += 1
                logger.info(f"Quote email sent successfully to {recipient}")

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to send quote email to {recipient}: {error_msg}")
                error_messages.append(f"{recipient}: {error_msg}")

        # Update quote status
        if success_count > 0:
            quote.status = 'Sent'
            quote.sent_date = timezone.now().date()
            quote.save()

            return True, f"Quote sent successfully to {success_count} recipient(s)"
        else:
            detailed_errors = '; '.join(error_messages) if error_messages else 'Unknown error'
            return False, f"Failed to send quote to any recipients. Errors: {detailed_errors}"

    def send_contract_email(
        self,
        contract_id,
        recipients=None,
        subject=None,
        body=None,
        sender='admin',
        request=None
    ) -> Tuple[bool, str]:
        """
        Send contract email with PDF attachment

        Args:
            contract_id: ID of the contract to send
            recipients: List of email addresses (optional, defaults to company contacts)
            subject: Custom subject line (optional, uses template if not provided)
            body: Custom body text (optional, uses template if not provided)
            sender: Sender key from EMAIL_SENDERS config (legacy, will be replaced by request.user)
            request: HTTP request object (for per-user SMTP authentication)

        Returns:
            Tuple of (success: bool, message: str)
        """
        from django.conf import settings
        from django.core.mail import get_connection

        # Get contract
        try:
            contract = Contract.objects.select_related('company').get(id=contract_id)
        except Contract.DoesNotExist:
            return False, f"Contract with ID {contract_id} not found"

        # Get recipients
        if not recipients:
            recipients = list(contract.company.contacts.filter(
                email__isnull=False,
                is_active=True
            ).values_list('email', flat=True))

        if not recipients:
            return False, "No recipients found for this contract"

        # Get user's SMTP configuration (per-user SMTP)
        smtp_connection = None
        if request and request.user.is_authenticated:
            user_smtp = request.user.get_smtp_config()
            if user_smtp:
                # Use user's own SMTP credentials
                try:
                    smtp_connection = get_connection(
                        host=user_smtp['host'],
                        port=user_smtp['port'],
                        username=user_smtp['email'],
                        password=user_smtp['password'],
                        use_tls=user_smtp['use_tls'],
                    )
                    from_email = user_smtp['email']
                    sender_name = request.user.get_full_name() or request.user.username
                except Exception as e:
                    logger.error(f"Failed to create user SMTP connection: {e}")
                    # Fall back to default
                    sender_config = settings.EMAIL_SENDERS.get(sender, settings.EMAIL_SENDERS['admin'])
                    from_email = f"{sender_config['display']} <{sender_config['email']}>"
                    sender_name = sender_config['name']
            else:
                # User has no SMTP configured, use default
                sender_config = settings.EMAIL_SENDERS.get(sender, settings.EMAIL_SENDERS['admin'])
                from_email = f"{sender_config['display']} <{sender_config['email']}>"
                sender_name = sender_config['name']
        else:
            # No authenticated user, use legacy sender config
            sender_config = settings.EMAIL_SENDERS.get(sender, settings.EMAIL_SENDERS['admin'])
            from_email = f"{sender_config['display']} <{sender_config['email']}>"
            sender_name = sender_config['name']

        # Prepare context for template
        context = {
            'company_name': contract.company.legal_entity_name or contract.company.name,
            'contact_name': 'Valued Customer',
            'document_number': contract.contract_number,
            'amount': f"{contract.currency} {contract.value:,.2f}",
            'valid_until': contract.end_date.strftime('%B %d, %Y'),
            'sender_name': sender_name,
            'current_year': datetime.now().year,
        }

        # Use template if subject/body not provided
        if not subject or not body:
            try:
                template = EmailTemplate.objects.get(
                    template_type='contract_send',
                    is_active=True
                )
                rendered = template.render(context)
                if not subject:
                    subject = rendered['subject']
                if not body:
                    body = rendered['body_text']
                    body_html = rendered['body_html']
            except EmailTemplate.DoesNotExist:
                # Fallback to default
                if not subject:
                    subject = f"Contract {contract.contract_number} from BMAsia Music"
                if not body:
                    body = f"Dear {context['contact_name']},\n\nPlease find attached contract {contract.contract_number} for {context['company_name']}.\n\nContract Value: {context['amount']}\nValid Until: {context['valid_until']}\n\nBest regards,\n{context['sender_name']}\nBMAsia Music"
                    body_html = body.replace('\n', '<br/>')
        else:
            body_html = body.replace('\n', '<br/>')

        # Generate PDF by directly calling the PDF generation logic (avoids viewset complications)
        try:
            from crm_app.services.pdf_generator import generate_contract_pdf

            # Try using PDF generator service if it exists
            pdf_data = generate_contract_pdf(contract)
            pdf_filename = f"Contract_{contract.contract_number}.pdf"
        except ImportError:
            # Fallback: Generate inline using the same logic as the view
            try:
                from reportlab.lib.pagesizes import letter
                from reportlab.lib import colors
                from reportlab.lib.units import inch
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, HRFlowable
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.enums import TA_CENTER
                from io import BytesIO
                import os

                company = contract.company

                # Get entity-specific details based on billing_entity
                billing_entity = company.billing_entity
                if billing_entity == 'BMAsia (Thailand) Co., Ltd.':
                    entity_name = 'BMAsia (Thailand) Co., Ltd.'
                    entity_address = '725 S-Metro Building, Suite 144, Level 20, Sukhumvit Road, Klongtan Nuea Watthana, Bangkok 10110, Thailand'
                    entity_phone = '+66 2153 3520'
                    entity_tax = '0105548025073'
                    entity_bank = 'TMBThanachart Bank, Thonglor Soi 17 Branch'
                    entity_swift = 'TMBKTHBK'
                    entity_account = '916-1-00579-9'
                else:  # BMAsia Limited (Hong Kong)
                    entity_name = 'BMAsia Limited'
                    entity_address = '22nd Floor, Tai Yau Building, 181 Johnston Road, Wanchai, Hong Kong'
                    entity_phone = '+66 2153 3520'
                    entity_tax = None
                    entity_bank = 'HSBC, HK'
                    entity_swift = 'HSBCHKHHHKH'
                    entity_account = '808-021570-838'

                # Create PDF buffer
                buffer = BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.4*inch, bottomMargin=0.4*inch)
                elements = []
                styles = getSampleStyleSheet()

                # Add logo
                logo_path = os.path.join(settings.BASE_DIR, 'crm_app', 'static', 'crm_app', 'images', 'bmasia_logo.png')
                try:
                    if os.path.exists(logo_path):
                        logo = Image(logo_path, width=160, height=64, kind='proportional')
                        logo.hAlign = 'LEFT'
                        elements.append(logo)
                except Exception:
                    pass

                elements.append(Spacer(1, 0.1*inch))
                elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#FFA500'), spaceBefore=0, spaceAfter=0))
                elements.append(Spacer(1, 0.2*inch))

                # Contract title
                contract_title_style = ParagraphStyle(
                    'ContractTitle',
                    parent=styles['Heading1'],
                    fontSize=24,
                    textColor=colors.HexColor('#FFA500'),
                    spaceAfter=20,
                    alignment=TA_CENTER,
                    fontName='Helvetica-Bold'
                )
                elements.append(Paragraph("CONTRACT AGREEMENT", contract_title_style))

                # Basic contract info (simplified version)
                body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10)
                elements.append(Paragraph(f"<b>Contract Number:</b> {contract.contract_number}", body_style))
                elements.append(Paragraph(f"<b>Company:</b> {company.legal_entity_name or company.name}", body_style))
                elements.append(Paragraph(f"<b>Period:</b> {contract.start_date.strftime('%b %d, %Y')} - {contract.end_date.strftime('%b %d, %Y')}", body_style))
                elements.append(Paragraph(f"<b>Value:</b> {contract.currency} {contract.value:,.2f}", body_style))
                elements.append(Paragraph(f"<b>Status:</b> {contract.status}", body_style))

                # Build PDF
                doc.build(elements)
                pdf_data = buffer.getvalue()
                buffer.close()
                pdf_filename = f"Contract_{contract.contract_number}.pdf"

            except Exception as e:
                logger.error(f"Failed to generate PDF for contract {contract.contract_number}: {e}")
                return False, f"Failed to generate PDF: {str(e)}"

        # Send to each recipient
        success_count = 0
        error_messages = []
        for recipient in recipients:
            try:
                # Find contact for this email
                contact = contract.company.contacts.filter(email=recipient).first()

                # Create email message
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=body,
                    from_email=from_email,
                    to=[recipient],
                    connection=smtp_connection
                )

                # Add HTML version
                msg.attach_alternative(body_html, "text/html")

                # Attach PDF
                msg.attach(pdf_filename, pdf_data, 'application/pdf')

                # Add tracking headers
                msg.extra_headers['X-BMAsia-Email-ID'] = f'contract_{contract.id}'
                if contact:
                    msg.extra_headers['List-Unsubscribe'] = self._get_unsubscribe_url(contact)

                # Send email
                msg.send(fail_silently=False)

                # Determine actual from_email for logging (extract from display format if needed)
                log_from_email = from_email
                if '<' in from_email and '>' in from_email:
                    log_from_email = from_email.split('<')[1].split('>')[0]

                # Log email
                email_log = EmailLog.objects.create(
                    company=contract.company,
                    contact=contact,
                    email_type='manual',
                    from_email=log_from_email,
                    to_email=recipient,
                    subject=subject,
                    body_html=body_html,
                    body_text=body,
                    status='sent',
                    sent_at=timezone.now(),
                    contract=contract
                )

                success_count += 1
                logger.info(f"Contract email sent successfully to {recipient}")

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to send contract email to {recipient}: {error_msg}")
                error_messages.append(f"{recipient}: {error_msg}")

        # Update contract status
        if success_count > 0:
            contract.status = 'Sent'
            contract.save()

            return True, f"Contract sent successfully to {success_count} recipient(s)"
        else:
            detailed_errors = '; '.join(error_messages) if error_messages else 'Unknown error'
            return False, f"Failed to send contract to any recipients. Errors: {detailed_errors}"

    def send_invoice_email(
        self,
        invoice_id,
        recipients=None,
        subject=None,
        body=None,
        sender='admin',
        request=None
    ) -> Tuple[bool, str]:
        """
        Send invoice email with PDF attachment

        Args:
            invoice_id: ID of the invoice to send
            recipients: List of email addresses (optional, defaults to company contacts)
            subject: Custom subject line (optional, uses template if not provided)
            body: Custom body text (optional, uses template if not provided)
            sender: Sender key from EMAIL_SENDERS config (legacy, will be replaced by request.user)
            request: HTTP request object (for per-user SMTP authentication)

        Returns:
            Tuple of (success: bool, message: str)
        """
        from django.conf import settings
        from django.core.mail import get_connection

        # Get invoice
        try:
            invoice = Invoice.objects.select_related('contract__company').get(id=invoice_id)
        except Invoice.DoesNotExist:
            return False, f"Invoice with ID {invoice_id} not found"

        company = invoice.contract.company

        # Get recipients - prioritize billing contacts
        if not recipients:
            recipients = list(company.contacts.filter(
                email__isnull=False,
                is_active=True
            ).filter(
                Q(contact_type='Billing') |
                Q(notification_types__contains='invoice')
            ).values_list('email', flat=True))

            # Fallback to all contacts if no billing contacts
            if not recipients:
                recipients = list(company.contacts.filter(
                    email__isnull=False,
                    is_active=True
                ).values_list('email', flat=True))

        if not recipients:
            return False, "No recipients found for this invoice"

        # Get user's SMTP configuration (per-user SMTP)
        smtp_connection = None
        if request and request.user.is_authenticated:
            user_smtp = request.user.get_smtp_config()
            if user_smtp:
                # Use user's own SMTP credentials
                try:
                    smtp_connection = get_connection(
                        host=user_smtp['host'],
                        port=user_smtp['port'],
                        username=user_smtp['email'],
                        password=user_smtp['password'],
                        use_tls=user_smtp['use_tls'],
                    )
                    from_email = user_smtp['email']
                    sender_name = request.user.get_full_name() or request.user.username
                except Exception as e:
                    logger.error(f"Failed to create user SMTP connection: {e}")
                    # Fall back to default
                    sender_config = settings.EMAIL_SENDERS.get(sender, settings.EMAIL_SENDERS['admin'])
                    from_email = f"{sender_config['display']} <{sender_config['email']}>"
                    sender_name = sender_config['name']
            else:
                # User has no SMTP configured, use default
                sender_config = settings.EMAIL_SENDERS.get(sender, settings.EMAIL_SENDERS['admin'])
                from_email = f"{sender_config['display']} <{sender_config['email']}>"
                sender_name = sender_config['name']
        else:
            # No authenticated user, use legacy sender config
            sender_config = settings.EMAIL_SENDERS.get(sender, settings.EMAIL_SENDERS['admin'])
            from_email = f"{sender_config['display']} <{sender_config['email']}>"
            sender_name = sender_config['name']

        # Prepare context for template
        context = {
            'company_name': company.legal_entity_name or company.name,
            'contact_name': 'Valued Customer',
            'document_number': invoice.invoice_number,
            'amount': f"{invoice.currency} {invoice.total_amount:,.2f}",
            'valid_until': invoice.due_date.strftime('%B %d, %Y'),
            'sender_name': sender_name,
            'current_year': datetime.now().year,
        }

        # Use template if subject/body not provided
        if not subject or not body:
            try:
                template = EmailTemplate.objects.get(
                    template_type='invoice_send',
                    is_active=True
                )
                rendered = template.render(context)
                if not subject:
                    subject = rendered['subject']
                if not body:
                    body = rendered['body_text']
                    body_html = rendered['body_html']
            except EmailTemplate.DoesNotExist:
                # Fallback to default
                if not subject:
                    subject = f"Invoice {invoice.invoice_number} from BMAsia Music"
                if not body:
                    body = f"Dear {context['contact_name']},\n\nPlease find attached invoice {invoice.invoice_number} for {context['company_name']}.\n\nAmount Due: {context['amount']}\nDue Date: {context['valid_until']}\n\nBest regards,\n{context['sender_name']}\nBMAsia Music"
                    body_html = body.replace('\n', '<br/>')
        else:
            body_html = body.replace('\n', '<br/>')

        # Generate PDF
        try:
            from django.test import RequestFactory
            from rest_framework.request import Request as DRFRequest
            from crm_app.views import InvoiceViewSet
            from django.contrib.auth.models import AnonymousUser

            factory = RequestFactory()
            django_request = factory.get(f'/api/invoices/{invoice.id}/pdf/')
            django_request.user = AnonymousUser()

            # Wrap in DRF Request to get query_params
            request = DRFRequest(django_request)

            viewset = InvoiceViewSet()
            viewset.request = request
            viewset.kwargs = {'pk': invoice.id}
            viewset.action = 'pdf'

            pdf_response = viewset.pdf(request, pk=invoice.id)
            pdf_data = pdf_response.content
            pdf_filename = f"Invoice_{invoice.invoice_number}.pdf"
        except Exception as e:
            logger.error(f"Failed to generate PDF for invoice {invoice.invoice_number}: {e}")
            return False, f"Failed to generate PDF: {str(e)}"

        # Send to each recipient
        success_count = 0
        error_messages = []
        for recipient in recipients:
            try:
                # Find contact for this email
                contact = company.contacts.filter(email=recipient).first()

                # Create email message
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=body,
                    from_email=from_email,
                    to=[recipient],
                    connection=smtp_connection
                )

                # Add HTML version
                msg.attach_alternative(body_html, "text/html")

                # Attach PDF
                msg.attach(pdf_filename, pdf_data, 'application/pdf')

                # Add tracking headers
                msg.extra_headers['X-BMAsia-Email-ID'] = f'invoice_{invoice.id}'
                if contact:
                    msg.extra_headers['List-Unsubscribe'] = self._get_unsubscribe_url(contact)

                # Send email
                msg.send(fail_silently=False)

                # Determine actual from_email for logging (extract from display format if needed)
                log_from_email = from_email
                if '<' in from_email and '>' in from_email:
                    log_from_email = from_email.split('<')[1].split('>')[0]

                # Log email
                email_log = EmailLog.objects.create(
                    company=company,
                    contact=contact,
                    email_type='manual',
                    from_email=log_from_email,
                    to_email=recipient,
                    subject=subject,
                    body_html=body_html,
                    body_text=body,
                    status='sent',
                    sent_at=timezone.now(),
                    invoice=invoice
                )

                success_count += 1
                logger.info(f"Invoice email sent successfully to {recipient}")

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to send invoice email to {recipient}: {error_msg}")
                error_messages.append(f"{recipient}: {error_msg}")

        # Update invoice status
        if success_count > 0:
            invoice.status = 'Sent'
            invoice.save()

            return True, f"Invoice sent successfully to {success_count} recipient(s)"
        else:
            detailed_errors = '; '.join(error_messages) if error_messages else 'Unknown error'
            return False, f"Failed to send invoice to any recipients. Errors: {detailed_errors}"

    def send_manual_renewal_reminder(
        self,
        contract_id,
        recipients=None,
        subject=None,
        body=None,
        sender='admin',
        request=None
    ) -> Tuple[bool, str]:
        """
        Send manual renewal reminder
        Blocks if automated reminder was sent within last 24 hours

        Args:
            contract_id: ID of the contract
            recipients: List of email addresses (optional, defaults to company contacts)
            subject: Custom subject line (optional, uses template if not provided)
            body: Custom body text (optional, uses template if not provided)
            sender: Sender key from EMAIL_SENDERS config (legacy, will be replaced by request.user)
            request: HTTP request object (for per-user SMTP authentication)

        Returns:
            Tuple of (success: bool, message: str)
        """
        from django.conf import settings
        from django.core.mail import get_connection

        # Get contract
        try:
            contract = Contract.objects.select_related('company').get(id=contract_id)
        except Contract.DoesNotExist:
            return False, f"Contract with ID {contract_id} not found"

        # Check if automated reminder was sent in last 24 hours
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        recent_auto_reminder = EmailLog.objects.filter(
            contract=contract,
            email_type='renewal',
            created_at__gte=twenty_four_hours_ago
        ).exists()

        if recent_auto_reminder:
            raise ValueError("An automated renewal reminder was sent within the last 24 hours. Please wait before sending a manual reminder.")

        # Get recipients - prioritize decision makers
        if not recipients:
            recipients = list(contract.company.contacts.filter(
                email__isnull=False,
                is_active=True
            ).filter(
                Q(contact_type__in=['Primary', 'Decision Maker']) |
                Q(notification_types__contains='renewal')
            ).values_list('email', flat=True))

            # Fallback to all contacts if no decision makers
            if not recipients:
                recipients = list(contract.company.contacts.filter(
                    email__isnull=False,
                    is_active=True
                ).values_list('email', flat=True))

        if not recipients:
            return False, "No recipients found for this contract"

        # Get user's SMTP configuration (per-user SMTP)
        smtp_connection = None
        if request and request.user.is_authenticated:
            user_smtp = request.user.get_smtp_config()
            if user_smtp:
                # Use user's own SMTP credentials
                try:
                    smtp_connection = get_connection(
                        host=user_smtp['host'],
                        port=user_smtp['port'],
                        username=user_smtp['email'],
                        password=user_smtp['password'],
                        use_tls=user_smtp['use_tls'],
                    )
                    from_email = user_smtp['email']
                    sender_name = request.user.get_full_name() or request.user.username
                except Exception as e:
                    logger.error(f"Failed to create user SMTP connection: {e}")
                    # Fall back to default
                    sender_config = settings.EMAIL_SENDERS.get(sender, settings.EMAIL_SENDERS['admin'])
                    from_email = f"{sender_config['display']} <{sender_config['email']}>"
                    sender_name = sender_config['name']
            else:
                # User has no SMTP configured, use default
                sender_config = settings.EMAIL_SENDERS.get(sender, settings.EMAIL_SENDERS['admin'])
                from_email = f"{sender_config['display']} <{sender_config['email']}>"
                sender_name = sender_config['name']
        else:
            # No authenticated user, use legacy sender config
            sender_config = settings.EMAIL_SENDERS.get(sender, settings.EMAIL_SENDERS['admin'])
            from_email = f"{sender_config['display']} <{sender_config['email']}>"
            sender_name = sender_config['name']

        # Calculate days until expiry
        days_until_expiry = contract.days_until_expiry

        # Prepare context for template
        context = {
            'company_name': contract.company.legal_entity_name or contract.company.name,
            'contact_name': 'Valued Customer',
            'contract': contract,
            'days_until_expiry': days_until_expiry,
            'contract_value': f"{contract.currency} {contract.value:,.2f}",
            'monthly_value': f"{contract.currency} {contract.monthly_value:,.2f}",
            'start_date': contract.start_date.strftime('%B %d, %Y'),
            'end_date': contract.end_date.strftime('%B %d, %Y'),
            'sender_name': sender_name,
            'current_year': datetime.now().year,
        }

        # Use template if subject/body not provided
        if not subject or not body:
            try:
                template = EmailTemplate.objects.get(
                    template_type='renewal_manual',
                    is_active=True
                )
                rendered = template.render(context)
                if not subject:
                    subject = rendered['subject']
                if not body:
                    body = rendered['body_text']
                    body_html = rendered['body_html']
            except EmailTemplate.DoesNotExist:
                # Fallback to default
                if not subject:
                    subject = f"Contract Renewal Reminder - {contract.contract_number}"
                if not body:
                    body = f"Dear {context['contact_name']},\n\nThis is a reminder that your contract {contract.contract_number} will expire on {context['end_date']} ({days_until_expiry} days from now).\n\nContract Value: {context['contract_value']}\n\nPlease contact us to discuss renewal options.\n\nBest regards,\n{context['sender_name']}\nBMAsia Music"
                    body_html = body.replace('\n', '<br/>')
        else:
            body_html = body.replace('\n', '<br/>')

        # Send to each recipient
        success_count = 0
        for recipient in recipients:
            try:
                # Find contact for this email
                contact = contract.company.contacts.filter(email=recipient).first()

                # Create email message
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=body,
                    from_email=from_email,
                    to=[recipient],
                    connection=smtp_connection
                )

                # Add HTML version
                msg.attach_alternative(body_html, "text/html")

                # Add tracking headers
                msg.extra_headers['X-BMAsia-Email-ID'] = f'renewal_manual_{contract.id}'
                if contact:
                    msg.extra_headers['List-Unsubscribe'] = self._get_unsubscribe_url(contact)

                # Send email
                msg.send(fail_silently=False)

                # Determine actual from_email for logging (extract from display format if needed)
                log_from_email = from_email
                if '<' in from_email and '>' in from_email:
                    log_from_email = from_email.split('<')[1].split('>')[0]

                # Log email
                email_log = EmailLog.objects.create(
                    company=contract.company,
                    contact=contact,
                    email_type='renewal',
                    from_email=log_from_email,
                    to_email=recipient,
                    subject=subject,
                    body_html=body_html,
                    body_text=body,
                    status='sent',
                    sent_at=timezone.now(),
                    contract=contract
                )

                success_count += 1
                logger.info(f"Manual renewal reminder sent successfully to {recipient}")

            except Exception as e:
                logger.error(f"Failed to send renewal reminder to {recipient}: {e}")

        # Update contract reminder tracking
        if success_count > 0:
            contract.renewal_notice_sent = True
            contract.renewal_notice_date = timezone.now().date()
            contract.save()

            return True, f"Renewal reminder sent successfully to {success_count} recipient(s)"
        else:
            return False, "Failed to send renewal reminder to any recipients"

    # ============================================================================
    # EMAIL SEQUENCE / DRIP CAMPAIGN METHODS
    # ============================================================================

    def enroll_contact_in_sequence(self, sequence_id, contact_id, company_id=None, notes=''):
        """
        Enroll a contact in an email sequence.

        Args:
            sequence_id: UUID of EmailSequence
            contact_id: UUID of Contact
            company_id: Optional UUID of Company
            notes: Optional enrollment notes

        Returns:
            SequenceEnrollment object

        Raises:
            ValueError: If sequence not active, contact already enrolled, or contact unsubscribed
        """
        # Get sequence
        try:
            sequence = EmailSequence.objects.get(id=sequence_id)
        except EmailSequence.DoesNotExist:
            raise ValueError(f"Email sequence with ID {sequence_id} not found")

        # Validate sequence is active
        if sequence.status != 'active':
            raise ValueError("Sequence is not active")

        # Get contact
        try:
            contact = Contact.objects.get(id=contact_id)
        except Contact.DoesNotExist:
            raise ValueError(f"Contact with ID {contact_id} not found")

        # Check if contact can receive emails
        if not contact.receives_notifications:
            raise ValueError("Contact has unsubscribed from emails")

        # Check if already enrolled
        existing_enrollment = SequenceEnrollment.objects.filter(
            sequence=sequence,
            contact=contact
        ).first()

        if existing_enrollment:
            raise ValueError("Contact already enrolled in this sequence")

        # Get company if provided
        company = None
        if company_id:
            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                logger.warning(f"Company with ID {company_id} not found, proceeding without company")

        # Create enrollment
        enrollment = SequenceEnrollment.objects.create(
            sequence=sequence,
            contact=contact,
            company=company,
            notes=notes,
            status='active',
            current_step_number=1,
            started_at=None  # Will be set when first email sends
        )

        # Schedule first step
        self.schedule_step_execution(enrollment, step_number=1)

        logger.info(f"Enrolled {contact.email} in sequence '{sequence.name}' (ID: {sequence.id})")

        return enrollment

    def schedule_step_execution(self, enrollment, step_number):
        """
        Schedule a sequence step for execution.

        Args:
            enrollment: SequenceEnrollment object
            step_number: Which step to schedule (1, 2, 3, etc.)

        Returns:
            SequenceStepExecution object or None if step doesn't exist
        """
        # Get the step
        try:
            step = SequenceStep.objects.get(
                sequence=enrollment.sequence,
                step_number=step_number,
                is_active=True
            )
        except SequenceStep.DoesNotExist:
            logger.info(f"No active step {step_number} found for sequence {enrollment.sequence.name}")
            return None

        # Calculate scheduled_for time
        if step_number == 1:
            # First step: schedule based on enrollment time
            base_time = enrollment.enrolled_at
        else:
            # Subsequent steps: schedule based on previous step's sent_at time
            previous_execution = SequenceStepExecution.objects.filter(
                enrollment=enrollment,
                step__step_number=step_number - 1,
                status='sent'
            ).first()

            if not previous_execution or not previous_execution.sent_at:
                # Previous step not sent yet, can't schedule this one
                logger.debug(f"Previous step {step_number - 1} not sent yet, cannot schedule step {step_number}")
                return None

            base_time = previous_execution.sent_at

        # Add delay
        scheduled_for = base_time + timedelta(days=step.delay_days)

        # Create execution
        execution = SequenceStepExecution.objects.create(
            enrollment=enrollment,
            step=step,
            scheduled_for=scheduled_for,
            status='scheduled',
            attempt_count=0
        )

        logger.info(f"Scheduled step {step_number} for {enrollment.contact.email} at {scheduled_for}")

        return execution

    def process_sequence_steps(self, max_emails=100):
        """
        Process pending sequence step executions.
        This method is called by the cron job.

        Args:
            max_emails: Maximum number of emails to send in this run

        Returns:
            dict with stats: {'sent': X, 'failed': Y, 'skipped': Z}
        """
        results = {
            'sent': 0,
            'failed': 0,
            'skipped': 0
        }

        # Find pending executions
        pending_executions = SequenceStepExecution.objects.filter(
            status='scheduled',
            scheduled_for__lte=timezone.now()
        ).select_related(
            'enrollment__contact',
            'enrollment__sequence',
            'enrollment__company',
            'step__email_template'
        ).order_by('scheduled_for')[:max_emails]

        logger.info(f"Found {pending_executions.count()} pending sequence step executions")

        for execution in pending_executions:
            enrollment = execution.enrollment
            contact = enrollment.contact

            # Check business hours - skip if outside business hours
            if not self.is_business_hours():
                logger.debug(f"Outside business hours, skipping execution {execution.id}")
                results['skipped'] += 1
                continue

            # Check enrollment status
            if enrollment.status != 'active':
                logger.info(f"Enrollment {enrollment.id} is not active (status: {enrollment.status}), skipping execution")
                execution.status = 'skipped'
                execution.save()
                results['skipped'] += 1
                continue

            # Check contact preferences
            if not contact.receives_notifications:
                logger.info(f"Contact {contact.email} has unsubscribed, marking enrollment as unsubscribed")
                enrollment.status = 'unsubscribed'
                enrollment.save()
                execution.status = 'skipped'
                execution.save()
                results['skipped'] += 1
                continue

            # Execute the step
            success = self.execute_sequence_step(execution.id)
            if success:
                results['sent'] += 1
            else:
                results['failed'] += 1

        logger.info(f"Sequence processing complete: {results}")
        return results

    def execute_sequence_step(self, execution_id):
        """
        Execute a single sequence step (send the email).

        Args:
            execution_id: UUID of SequenceStepExecution

        Returns:
            bool: True if sent successfully, False otherwise
        """
        # Get execution
        try:
            execution = SequenceStepExecution.objects.select_related(
                'enrollment__contact',
                'enrollment__company',
                'enrollment__sequence',
                'step__email_template'
            ).get(id=execution_id)
        except SequenceStepExecution.DoesNotExist:
            logger.error(f"SequenceStepExecution with ID {execution_id} not found")
            return False

        # Increment attempt count
        execution.attempt_count += 1
        execution.save()

        # Get template, contact, and context
        template = execution.step.email_template
        contact = execution.enrollment.contact
        company = execution.enrollment.company

        # Render template with context
        context = {
            'contact': contact,
            'company': company,
            'sequence': execution.enrollment.sequence,
        }

        try:
            rendered = template.render(context)
            subject = rendered['subject']
            html_content = rendered['body_html']
            text_content = rendered['body_text']
        except Exception as e:
            logger.error(f"Failed to render template for execution {execution_id}: {e}")
            execution.status = 'failed'
            execution.error_message = f"Template rendering error: {str(e)}"
            execution.save()
            return False

        # Determine sender based on sequence type
        sequence_type = execution.enrollment.sequence.sequence_type
        from_email = self._get_sequence_sender(sequence_type)

        # Send email using existing method
        try:
            success, message = self.send_email(
                to_email=contact.email,
                subject=subject,
                body_html=html_content,
                body_text=text_content,
                from_email=from_email,
                company=company,
                contact=contact,
                email_type='sequence',
                template=template
            )

            if not success:
                raise Exception(message)

            # Get the email log that was just created
            email_log = EmailLog.objects.filter(
                contact=contact,
                subject=subject,
                status='sent'
            ).order_by('-sent_at').first()

            # Update execution
            execution.status = 'sent'
            execution.sent_at = timezone.now()
            execution.email_log = email_log
            execution.save()

            # Update enrollment
            enrollment = execution.enrollment
            if not enrollment.started_at:
                enrollment.started_at = timezone.now()

            # Schedule next step
            next_step_number = execution.step.step_number + 1
            next_scheduled = self.schedule_step_execution(enrollment, next_step_number)

            # If no more steps, mark enrollment complete
            if not next_scheduled:
                enrollment.status = 'completed'
                enrollment.completed_at = timezone.now()
                logger.info(f"Enrollment {enrollment.id} completed - no more steps")
            else:
                enrollment.current_step_number = next_step_number
                logger.info(f"Scheduled next step {next_step_number} for enrollment {enrollment.id}")

            enrollment.save()

            logger.info(f"Successfully executed step {execution.step.step_number} for {contact.email}")
            return True

        except Exception as e:
            # Log error
            error_msg = str(e)
            execution.status = 'failed'
            execution.error_message = error_msg
            execution.save()

            logger.error(f"Failed to execute sequence step {execution_id}: {error_msg}")

            # Retry logic: if attempt_count < 3, reset to 'scheduled' to retry later
            if execution.attempt_count < 3:
                execution.status = 'scheduled'
                execution.save()
                logger.info(f"Execution {execution_id} will be retried (attempt {execution.attempt_count}/3)")
            else:
                logger.warning(f"Execution {execution_id} failed after 3 attempts, giving up")

            return False

    def unenroll_contact(self, enrollment_id, reason='manual'):
        """
        Unenroll a contact from a sequence.

        Args:
            enrollment_id: UUID of SequenceEnrollment
            reason: 'manual', 'unsubscribed', 'completed', etc.

        Returns:
            bool: True if unenrolled successfully
        """
        # Get enrollment
        try:
            enrollment = SequenceEnrollment.objects.get(id=enrollment_id)
        except SequenceEnrollment.DoesNotExist:
            logger.error(f"SequenceEnrollment with ID {enrollment_id} not found")
            return False

        # Update enrollment status
        if reason == 'manual':
            enrollment.status = 'paused'
        else:
            enrollment.status = reason

        # Cancel pending executions
        cancelled_count = SequenceStepExecution.objects.filter(
            enrollment=enrollment,
            status='scheduled'
        ).update(status='skipped')

        # Add notes
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        enrollment.notes += f"\nUnenrolled on {timestamp}: {reason}"
        enrollment.save()

        logger.info(f"Unenrolled contact {enrollment.contact.email} from sequence {enrollment.sequence.name} (reason: {reason}). Cancelled {cancelled_count} pending steps.")

        return True


# Create singleton instance
email_service = EmailService()