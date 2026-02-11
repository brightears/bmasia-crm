from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0061_invoice_payment_terms_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='service_period_start',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='service_period_end',
            field=models.DateField(blank=True, null=True),
        ),
    ]
