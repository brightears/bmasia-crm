import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0071_contract_service_location'),
    ]

    operations = [
        migrations.AddField(
            model_name='emaillog',
            name='quote',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='email_logs',
                to='crm_app.quote',
            ),
        ),
        migrations.AddField(
            model_name='emaillog',
            name='tracking_token',
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=64,
                null=True,
                unique=True,
            ),
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
                ],
                max_length=20,
            ),
        ),
    ]
