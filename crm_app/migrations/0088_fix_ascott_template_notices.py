"""Fix Ascott contract template: replace {{venue_names}} with {{company_name}} in Notices clause.

Nikki reported clause 20.2 "Notices" shows zone name ("Lobby and Corridor")
instead of hotel/company name. The template used {{venue_names}} where
{{company_name}} should be.
"""

from django.db import migrations


def fix_ascott_templates(apps, schema_editor):
    ContractTemplate = apps.get_model('crm_app', 'ContractTemplate')

    for template in ContractTemplate.objects.filter(name__icontains='ascott'):
        content = template.content
        changed = False

        # Replace {{venue_names}} with {{company_name}} in templates that have Notices
        if '{{venue_names}}' in content and 'Notices' in content:
            content = content.replace('{{venue_names}}', '{{company_name}}')
            changed = True

        # Also fix any hardcoded "Lobby and Corridor" text (fallback)
        if 'Lobby and Corridor' in content:
            content = content.replace('Lobby and Corridor', '{{company_name}}')
            changed = True

        if changed:
            template.content = content
            template.save()


def reverse_fix(apps, schema_editor):
    # Cannot reliably reverse a content fix — no-op
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0087_sequenceenrollment_trigger_entity_id_to_charfield'),
    ]

    operations = [
        migrations.RunPython(fix_ascott_templates, reverse_fix),
    ]
