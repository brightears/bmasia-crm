"""
Custom admin views for CRM app
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import permission_required
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.db.models import Q

from .models import EmailTemplate, Contact, Company, DocumentAttachment
from .forms import SendEmailForm, BulkEmailForm
from .services.email_service import email_service
from .utils.email_utils import text_to_html


@staff_member_required
def send_email_view(request, template_id=None, company_id=None):
    """Admin view for sending emails with recipient selection and attachments"""
    
    template = None
    company = None
    
    if template_id:
        template = get_object_or_404(EmailTemplate, pk=template_id)
    
    if company_id:
        company = get_object_or_404(Company, pk=company_id)
    
    if request.method == 'POST':
        form = SendEmailForm(
            request.POST,
            template=template,
            company=company,
            user=request.user
        )
        
        if form.is_valid():
            # Get form data
            contacts = form.cleaned_data['contacts']
            subject = form.cleaned_data['subject']
            body_text = form.cleaned_data['body']
            attachments = form.cleaned_data['attachments']
            send_test = form.cleaned_data['send_test']
            
            # Convert text to HTML
            body_html = text_to_html(body_text)
            
            # Determine recipients
            if send_test:
                # Send test email to current user
                recipients = [(request.user.email, request.user.get_full_name() or request.user.username)]
                messages.info(request, f"Sending test email to {request.user.email}")
            else:
                recipients = [(contact.email, contact.name) for contact in contacts]
            
            # Send emails
            sent_count = 0
            failed_count = 0
            
            for email, name in recipients:
                # Prepare context for template variables
                if send_test:
                    context = {
                        'contact_name': name,
                        'company_name': 'Test Company',
                        'current_year': 2025,
                    }
                else:
                    contact = contacts.filter(email=email).first()
                    context = {
                        'contact_name': contact.name,
                        'company_name': contact.company.name,
                        'current_year': 2025,
                    }
                
                # Render subject and body with context
                from django.template import Template, Context
                subject_template = Template(subject)
                body_template = Template(body_text)
                
                rendered_subject = subject_template.render(Context(context))
                rendered_body = body_template.render(Context(context))
                rendered_html = text_to_html(rendered_body)
                
                # Send email
                success, message = email_service.send_email(
                    to_email=email,
                    subject=rendered_subject,
                    body_html=rendered_html,
                    body_text=rendered_body,
                    from_email=request.user.email if send_test else None,
                    company=contact.company if not send_test else None,
                    contact=contact if not send_test else None,
                    email_type='manual',
                    template=template,
                    attachments=list(attachments) if attachments else None
                )
                
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
                    messages.error(request, f"Failed to send to {email}: {message}")
            
            # Show results
            if sent_count > 0:
                messages.success(request, f"Successfully sent {sent_count} email(s)")
            
            if failed_count > 0:
                messages.error(request, f"Failed to send {failed_count} email(s)")
            
            # Redirect based on where we came from
            if template:
                return redirect('admin:crm_app_emailtemplate_changelist')
            elif company:
                return redirect('admin:crm_app_company_change', company.pk)
            else:
                return redirect('admin:crm_app_emaillog_changelist')
    
    else:
        form = SendEmailForm(
            template=template,
            company=company,
            user=request.user
        )
    
    context = {
        'form': form,
        'template': template,
        'company': company,
        'title': 'Send Email',
        'opts': EmailTemplate._meta if template else Company._meta if company else None,
    }
    
    return render(request, 'admin/crm_app/send_email.html', context)


@staff_member_required
def preview_bulk_email_view(request, template_id):
    """Preview bulk email recipients before sending"""
    
    template = get_object_or_404(EmailTemplate, pk=template_id)
    
    if request.method == 'POST':
        form = BulkEmailForm(request.POST)
        
        if form.is_valid():
            companies = form.cleaned_data['companies']
            contact_types = form.cleaned_data['contact_types']
            preview_only = form.cleaned_data['preview_only']
            
            # Build recipient query
            contacts_query = Contact.objects.filter(
                is_active=True,
                receives_notifications=True,
                unsubscribed=False,
                contact_type__in=contact_types
            )
            
            if companies:
                contacts_query = contacts_query.filter(company__in=companies)
            
            contacts = contacts_query.select_related('company').order_by('company__name', 'name')
            
            if not preview_only and request.POST.get('confirm_send'):
                # Actually send emails
                sent_count = 0
                failed_count = 0
                
                for contact in contacts:
                    # Prepare context based on template type
                    context = {
                        'contact_name': contact.name,
                        'company_name': contact.company.name,
                        'current_year': 2025,
                    }
                    
                    # Add specific context based on template type
                    if 'renewal' in template.template_type:
                        # Get active contract
                        contract = contact.company.contracts.filter(
                            is_active=True,
                            status='Active'
                        ).first()
                        
                        if contract:
                            context.update({
                                'contract': contract,
                                'days_until_expiry': contract.days_until_expiry,
                                'contract_value': f"{contract.currency} {contract.value:,.2f}",
                                'monthly_value': f"{contract.currency} {contract.monthly_value:,.2f}",
                            })
                    
                    success, message = email_service.send_template_email(
                        template_type=template.template_type,
                        contact=contact,
                        context=context,
                        email_type='manual'
                    )
                    
                    if success:
                        sent_count += 1
                    else:
                        failed_count += 1
                
                messages.success(request, f"Sent {sent_count} emails successfully")
                if failed_count > 0:
                    messages.error(request, f"Failed to send {failed_count} emails")
                
                return redirect('admin:crm_app_emailtemplate_changelist')
            
            # Show preview
            context = {
                'form': form,
                'template': template,
                'contacts': contacts,
                'contact_count': contacts.count(),
                'title': f'Preview Bulk Email - {template.name}',
                'opts': EmailTemplate._meta,
            }
            
            return render(request, 'admin/crm_app/preview_bulk_email.html', context)
    
    else:
        form = BulkEmailForm()
    
    context = {
        'form': form,
        'template': template,
        'title': f'Send Bulk Email - {template.name}',
        'opts': EmailTemplate._meta,
    }
    
    return render(request, 'admin/crm_app/send_bulk_email.html', context)