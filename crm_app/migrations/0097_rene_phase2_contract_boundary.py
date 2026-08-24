import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0096_quote_billing_frequency_onetime'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contract',
            name='end_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='ReneRenewalPolicy',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('scope_key', models.CharField(default='global', max_length=64, unique=True)),
                ('review_status', models.CharField(choices=[('pending', 'Pending'), ('reviewed', 'Reviewed')], default='pending', max_length=16)),
                ('start_policy_id', models.CharField(max_length=128)),
                ('start_rule', models.CharField(choices=[('SAME_DAY', 'Same day'), ('NEXT_DAY', 'Next day')], max_length=32)),
                ('start_evidence_sha256', models.CharField(max_length=64)),
                ('start_source_ref', models.CharField(max_length=256)),
                ('start_source_label', models.CharField(max_length=160)),
                ('start_revision', models.PositiveIntegerField(default=1)),
                ('end_policy_id', models.CharField(max_length=128)),
                ('end_rule', models.CharField(choices=[('INCLUSIVE_MINUS_ONE', 'Anniversary minus one day'), ('ANNIVERSARY_DAY', 'Anniversary day')], max_length=32)),
                ('end_evidence_sha256', models.CharField(max_length=64)),
                ('end_source_ref', models.CharField(max_length=256)),
                ('end_source_label', models.CharField(max_length=160)),
                ('end_revision', models.PositiveIntegerField(default=1)),
                ('contract_number_policy_id', models.CharField(max_length=128)),
                ('contract_number_rule', models.CharField(choices=[('RESERVE_UNUSED_DOCUMENT_SEQUENCE_BEFORE_PDF', 'Reserve the next unused DocumentSequence number before PDF review')], max_length=64)),
                ('contract_number_evidence_sha256', models.CharField(max_length=64)),
                ('contract_number_source_ref', models.CharField(max_length=256)),
                ('contract_number_source_label', models.CharField(max_length=160)),
                ('contract_number_revision', models.PositiveIntegerField(default=1)),
                ('post_send_state_semantics_reviewed', models.BooleanField(default=False)),
                ('post_send_policy_id', models.CharField(blank=True, max_length=128)),
                ('post_send_rule', models.CharField(blank=True, choices=[('PREPARED_TO_SENT_SOURCE_UNCHANGED', 'Move only the prepared draft to Sent; leave the source unchanged')], max_length=64)),
                ('post_send_evidence_sha256', models.CharField(blank=True, max_length=64)),
                ('post_send_source_ref', models.CharField(blank=True, max_length=256)),
                ('post_send_source_label', models.CharField(blank=True, max_length=160)),
                ('post_send_revision', models.PositiveIntegerField(default=1)),
            ],
            options={
                'verbose_name': 'Rene renewal policy',
                'verbose_name_plural': 'Rene renewal policies',
            },
        ),
        migrations.CreateModel(
            name='RenePreparedContract',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('state', models.CharField(choices=[('ready_for_review', 'Ready for review'), ('Sent', 'Sent')], max_length=32)),
                ('prepare_request_id', models.CharField(max_length=256, unique=True)),
                ('prepare_request_key', models.CharField(max_length=512, unique=True)),
                ('prepare_intent_sha256', models.CharField(max_length=64)),
                ('source_inspection_sha256', models.CharField(max_length=64)),
                ('source_contract_version', models.CharField(max_length=128)),
                ('source_contract_updated_at', models.DateTimeField()),
                ('source_contract_status', models.CharField(max_length=20)),
                ('terms_sha256', models.CharField(max_length=64)),
                ('sheet_evidence', models.JSONField()),
                ('pdf_filename', models.CharField(max_length=128)),
                ('pdf_sha256', models.CharField(max_length=64)),
                ('pdf_content', models.BinaryField()),
                ('contract_number_policy_id', models.CharField(max_length=128)),
                ('contract_number_policy_rule', models.CharField(max_length=64)),
                ('contract_number_policy_evidence_sha256', models.CharField(max_length=64)),
                ('contract_number_policy_source_ref', models.CharField(max_length=256)),
                ('contract_number_policy_source_label', models.CharField(max_length=160)),
                ('contract_number_policy_revision', models.PositiveIntegerField()),
                ('gmail_sent_evidence_sha256', models.CharField(blank=True, max_length=64, null=True, unique=True)),
                ('post_send_policy_id', models.CharField(blank=True, max_length=128)),
                ('post_send_policy_rule', models.CharField(blank=True, max_length=64)),
                ('post_send_policy_evidence_sha256', models.CharField(blank=True, max_length=64)),
                ('post_send_policy_source_ref', models.CharField(blank=True, max_length=256)),
                ('post_send_policy_source_label', models.CharField(blank=True, max_length=160)),
                ('post_send_policy_revision', models.PositiveIntegerField(blank=True, null=True)),
                ('contract', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='rene_preparation', to='crm_app.contract')),
                ('source_contract', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='rene_prepared_renewals', to='crm_app.contract')),
            ],
        ),
        migrations.CreateModel(
            name='ReneCiraRequest',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('request_id', models.CharField(max_length=256, unique=True)),
                ('request_key', models.CharField(max_length=512, unique=True)),
                ('intent_sha256', models.CharField(max_length=64)),
                ('operation', models.CharField(max_length=64)),
                ('envelope', models.JSONField()),
                ('canonical_envelope_sha256', models.CharField(max_length=64)),
                ('state', models.CharField(choices=[('accepted', 'Accepted'), ('succeeded', 'Succeeded'), ('failed', 'Failed')], default='accepted', max_length=16)),
                ('receipt', models.JSONField(blank=True, null=True)),
                ('failure_code', models.CharField(blank=True, max_length=64)),
                ('target_request_key', models.CharField(blank=True, db_index=True, max_length=512)),
                ('target_intent_sha256', models.CharField(blank=True, max_length=64)),
            ],
        ),
        migrations.AddIndex(
            model_name='renepreparedcontract',
            index=models.Index(fields=['state', 'source_contract'], name='crm_app_ren_state_20ac95_idx'),
        ),
        migrations.AddIndex(
            model_name='renepreparedcontract',
            index=models.Index(fields=['prepare_intent_sha256'], name='crm_app_ren_prepare_a9eb42_idx'),
        ),
        migrations.AddIndex(
            model_name='renecirarequest',
            index=models.Index(fields=['operation', 'state'], name='crm_app_ren_operati_30e75e_idx'),
        ),
        migrations.AddIndex(
            model_name='renecirarequest',
            index=models.Index(fields=['target_request_key', 'target_intent_sha256'], name='crm_app_ren_target__db247f_idx'),
        ),
    ]
