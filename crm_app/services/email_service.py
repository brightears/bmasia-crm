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
    Contact, Company, Contract, Invoice, DocumentAttachment
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
        """Get appropriate from email based on department"""
        department_emails = {
            'Sales': settings.SALES_EMAIL,
            'Finance': settings.FINANCE_EMAIL,
            'Tech Support': settings.SUPPORT_EMAIL,
            'Music Design': settings.MUSIC_DESIGN_EMAIL,
        }
        
        return department_emails.get(department, settings.DEFAULT_FROM_EMAIL)
    
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
        attachments: List[DocumentAttachment] = None
    ) -> Tuple[bool, str]:
        """
        Send an email and log it
        Returns: (success: bool, message: str)
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
                reply_to=[reply_to] if reply_to else None
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
        sender='admin'
    ) -> Tuple[bool, str]:
        """
        Send quote email with PDF attachment

        Args:
            quote_id: ID of the quote to send
            recipients: List of email addresses (optional, defaults to company contacts)
            subject: Custom subject line (optional, uses template if not provided)
            body: Custom body text (optional, uses template if not provided)
            sender: Sender key from EMAIL_SENDERS config

        Returns:
            Tuple of (success: bool, message: str)
        """
        from crm_app.models import Quote
        from django.conf import settings
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

        # Get sender configuration
        sender_config = settings.EMAIL_SENDERS.get(sender, settings.EMAIL_SENDERS['admin'])
        from_email = f"{sender_config['display']} <{sender_config['email']}>"

        # Prepare context for template
        context = {
            'company_name': quote.company.legal_entity_name or quote.company.name,
            'contact_name': quote.contact.name if quote.contact else 'Valued Customer',
            'document_number': quote.quote_number,
            'amount': f"{quote.currency} {quote.total_value:,.2f}",
            'valid_until': quote.valid_until.strftime('%B %d, %Y'),
            'sender_name': sender_config['name'],
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

            pdf_response = viewset.pdf(request, pk=quote.id)
            pdf_data = pdf_response.content
            pdf_filename = f"Quote_{quote.quote_number}.pdf"
        except Exception as e:
            logger.error(f"Failed to generate PDF for quote {quote.quote_number}: {e}")
            return False, f"Failed to generate PDF: {str(e)}"

        # Send to each recipient
        success_count = 0
        for recipient in recipients:
            try:
                # Find contact for this email
                contact = quote.company.contacts.filter(email=recipient).first()

                # Create email message
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=body,
                    from_email=from_email,
                    to=[recipient]
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

                # Log email
                email_log = EmailLog.objects.create(
                    company=quote.company,
                    contact=contact,
                    email_type='manual',
                    from_email=sender_config['email'],
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
                logger.error(f"Failed to send quote email to {recipient}: {e}")

        # Update quote status
        if success_count > 0:
            quote.status = 'Sent'
            quote.sent_date = timezone.now().date()
            quote.save()

            return True, f"Quote sent successfully to {success_count} recipient(s)"
        else:
            return False, "Failed to send quote to any recipients"

    def send_contract_email(
        self,
        contract_id,
        recipients=None,
        subject=None,
        body=None,
        sender='admin'
    ) -> Tuple[bool, str]:
        """
        Send contract email with PDF attachment

        Args:
            contract_id: ID of the contract to send
            recipients: List of email addresses (optional, defaults to company contacts)
            subject: Custom subject line (optional, uses template if not provided)
            body: Custom body text (optional, uses template if not provided)
            sender: Sender key from EMAIL_SENDERS config

        Returns:
            Tuple of (success: bool, message: str)
        """
        from django.conf import settings

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

        # Get sender configuration
        sender_config = settings.EMAIL_SENDERS.get(sender, settings.EMAIL_SENDERS['admin'])
        from_email = f"{sender_config['display']} <{sender_config['email']}>"

        # Prepare context for template
        context = {
            'company_name': contract.company.legal_entity_name or contract.company.name,
            'contact_name': 'Valued Customer',
            'document_number': contract.contract_number,
            'amount': f"{contract.currency} {contract.value:,.2f}",
            'valid_until': contract.end_date.strftime('%B %d, %Y'),
            'sender_name': sender_config['name'],
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
        for recipient in recipients:
            try:
                # Find contact for this email
                contact = contract.company.contacts.filter(email=recipient).first()

                # Create email message
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=body,
                    from_email=from_email,
                    to=[recipient]
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

                # Log email
                email_log = EmailLog.objects.create(
                    company=contract.company,
                    contact=contact,
                    email_type='manual',
                    from_email=sender_config['email'],
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
                logger.error(f"Failed to send contract email to {recipient}: {e}")

        # Update contract status
        if success_count > 0:
            contract.status = 'Sent'
            contract.save()

            return True, f"Contract sent successfully to {success_count} recipient(s)"
        else:
            return False, "Failed to send contract to any recipients"

    def send_invoice_email(
        self,
        invoice_id,
        recipients=None,
        subject=None,
        body=None,
        sender='admin'
    ) -> Tuple[bool, str]:
        """
        Send invoice email with PDF attachment

        Args:
            invoice_id: ID of the invoice to send
            recipients: List of email addresses (optional, defaults to company contacts)
            subject: Custom subject line (optional, uses template if not provided)
            body: Custom body text (optional, uses template if not provided)
            sender: Sender key from EMAIL_SENDERS config

        Returns:
            Tuple of (success: bool, message: str)
        """
        from django.conf import settings

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

        # Get sender configuration
        sender_config = settings.EMAIL_SENDERS.get(sender, settings.EMAIL_SENDERS['admin'])
        from_email = f"{sender_config['display']} <{sender_config['email']}>"

        # Prepare context for template
        context = {
            'company_name': company.legal_entity_name or company.name,
            'contact_name': 'Valued Customer',
            'document_number': invoice.invoice_number,
            'amount': f"{invoice.currency} {invoice.total_amount:,.2f}",
            'valid_until': invoice.due_date.strftime('%B %d, %Y'),
            'sender_name': sender_config['name'],
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

            pdf_response = viewset.pdf(request, pk=invoice.id)
            pdf_data = pdf_response.content
            pdf_filename = f"Invoice_{invoice.invoice_number}.pdf"
        except Exception as e:
            logger.error(f"Failed to generate PDF for invoice {invoice.invoice_number}: {e}")
            return False, f"Failed to generate PDF: {str(e)}"

        # Send to each recipient
        success_count = 0
        for recipient in recipients:
            try:
                # Find contact for this email
                contact = company.contacts.filter(email=recipient).first()

                # Create email message
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=body,
                    from_email=from_email,
                    to=[recipient]
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

                # Log email
                email_log = EmailLog.objects.create(
                    company=company,
                    contact=contact,
                    email_type='manual',
                    from_email=sender_config['email'],
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
                logger.error(f"Failed to send invoice email to {recipient}: {e}")

        # Update invoice status
        if success_count > 0:
            invoice.status = 'Sent'
            invoice.save()

            return True, f"Invoice sent successfully to {success_count} recipient(s)"
        else:
            return False, "Failed to send invoice to any recipients"

    def send_manual_renewal_reminder(
        self,
        contract_id,
        recipients=None,
        subject=None,
        body=None,
        sender='admin'
    ) -> Tuple[bool, str]:
        """
        Send manual renewal reminder
        Blocks if automated reminder was sent within last 24 hours

        Args:
            contract_id: ID of the contract
            recipients: List of email addresses (optional, defaults to company contacts)
            subject: Custom subject line (optional, uses template if not provided)
            body: Custom body text (optional, uses template if not provided)
            sender: Sender key from EMAIL_SENDERS config

        Returns:
            Tuple of (success: bool, message: str)
        """
        from django.conf import settings

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

        # Get sender configuration
        sender_config = settings.EMAIL_SENDERS.get(sender, settings.EMAIL_SENDERS['admin'])
        from_email = f"{sender_config['display']} <{sender_config['email']}>"

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
            'sender_name': sender_config['name'],
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
                    to=[recipient]
                )

                # Add HTML version
                msg.attach_alternative(body_html, "text/html")

                # Add tracking headers
                msg.extra_headers['X-BMAsia-Email-ID'] = f'renewal_manual_{contract.id}'
                if contact:
                    msg.extra_headers['List-Unsubscribe'] = self._get_unsubscribe_url(contact)

                # Send email
                msg.send(fail_silently=False)

                # Log email
                email_log = EmailLog.objects.create(
                    company=contract.company,
                    contact=contact,
                    email_type='renewal',
                    from_email=sender_config['email'],
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


# Create singleton instance
email_service = EmailService()