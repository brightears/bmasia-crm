"""
Set seasonal trigger dates for variable holidays.
Idempotent — safe to run on every deploy.
"""
from datetime import date
from django.core.management.base import BaseCommand
from crm_app.models import SeasonalTriggerDate


# 2026 variable holiday dates (update yearly)
SEASONAL_DATES_2026 = [
    {
        'holiday_type': 'auto_seasonal_cny',
        'year': 2026,
        'trigger_date': date(2026, 2, 3),
        'holiday_date': date(2026, 2, 17),
        'notes': 'Chinese New Year 2026 - Year of the Horse',
    },
    {
        'holiday_type': 'auto_seasonal_ramadan',
        'year': 2026,
        'trigger_date': date(2026, 2, 4),
        'holiday_date': date(2026, 2, 18),
        'notes': 'Ramadan 2026 - starts ~Feb 18 (subject to moon sighting)',
    },
    {
        'holiday_type': 'auto_seasonal_eid_fitr',
        'year': 2026,
        'trigger_date': date(2026, 3, 6),
        'holiday_date': date(2026, 3, 20),
        'notes': 'Eid al-Fitr 2026 - ~Mar 20 (subject to moon sighting)',
    },
    {
        'holiday_type': 'auto_seasonal_mid_autumn',
        'year': 2026,
        'trigger_date': date(2026, 9, 11),
        'holiday_date': date(2026, 9, 25),
        'notes': 'Mid-Autumn Festival 2026',
    },
    {
        'holiday_type': 'auto_seasonal_diwali',
        'year': 2026,
        'trigger_date': date(2026, 10, 25),
        'holiday_date': date(2026, 11, 8),
        'notes': 'Diwali 2026 - Festival of Lights',
    },
    {
        'holiday_type': 'auto_seasonal_loy_krathong',
        'year': 2026,
        'trigger_date': date(2026, 11, 10),
        'holiday_date': date(2026, 11, 24),
        'notes': 'Loy Krathong 2026 - Full moon, 12th Thai lunar month',
    },
]


class Command(BaseCommand):
    help = 'Set seasonal trigger dates for variable holidays (idempotent)'

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for entry in SEASONAL_DATES_2026:
            obj, created = SeasonalTriggerDate.objects.update_or_create(
                holiday_type=entry['holiday_type'],
                year=entry['year'],
                defaults={
                    'trigger_date': entry['trigger_date'],
                    'holiday_date': entry['holiday_date'],
                    'notes': entry['notes'],
                },
            )
            if created:
                created_count += 1
                self.stdout.write(f"  Created: {obj.get_holiday_type_display()} {obj.year} (trigger: {obj.trigger_date})")
            else:
                updated_count += 1
                self.stdout.write(f"  Exists: {obj.get_holiday_type_display()} {obj.year} (trigger: {obj.trigger_date})")

        self.stdout.write(self.style.SUCCESS(
            f'Seasonal dates: {created_count} created, {updated_count} already existed'
        ))
