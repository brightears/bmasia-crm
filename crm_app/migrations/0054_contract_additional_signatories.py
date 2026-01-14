# Generated migration for additional customer signatories
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0053_contract_tax_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='additional_customer_signatories',
            field=models.JSONField(
                default=list,
                blank=True,
                help_text='Additional customer signatories: [{"name": "...", "title": "..."}]'
            ),
        ),
    ]
