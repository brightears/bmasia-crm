from django.db import migrations, models


class Migration(migrations.Migration):
    """Add 'one-time' to Quote.billing_frequency choices so one-off hardware/setup quotes can be
    marked one-time and the quote PDF stops annualising them under 'Total (per year)'
    (INC-20260622-af80a5). Choices are not stored in the DB for a CharField, so this AlterField is
    a no-op at the schema level — it exists only to keep Django's migration state in sync."""

    dependencies = [
        ('crm_app', '0095_alter_contract_property_name_default'),
    ]

    operations = [
        migrations.AlterField(
            model_name='quote',
            name='billing_frequency',
            field=models.CharField(
                choices=[
                    ('annual', 'Annual'),
                    ('upfront', 'Upfront (full term)'),
                    ('biannual', 'Bi-annual'),
                    ('quarterly', 'Quarterly'),
                    ('monthly', 'Monthly'),
                    ('one-time', 'One-time'),
                ],
                default='annual',
                help_text='How the subscription is billed across the contract term (shown on the quote PDF).',
                max_length=20,
            ),
        ),
    ]
