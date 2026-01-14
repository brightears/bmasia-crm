# Generated migration for contract status simplification
from django.db import migrations, models
import django.db.models.deletion


def convert_old_statuses(apps, schema_editor):
    """Convert old contract statuses to new simplified ones."""
    Contract = apps.get_model('crm_app', 'Contract')

    # Map old statuses to new ones
    status_mapping = {
        'Draft': 'Active',
        'Sent': 'Active',
        'Signed': 'Active',
        'Terminated': 'Cancelled',
    }

    for old_status, new_status in status_mapping.items():
        Contract.objects.filter(status=old_status).update(status=new_status)


def reverse_status_conversion(apps, schema_editor):
    """Reverse is a no-op - we can't know what the original status was."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0051_balance_sheet_module'),
    ]

    operations = [
        # Add renewed_from field
        migrations.AddField(
            model_name='contract',
            name='renewed_from',
            field=models.ForeignKey(
                blank=True,
                help_text='Previous contract this was renewed from',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='renewals',
                to='crm_app.contract',
            ),
        ),
        # Convert old statuses to new ones
        migrations.RunPython(convert_old_statuses, reverse_status_conversion),
        # Update status field choices and default
        migrations.AlterField(
            model_name='contract',
            name='status',
            field=models.CharField(
                choices=[
                    ('Active', 'Active'),
                    ('Renewed', 'Renewed'),
                    ('Expired', 'Expired'),
                    ('Cancelled', 'Cancelled'),
                ],
                default='Active',
                max_length=20,
            ),
        ),
    ]
