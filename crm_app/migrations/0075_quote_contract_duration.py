from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0074_clienttechdetail_os_pcname'),
    ]

    operations = [
        migrations.AddField(
            model_name='quote',
            name='contract_duration_months',
            field=models.PositiveIntegerField(
                default=12,
                help_text='Proposed contract duration in months (e.g., 6, 12, 24, 36)',
            ),
        ),
    ]
