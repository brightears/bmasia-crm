"""Phase 1 Stage A: append-only AgentRequest ledger for the agent gate.

Additive only (one new table). Hand-written so unrelated model/migration drift
(index renames etc.) is not swept into this change.
"""
import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('crm_app', '0101_contract_send_receipt_use')]

    operations = [
        migrations.CreateModel(
            name='AgentRequest',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('mode', models.CharField(default='observe', max_length=10)),
                ('username', models.CharField(blank=True, max_length=150)),
                ('principal', models.CharField(blank=True, db_index=True, max_length=40)),
                ('tool', models.CharField(max_length=60)),
                ('verb', models.CharField(max_length=20)),
                ('collection', models.CharField(blank=True, max_length=50)),
                ('record_id', models.CharField(blank=True, max_length=64)),
                ('fields', models.JSONField(blank=True, default=list)),
                ('decision', models.CharField(choices=[
                    ('allow', 'Allowed by policy'),
                    ('would_deny', 'Would be refused by policy'),
                    ('uncertain', 'Verdict depends on state that could not be read'),
                    ('not_agent', 'Human / unlisted user (not gated)'),
                    ('unauthenticated', 'No authenticated caller'),
                ], db_index=True, max_length=20)),
                ('reasons', models.JSONField(blank=True, default=list)),
                ('protocol_gaps', models.JSONField(blank=True, default=list)),
                ('request_key', models.CharField(blank=True, max_length=200)),
                ('has_expected_version', models.BooleanField(default=False)),
                ('payload_sha256', models.CharField(blank=True, max_length=64)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['principal', 'decision', '-created_at'],
                                         name='crm_app_age_princip_d600d9_idx')],
            },
        ),
    ]
