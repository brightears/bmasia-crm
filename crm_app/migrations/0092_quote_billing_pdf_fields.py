from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0091_documentsequence'),
    ]

    operations = [
        migrations.AddField(
            model_name='quote',
            name='billing_frequency',
            field=models.CharField(
                choices=[
                    ('annual', 'Annual'),
                    ('upfront', 'Upfront (full term)'),
                    ('biannual', 'Bi-annual'),
                    ('quarterly', 'Quarterly'),
                    ('monthly', 'Monthly'),
                ],
                default='annual',
                help_text='How the subscription is billed across the contract term (shown on the quote PDF).',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='quote',
            name='payment_schedule',
            field=models.CharField(
                blank=True,
                help_text='Explicit payment-schedule line for the quote PDF. If blank, it is derived from billing frequency + contract term.',
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name='quotelineitem',
            name='unit_value',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='List/retail value per unit. Shown for complimentary (zero-price) items to anchor the saving. Leave blank for normally priced items.',
                max_digits=12,
                null=True,
            ),
        ),
    ]
