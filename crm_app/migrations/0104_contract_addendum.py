"""Contract addenda (CRM-007): one-page changes linked to their contract.

Additive only (one new table). Hand-written so unrelated model/migration drift
is not swept into this change.
"""
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('crm_app', '0103_quote_send_receipt_use'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ContractAddendum',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('sequence', models.PositiveIntegerField()),
                ('addendum_number', models.CharField(max_length=60, unique=True)),
                ('status', models.CharField(
                    choices=[('Draft', 'Draft'), ('Sent', 'Sent'), ('Signed', 'Signed'), ('Cancelled', 'Cancelled')],
                    default='Draft', max_length=20,
                )),
                ('effective_date', models.DateField(help_text='Date the changes take effect')),
                ('changes', models.JSONField(
                    default=list, help_text='Validated change items; see crm_app/services/contract_addenda.py',
                )),
                ('customer_signatory_name', models.CharField(
                    blank=True, help_text="Blank uses the contract's signatory", max_length=255,
                )),
                ('customer_signatory_title', models.CharField(blank=True, max_length=255)),
                ('bmasia_signatory_name', models.CharField(blank=True, max_length=255)),
                ('bmasia_signatory_title', models.CharField(blank=True, max_length=255)),
                ('notes', models.TextField(blank=True, help_text='Internal only; never printed')),
                ('sent_date', models.DateField(blank=True, null=True)),
                ('signed_date', models.DateField(blank=True, null=True)),
                ('applied_at', models.DateTimeField(blank=True, null=True)),
                ('applied_snapshot', models.JSONField(blank=True, null=True)),
                ('contract', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='addenda', to='crm_app.contract',
                )),
                ('created_by', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_contract_addenda', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['contract', 'sequence']},
        ),
        migrations.AddConstraint(
            model_name='contractaddendum',
            constraint=models.UniqueConstraint(fields=('contract', 'sequence'), name='uniq_contract_addendum_sequence'),
        ),
    ]
