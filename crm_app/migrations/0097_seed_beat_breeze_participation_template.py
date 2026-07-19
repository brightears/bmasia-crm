from django.db import migrations


BB_PARTICIPATION_TEMPLATE = {
    'name': 'Beat Breeze Participation Agreement',
    'template_type': 'preamble',
    'pdf_format': 'participation',
    'content': '''Beat Breeze Participation Agreement

This template selects the Participation Agreement PDF format for Beat Breeze service locations.
The participation PDF generator renders the current venue, master agreement, service locations,
commercial terms, and signature blocks from the contract record.''',
    'is_default': False,
    'is_active': True,
    'version': '2026.1',
}


def create_bb_participation_template(apps, schema_editor):
    ContractTemplate = apps.get_model('crm_app', 'ContractTemplate')
    ContractTemplate.objects.get_or_create(
        name=BB_PARTICIPATION_TEMPLATE['name'],
        defaults=BB_PARTICIPATION_TEMPLATE,
    )


def reverse_bb_participation_template(apps, schema_editor):
    ContractTemplate = apps.get_model('crm_app', 'ContractTemplate')
    ContractTemplate.objects.filter(
        name=BB_PARTICIPATION_TEMPLATE['name'],
        version=BB_PARTICIPATION_TEMPLATE['version'],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0096_quote_billing_frequency_onetime'),
    ]

    operations = [
        migrations.RunPython(
            create_bb_participation_template,
            reverse_bb_participation_template,
        ),
    ]
