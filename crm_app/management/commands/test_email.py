"""
Management command to test email configuration
"""

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
import datetime


class Command(BaseCommand):
    help = 'Test email configuration by sending a test email'

    def add_arguments(self, parser):
        parser.add_argument(
            '--to',
            type=str,
            default='norbert@bmasiamusic.com',
            help='Email address to send test email to'
        )

    def handle(self, *args, **options):
        to_email = options['to']
        
        self.stdout.write('Testing email configuration...')
        self.stdout.write(f'From: {settings.DEFAULT_FROM_EMAIL}')
        self.stdout.write(f'To: {to_email}')
        self.stdout.write(f'SMTP Server: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}')
        
        try:
            # Send test email
            subject = f'BMAsia CRM Email Test - {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}'
            message = '''
Hello!

This is a test email from your BMAsia CRM system.

If you're receiving this, it means your email configuration is working correctly! 🎉

Email System Details:
- SMTP Server: Gmail
- From Address: {}
- Email System: Ready for automated reminders

You can now:
✅ Send renewal reminders automatically
✅ Send payment reminders for overdue invoices
✅ Send quarterly check-ins to customers
✅ Track all email communications in the CRM

Best regards,
BMAsia CRM Email System
            '''.format(settings.DEFAULT_FROM_EMAIL)
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                fail_silently=False
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ SUCCESS! Test email sent to {to_email}\n'
                    f'Check your inbox (and spam folder) for the test email.'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'\n❌ FAILED to send email!\n'
                    f'Error: {str(e)}\n\n'
                    f'Common issues:\n'
                    f'1. EMAIL_HOST_USER not set in environment\n'
                    f'2. EMAIL_HOST_PASSWORD not set or incorrect\n'
                    f'3. Gmail App Password not properly configured\n'
                    f'4. 2-Step Verification not enabled on Gmail account'
                )
            )