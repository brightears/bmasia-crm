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


# Create singleton instance
email_service = EmailService()