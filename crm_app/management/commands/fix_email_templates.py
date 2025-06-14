"""
Fix email template department field issue
"""

from django.core.management.base import BaseCommand
from crm_app.models import EmailTemplate


class Command(BaseCommand):
    help = 'Fix department field in email templates'

    def handle(self, *args, **options):
        self.stdout.write('Fixing email template departments...')
        
        # Map template types to valid departments
        department_mapping = {
            'renewal_30_days': 'Sales',
            'renewal_14_days': 'Sales',
            'renewal_7_days': 'Sales',
            'renewal_urgent': 'Sales',
            'invoice_new': 'Finance',
            'payment_reminder_7_days': 'Finance',
            'payment_reminder_14_days': 'Finance',
            'payment_overdue': 'Finance',
            'quarterly_checkin': 'Music',
            'seasonal_christmas': 'Music',
            'seasonal_newyear': 'Music',
            'seasonal_songkran': 'Music',
            'seasonal_ramadan': 'Music',
            'zone_offline_48h': 'Tech',
            'zone_offline_7d': 'Tech',
        }
        
        templates = EmailTemplate.objects.all()
        fixed_count = 0
        
        for template in templates:
            correct_dept = department_mapping.get(template.template_type, '')
            if template.department != correct_dept:
                self.stdout.write(f"Fixing {template.name}: '{template.department}' -> '{correct_dept}'")
                template.department = correct_dept
                template.save()
                fixed_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'\nFixed {fixed_count} templates'))
        
        # Show current templates
        self.stdout.write('\nCurrent templates:')
        for template in EmailTemplate.objects.all():
            self.stdout.write(f"- {template.name} ({template.department})")