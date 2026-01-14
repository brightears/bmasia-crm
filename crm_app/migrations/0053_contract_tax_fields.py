# Generated migration for contract tax fields
from django.db import migrations, models
from decimal import Decimal


def calculate_existing_totals(apps, schema_editor):
    """
    For existing contracts, set total_value = value (assuming existing values are totals).
    For THB contracts, back-calculate the base value and VAT.
    """
    Contract = apps.get_model('crm_app', 'Contract')

    for contract in Contract.objects.all():
        if contract.currency == 'THB':
            # Existing THB contracts: assume value was entered as total including VAT
            # Back-calculate: base = total / 1.07, vat = total - base
            total = contract.value
            base_value = total / Decimal('1.07')
            tax_amount = total - base_value
            contract.value = base_value.quantize(Decimal('0.01'))
            contract.tax_rate = Decimal('7.00')
            contract.tax_amount = tax_amount.quantize(Decimal('0.01'))
            contract.total_value = total
        else:
            # USD contracts: no tax
            contract.tax_rate = Decimal('0.00')
            contract.tax_amount = Decimal('0.00')
            contract.total_value = contract.value
        contract.save()


def reverse_calculation(apps, schema_editor):
    """Reverse: set value back to total_value for THB contracts."""
    Contract = apps.get_model('crm_app', 'Contract')
    for contract in Contract.objects.filter(currency='THB'):
        contract.value = contract.total_value
        contract.save()


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0052_contract_status_simplification'),
    ]

    operations = [
        # Add tax_rate field
        migrations.AddField(
            model_name='contract',
            name='tax_rate',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Tax rate percentage (e.g., 7 for 7% VAT)',
                max_digits=5,
            ),
        ),
        # Add tax_amount field
        migrations.AddField(
            model_name='contract',
            name='tax_amount',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Calculated: value × tax_rate',
                max_digits=12,
            ),
        ),
        # Add total_value field
        migrations.AddField(
            model_name='contract',
            name='total_value',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Total including tax: value + tax_amount',
                max_digits=12,
            ),
        ),
        # Update value field help text
        migrations.AlterField(
            model_name='contract',
            name='value',
            field=models.DecimalField(
                decimal_places=2,
                help_text='Base contract value (excluding VAT/tax)',
                max_digits=12,
            ),
        ),
        # Calculate totals for existing contracts
        migrations.RunPython(calculate_existing_totals, reverse_calculation),
    ]
