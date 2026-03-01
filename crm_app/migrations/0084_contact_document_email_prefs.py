from django.db import migrations, models


def set_defaults_by_contact_type(apps, schema_editor):
    """Set document email preferences based on contact_type."""
    Contact = apps.get_model('crm_app', 'Contact')

    # Billing: invoices only
    Contact.objects.filter(contact_type='Billing').update(
        receives_quote_emails=False,
        receives_contract_emails=False,
        receives_invoice_emails=True,
    )

    # Decision Maker: quotes + contracts, not invoices
    Contact.objects.filter(contact_type='Decision Maker').update(
        receives_quote_emails=True,
        receives_contract_emails=True,
        receives_invoice_emails=False,
    )

    # Technical: none
    Contact.objects.filter(contact_type='Technical').update(
        receives_quote_emails=False,
        receives_contract_emails=False,
        receives_invoice_emails=False,
    )

    # Primary and Other: keep defaults (all True) — no update needed


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0083_contract_followup_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='contact',
            name='receives_quote_emails',
            field=models.BooleanField(default=True, help_text='Pre-selected when sending quotes'),
        ),
        migrations.AddField(
            model_name='contact',
            name='receives_contract_emails',
            field=models.BooleanField(default=True, help_text='Pre-selected when sending contracts'),
        ),
        migrations.AddField(
            model_name='contact',
            name='receives_invoice_emails',
            field=models.BooleanField(default=True, help_text='Pre-selected when sending invoices'),
        ),
        migrations.RunPython(set_defaults_by_contact_type, migrations.RunPython.noop),
    ]
