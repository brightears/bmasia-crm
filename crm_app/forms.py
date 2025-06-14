"""
Forms for CRM app
"""

from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from .models import Contact, DocumentAttachment, EmailTemplate, Company


class SendEmailForm(forms.Form):
    """Form for sending emails from admin"""
    
    # Recipients
    contacts = forms.ModelMultipleChoiceField(
        queryset=Contact.objects.none(),
        widget=FilteredSelectMultiple('contacts', is_stacked=False),
        required=True,
        help_text="Select one or more contacts to send email to"
    )
    
    # Email content
    subject = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'style': 'width: 100%;'})
    )
    
    body = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 15,
            'style': 'width: 100%; font-family: monospace;'
        }),
        help_text="Write your email in plain text. HTML will be generated automatically."
    )
    
    # Attachments
    attachments = forms.ModelMultipleChoiceField(
        queryset=DocumentAttachment.objects.none(),
        widget=FilteredSelectMultiple('attachments', is_stacked=False),
        required=False,
        help_text="Select documents to attach to this email"
    )
    
    # Options
    send_test = forms.BooleanField(
        required=False,
        initial=False,
        help_text="Send test email to yourself instead of selected recipients"
    )
    
    def __init__(self, *args, **kwargs):
        template = kwargs.pop('template', None)
        company = kwargs.pop('company', None)
        user = kwargs.pop('user', None)
        
        super().__init__(*args, **kwargs)
        
        # Set up contacts queryset
        if company:
            self.fields['contacts'].queryset = Contact.objects.filter(
                company=company,
                is_active=True,
                unsubscribed=False
            ).order_by('name')
        else:
            self.fields['contacts'].queryset = Contact.objects.filter(
                is_active=True,
                unsubscribed=False
            ).order_by('company__name', 'name')
        
        # Set up attachments queryset
        if company:
            self.fields['attachments'].queryset = DocumentAttachment.objects.filter(
                company=company,
                is_active=True
            ).order_by('-created_at')
        else:
            self.fields['attachments'].queryset = DocumentAttachment.objects.filter(
                is_active=True
            ).order_by('company__name', '-created_at')
        
        # Pre-fill from template if provided
        if template:
            # Render template with sample context for preview
            sample_context = {
                'company_name': '{{company_name}}',
                'contact_name': '{{contact_name}}',
                'days_until_expiry': '{{days_until_expiry}}',
                'contract_value': '{{contract_value}}',
                'monthly_value': '{{monthly_value}}',
                'invoice_amount': '{{invoice_amount}}',
                'zone_count': '{{zone_count}}',
            }
            
            self.fields['subject'].initial = template.subject
            self.fields['body'].initial = template.body_text


class BulkEmailForm(forms.Form):
    """Form for sending bulk emails based on criteria"""
    
    # Recipient criteria
    companies = forms.ModelMultipleChoiceField(
        queryset=Company.objects.filter(is_active=True),
        widget=FilteredSelectMultiple('companies', is_stacked=False),
        required=False,
        help_text="Select specific companies (leave empty for all)"
    )
    
    contact_types = forms.MultipleChoiceField(
        choices=[
            ('Primary', 'Primary Contact'),
            ('Technical', 'Technical Contact'),
            ('Billing', 'Billing Contact'),
            ('Decision Maker', 'Decision Maker'),
        ],
        widget=forms.CheckboxSelectMultiple,
        required=True,
        initial=['Primary'],
        help_text="Select which contact types should receive the email"
    )
    
    # Template selection
    template = forms.ModelChoiceField(
        queryset=EmailTemplate.objects.filter(is_active=True),
        required=True,
        help_text="Select email template to use"
    )
    
    # Options
    preview_only = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Preview recipients without sending (recommended first step)"
    )