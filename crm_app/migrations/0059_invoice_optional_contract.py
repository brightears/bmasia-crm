"""
Invoice: Add direct company FK, make contract optional.

Existing invoices get company backfilled from contract.company.
"""
from django.db import migrations, models
import django.db.models.deletion


def backfill_company(apps, schema_editor):
    """Populate company from contract.company for all existing invoices."""
    Invoice = apps.get_model('crm_app', 'Invoice')
    for invoice in Invoice.objects.select_related('contract__company').all():
        if invoice.contract_id:
            invoice.company_id = invoice.contract.company_id
            invoice.save(update_fields=['company_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0058_task_improvements'),
    ]

    operations = [
        # Step 1: Add nullable company FK
        migrations.AddField(
            model_name='invoice',
            name='company',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='invoices',
                to='crm_app.company',
            ),
        ),
        # Step 2: Backfill company from contract.company
        migrations.RunPython(backfill_company, migrations.RunPython.noop),
        # Step 3: Make company non-nullable
        migrations.AlterField(
            model_name='invoice',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='invoices',
                to='crm_app.company',
            ),
        ),
        # Step 4: Make contract nullable
        migrations.AlterField(
            model_name='invoice',
            name='contract',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='invoices',
                to='crm_app.contract',
            ),
        ),
    ]
