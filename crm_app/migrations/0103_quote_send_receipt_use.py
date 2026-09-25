"""Guarded quote Sent bookkeeping: single-use ledger for signed quote-send receipts.

Additive only (one new table). Hand-written so unrelated model/migration drift
is not swept into this change.
"""
import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('crm_app', '0102_agent_request')]

    operations = [
        migrations.CreateModel(
            name='QuoteSendReceiptUse',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('request_key', models.CharField(max_length=256, unique=True)),
                ('nonce', models.UUIDField(unique=True)),
                ('receipt_sha256', models.CharField(max_length=64, unique=True)),
                ('key_id', models.CharField(max_length=64)),
                ('quote_number', models.CharField(max_length=50)),
                ('mailbox', models.CharField(max_length=254)),
                ('sent_date', models.DateField()),
                ('before_version', models.CharField(max_length=128)),
                ('after_version', models.CharField(max_length=128)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('quote', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='send_receipt_uses', to='crm_app.quote',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
