from django.db import migrations, models


def mark_existing_charged_player_contracts(apps, schema_editor):
    Contract = apps.get_model('crm_app', 'Contract')
    ContractLineItem = apps.get_model('crm_app', 'ContractLineItem')
    contract_ids = ContractLineItem.objects.filter(
        contract__service_type='beat_breeze_yearly',
        product_service__icontains='player box',
        quantity__gt=0,
        unit_price__gt=0,
        discount_percentage__lt=100,
    ).values_list('contract_id', flat=True)
    Contract.objects.filter(pk__in=contract_ids).update(
        service_type='beat_breeze_yearly_with_players',
    )


class Migration(migrations.Migration):
    dependencies = [('crm_app', '0099_merge_commercial_issuer_and_rene')]

    operations = [
        migrations.AlterField(
            model_name='contract',
            name='service_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('soundtrack_essential_monthly', 'Soundtrack Essential (Monthly)'),
                    ('soundtrack_essential_yearly', 'Soundtrack Essential (Yearly)'),
                    ('soundtrack_unlimited_monthly', 'Soundtrack Unlimited (Monthly)'),
                    ('soundtrack_unlimited_yearly', 'Soundtrack Unlimited (Yearly)'),
                    ('soundtrack_enterprise', 'Soundtrack Enterprise (Custom)'),
                    ('beat_breeze_monthly', 'Beat Breeze (Monthly)'),
                    ('beat_breeze_yearly', 'Beat Breeze (Yearly — no player boxes)'),
                    ('beat_breeze_yearly_with_players', 'Beat Breeze (Yearly — charged player boxes)'),
                    ('custom_package', 'Custom Package'),
                    ('one_time_setup', 'One-time Setup'),
                    ('consulting', 'Consulting Services'),
                    ('maintenance', 'Maintenance & Support'),
                ],
                help_text='Specific service or plan',
                max_length=50,
            ),
        ),
        migrations.RunPython(mark_existing_charged_player_contracts, migrations.RunPython.noop),
    ]
