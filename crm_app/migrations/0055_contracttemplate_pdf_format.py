# Generated migration for adding pdf_format to ContractTemplate
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0054_contract_additional_signatories'),
    ]

    operations = [
        migrations.AddField(
            model_name='contracttemplate',
            name='pdf_format',
            field=models.CharField(
                choices=[
                    ('standard', 'Standard Contract'),
                    ('corporate_master', 'Corporate Master Agreement'),
                    ('participation', 'Participation Agreement'),
                ],
                default='standard',
                help_text='Which PDF structure to use when generating contracts',
                max_length=20,
            ),
        ),
        # Also add default to template_type since we added it to the model
        migrations.AlterField(
            model_name='contracttemplate',
            name='template_type',
            field=models.CharField(
                choices=[
                    ('preamble', 'Preamble/Introduction'),
                    ('service_standard', 'Service Package - Standard'),
                    ('service_managed', 'Service Package - Managed'),
                    ('service_custom', 'Service Package - Custom'),
                    ('payment_thailand', 'Payment Terms - Thailand'),
                    ('payment_international', 'Payment Terms - International'),
                    ('activation', 'Activation Terms'),
                ],
                default='preamble',
                max_length=30,
            ),
        ),
        # Update ordering on ContractTemplate Meta
        migrations.AlterModelOptions(
            name='contracttemplate',
            options={
                'ordering': ['name'],
                'verbose_name': 'Contract Template',
                'verbose_name_plural': 'Contract Templates',
            },
        ),
    ]
