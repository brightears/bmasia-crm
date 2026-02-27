import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0080_default_prospect_sequences'),
    ]

    operations = [
        # Add 'sequence' to EmailLog email_type choices
        migrations.AlterField(
            model_name='emaillog',
            name='email_type',
            field=models.CharField(
                choices=[
                    ('renewal', 'Renewal Reminder'),
                    ('invoice', 'Invoice'),
                    ('invoice_send', 'Invoice Sent'),
                    ('payment', 'Payment Reminder'),
                    ('quarterly', 'Quarterly Check-in'),
                    ('seasonal', 'Seasonal Campaign'),
                    ('support', 'Technical Support'),
                    ('manual', 'Manual Email'),
                    ('test', 'Test Email'),
                    ('quote_send', 'Quote Sent'),
                    ('quote_followup', 'Quote Follow-up'),
                    ('contract_send', 'Contract Sent'),
                    ('sequence', 'Prospect Sequence'),
                ],
                max_length=20,
            ),
        ),
        # Create ProspectReply model
        migrations.CreateModel(
            name='ProspectReply',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('imap_message_id', models.CharField(help_text='Message-ID header for dedup', max_length=500, unique=True)),
                ('from_email', models.EmailField(max_length=254)),
                ('subject', models.CharField(max_length=500)),
                ('body_text', models.TextField(blank=True)),
                ('received_at', models.DateTimeField()),
                ('classification', models.CharField(
                    choices=[
                        ('interested', 'Interested'),
                        ('not_interested', 'Not Interested'),
                        ('question', 'Question'),
                        ('objection', 'Objection'),
                        ('meeting_request', 'Meeting Request'),
                        ('out_of_office', 'Out of Office'),
                        ('unsubscribe', 'Unsubscribe Request'),
                        ('referral', 'Referral'),
                        ('bounce', 'Bounce/Error'),
                        ('other', 'Other'),
                        ('unclassified', 'Unclassified'),
                    ],
                    default='unclassified',
                    max_length=20,
                )),
                ('classification_confidence', models.FloatField(default=0.0, help_text='0.0-1.0')),
                ('classification_method', models.CharField(blank=True, help_text="'rule' or 'ai'", max_length=20)),
                ('enrollment_paused', models.BooleanField(default=False)),
                ('stage_updated', models.BooleanField(default=False)),
                ('needs_human_review', models.BooleanField(default=False)),
                ('enrollment', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='replies',
                    to='crm_app.prospectenrollment',
                )),
                ('email_log', models.ForeignKey(
                    blank=True,
                    help_text='The outbound email this replies to',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='prospect_replies',
                    to='crm_app.emaillog',
                )),
                ('task_created', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='crm_app.task',
                )),
            ],
            options={
                'verbose_name': 'Prospect Reply',
                'verbose_name_plural': 'Prospect Replies',
                'ordering': ['-received_at'],
                'indexes': [
                    models.Index(fields=['enrollment', '-received_at'], name='crm_app_pros_enrollm_reply_idx'),
                    models.Index(fields=['classification', 'needs_human_review'], name='crm_app_pros_classif_idx'),
                ],
            },
        ),
    ]
