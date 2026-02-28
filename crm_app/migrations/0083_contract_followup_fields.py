from django.db import migrations, models


def backfill_sent_date(apps, schema_editor):
    """Set sent_date for existing contracts in 'Sent' status"""
    Contract = apps.get_model('crm_app', 'Contract')
    for contract in Contract.objects.filter(status='Sent', sent_date__isnull=True):
        contract.sent_date = contract.updated_at.date() if contract.updated_at else None
        if contract.sent_date:
            contract.save(update_fields=['sent_date'])


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0082_opportunity_choice_expansion'),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='sent_date',
            field=models.DateField(blank=True, help_text='Auto-set when status changes to Sent', null=True),
        ),
        migrations.AddField(
            model_name='contract',
            name='first_followup_sent',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='contract',
            name='second_followup_sent',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='emaillog',
            name='email_type',
            field=models.CharField(
                choices=[
                    ('renewal', 'Renewal Reminder'),
                    ('invoice', 'Invoice'),
                    ('invoice_send', 'Invoice Sent'),
                    ('payment', 'Payment Reminder'),
                    ('quarterly', 'Quarterly Check-in'),
                    ('seasonal', 'Seasonal Campaign'),
                    ('support', 'Technical Support'),
                    ('manual', 'Manual Email'),
                    ('test', 'Test Email'),
                    ('quote_send', 'Quote Sent'),
                    ('quote_followup', 'Quote Follow-up'),
                    ('contract_send', 'Contract Sent'),
                    ('contract_followup', 'Contract Follow-up'),
                    ('sequence', 'Prospect Sequence'),
                ],
                max_length=20,
            ),
        ),
        migrations.RunPython(backfill_sent_date, migrations.RunPython.noop),
    ]
