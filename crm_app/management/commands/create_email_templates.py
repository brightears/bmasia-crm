"""
Management command to create initial email templates
"""

from django.core.management.base import BaseCommand
from crm_app.models import EmailTemplate, User


class Command(BaseCommand):
    help = 'Create initial email templates for the system'

    def handle(self, *args, **options):
        templates = [
            # Renewal reminders
            {
                'name': '30-Day Renewal Reminder (EN)',
                'template_type': 'renewal_30_days',
                'language': 'en',
                'department': 'Sales',
                'subject': 'Your {{company_name}} subscription expires in 30 days',
                'body_html': '''
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2c3e50;">Subscription Renewal Reminder</h2>
        
        <p>Dear {{contact_name}},</p>
        
        <p>We hope you're enjoying your music experience with BMAsia. This is a friendly reminder that your subscription for <strong>{{company_name}}</strong> will expire in <strong>{{days_until_expiry}} days</strong> on <strong>{{end_date}}</strong>.</p>
        
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="margin-top: 0;">Contract Details:</h3>
            <ul style="list-style: none; padding: 0;">
                <li><strong>Contract Number:</strong> {{contract.contract_number}}</li>
                <li><strong>Current Period:</strong> {{start_date}} - {{end_date}}</li>
                <li><strong>Contract Value:</strong> {{contract_value}}</li>
                <li><strong>Monthly Value:</strong> {{monthly_value}}</li>
            </ul>
        </div>
        
        <p>To ensure uninterrupted service for your locations, please contact us to discuss your renewal options. We'd be happy to review your current usage and recommend any adjustments that might benefit your business.</p>
        
        <p>You can reach us at:</p>
        <ul>
            <li>Email: sales@bmasiamusic.com</li>
            <li>Phone: +66 2 123 4567</li>
        </ul>
        
        <p>Thank you for choosing BMAsia for your background music needs!</p>
        
        <p>Best regards,<br>
        The BMAsia Team</p>
        
        <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
        <p style="font-size: 12px; color: #666;">
            You're receiving this email because you're listed as a contact for {{company_name}}. 
            <a href="{{unsubscribe_url}}" style="color: #666;">Unsubscribe</a>
        </p>
    </div>
</body>
</html>
                ''',
                'body_text': '''Dear {{contact_name}},

We hope you're enjoying your music experience with BMAsia. This is a friendly reminder that your subscription for {{company_name}} will expire in {{days_until_expiry}} days on {{end_date}}.

Contract Details:
- Contract Number: {{contract.contract_number}}
- Current Period: {{start_date}} - {{end_date}}
- Contract Value: {{contract_value}}
- Monthly Value: {{monthly_value}}

To ensure uninterrupted service for your locations, please contact us to discuss your renewal options.

You can reach us at:
- Email: sales@bmasiamusic.com
- Phone: +66 2 123 4567

Thank you for choosing BMAsia for your background music needs!

Best regards,
The BMAsia Team

---
You're receiving this email because you're listed as a contact for {{company_name}}.
Unsubscribe: {{unsubscribe_url}}
                ''',
            },
            
            # 14-day renewal reminder
            {
                'name': '14-Day Renewal Reminder (EN)',
                'template_type': 'renewal_14_days',
                'language': 'en',
                'department': 'Sales',
                'subject': 'Urgent: Your {{company_name}} subscription expires in 14 days',
                'body_html': '''
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #e74c3c;">Urgent: Subscription Expiring Soon</h2>
        
        <p>Dear {{contact_name}},</p>
        
        <p>Your subscription for <strong>{{company_name}}</strong> will expire in just <strong>{{days_until_expiry}} days</strong> on <strong>{{end_date}}</strong>.</p>
        
        <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ff9800;">
            <p style="margin: 0;"><strong>⚠️ Action Required:</strong> To avoid service interruption, please contact us immediately to renew your subscription.</p>
        </div>
        
        <p>Don't let your locations go silent! Contact us today:</p>
        <ul>
            <li>Email: sales@bmasiamusic.com</li>
            <li>Phone: +66 2 123 4567</li>
        </ul>
        
        <p>Best regards,<br>
        The BMAsia Team</p>
    </div>
</body>
</html>
                ''',
                'body_text': '''Dear {{contact_name}},

URGENT: Your subscription for {{company_name}} will expire in just {{days_until_expiry}} days on {{end_date}}.

Action Required: To avoid service interruption, please contact us immediately to renew your subscription.

Don't let your locations go silent! Contact us today:
- Email: sales@bmasiamusic.com
- Phone: +66 2 123 4567

Best regards,
The BMAsia Team
                ''',
            },
            
            # New invoice
            {
                'name': 'New Invoice (EN)',
                'template_type': 'invoice_new',
                'language': 'en',
                'department': 'Finance',
                'subject': 'Invoice {{invoice.invoice_number}} for {{company_name}}',
                'body_html': '''
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2c3e50;">Invoice {{invoice.invoice_number}}</h2>
        
        <p>Dear {{contact_name}},</p>
        
        <p>Please find attached invoice {{invoice.invoice_number}} for your subscription with BMAsia.</p>
        
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="margin-top: 0;">Invoice Details:</h3>
            <ul style="list-style: none; padding: 0;">
                <li><strong>Invoice Number:</strong> {{invoice.invoice_number}}</li>
                <li><strong>Issue Date:</strong> {{invoice.issue_date}}</li>
                <li><strong>Due Date:</strong> {{due_date}}</li>
                <li><strong>Amount:</strong> {{invoice_amount}}</li>
            </ul>
        </div>
        
        <p>Payment can be made via bank transfer to:</p>
        <ul>
            <li>Bank: Bangkok Bank</li>
            <li>Account Name: BMAsia Music Co., Ltd.</li>
            <li>Account Number: 123-4-56789-0</li>
        </ul>
        
        <p>Please reference invoice number {{invoice.invoice_number}} with your payment.</p>
        
        <p>If you have any questions about this invoice, please contact our finance team at finance@bmasiamusic.com</p>
        
        <p>Thank you for your business!</p>
        
        <p>Best regards,<br>
        BMAsia Finance Team</p>
    </div>
</body>
</html>
                ''',
                'body_text': '''Dear {{contact_name}},

Please find attached invoice {{invoice.invoice_number}} for your subscription with BMAsia.

Invoice Details:
- Invoice Number: {{invoice.invoice_number}}
- Issue Date: {{invoice.issue_date}}
- Due Date: {{due_date}}
- Amount: {{invoice_amount}}

Payment can be made via bank transfer to:
- Bank: Bangkok Bank
- Account Name: BMAsia Music Co., Ltd.
- Account Number: 123-4-56789-0

Please reference invoice number {{invoice.invoice_number}} with your payment.

If you have any questions, please contact our finance team at finance@bmasiamusic.com

Thank you for your business!

Best regards,
BMAsia Finance Team
                ''',
            },
            
            # Quarterly check-in
            {
                'name': 'Quarterly Check-in (EN)',
                'template_type': 'quarterly_checkin',
                'language': 'en',
                'department': 'Music',
                'subject': 'How is your music experience with BMAsia?',
                'body_html': '''
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2c3e50;">Quarterly Music Experience Check-in</h2>
        
        <p>Dear {{contact_name}},</p>
        
        <p>We hope everything is going well at {{company_name}}! It's been three months since our last check-in, and we wanted to reach out to see how your music experience is going.</p>
        
        <div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="margin-top: 0;">Your Current Setup:</h3>
            <ul style="list-style: none; padding: 0;">
                <li><strong>Total Zones:</strong> {{zone_count}}</li>
                <li><strong>Active Zones:</strong> {{active_zones}}</li>
            </ul>
        </div>
        
        <p>We're here to help with:</p>
        <ul>
            <li>🎵 Playlist updates and customization</li>
            <li>🎯 Genre adjustments for your target audience</li>
            <li>🕐 Time-based music scheduling</li>
            <li>🎉 Special event or seasonal playlists</li>
            <li>🔊 Volume and technical optimization</li>
        </ul>
        
        <p>Is there anything we can adjust or improve for your locations? Simply reply to this email and let us know!</p>
        
        <p>Best regards,<br>
        Your Music Design Team<br>
        BMAsia Music</p>
    </div>
</body>
</html>
                ''',
                'body_text': '''Dear {{contact_name}},

We hope everything is going well at {{company_name}}! It's been three months since our last check-in, and we wanted to reach out to see how your music experience is going.

Your Current Setup:
- Total Zones: {{zone_count}}
- Active Zones: {{active_zones}}

We're here to help with:
- Playlist updates and customization
- Genre adjustments for your target audience
- Time-based music scheduling
- Special event or seasonal playlists
- Volume and technical optimization

Is there anything we can adjust or improve for your locations? Simply reply to this email and let us know!

Best regards,
Your Music Design Team
BMAsia Music
                ''',
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for template_data in templates:
            template, created = EmailTemplate.objects.update_or_create(
                template_type=template_data['template_type'],
                language=template_data['language'],
                defaults={
                    'name': template_data['name'],
                    'subject': template_data['subject'],
                    'body_html': template_data['body_html'],
                    'body_text': template_data['body_text'],
                    'department': template_data.get('department', ''),
                    'is_active': True,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(f"Created template: {template_data['name']}")
            else:
                updated_count += 1
                self.stdout.write(f"Updated template: {template_data['name']}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\nEmail templates setup complete: "
                f"{created_count} created, {updated_count} updated"
            )
        )