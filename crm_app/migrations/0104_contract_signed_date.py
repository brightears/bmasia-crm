"""Contract.signed_date: nullable signature date. Additive only, no backfill."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('crm_app', '0103_quote_send_receipt_use')]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='signed_date',
            field=models.DateField(
                blank=True, null=True,
                help_text='Date the customer signed this contract. Recorded only from evidence; never inferred.',
            ),
        ),
    ]
