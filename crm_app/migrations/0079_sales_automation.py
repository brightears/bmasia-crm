import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('crm_app', '0078_clienttechdetail_syb_account_type'),
    ]

    operations = [
        # Add stage_changed_at to Opportunity
        migrations.AddField(
            model_name='opportunity',
            name='stage_changed_at',
            field=models.DateTimeField(blank=True, help_text='Timestamp of last stage change', null=True),
        ),

        # ProspectSequence
        migrations.CreateModel(
            name='ProspectSequence',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text="Sequence name, e.g. 'New Lead Follow-up'", max_length=255)),
                ('description', models.TextField(blank=True)),
                ('trigger_type', models.CharField(choices=[('manual', 'Manual Enrollment'), ('new_opportunity', 'New Opportunity Created'), ('quote_sent', 'Quote Sent'), ('stale_deal', 'Stale Deal Re-engagement')], default='manual', max_length=20)),
                ('target_stages', models.JSONField(blank=True, default=list, help_text="Opportunity stages this sequence targets, e.g. ['Contacted', 'Quotation Sent']")),
                ('is_active', models.BooleanField(default=True)),
                ('billing_entity', models.CharField(blank=True, help_text='Filter by billing entity, blank=all', max_length=100)),
                ('max_enrollments_per_company', models.IntegerField(default=1, help_text='Max active enrollments per company')),
                ('stale_days_threshold', models.IntegerField(default=14, help_text='Days before a deal is considered stale (for stale_deal trigger)')),
            ],
            options={
                'verbose_name': 'Prospect Sequence',
                'verbose_name_plural': 'Prospect Sequences',
                'ordering': ['name'],
            },
        ),

        # ProspectSequenceStep
        migrations.CreateModel(
            name='ProspectSequenceStep',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('step_number', models.IntegerField(help_text='Order of this step in the sequence')),
                ('delay_days', models.IntegerField(default=0, help_text='Days to wait after previous step (or enrollment) before executing')),
                ('action_type', models.CharField(choices=[('email', 'Send Email'), ('ai_email', 'AI-Generated Email'), ('task', 'Create Task'), ('stage_update', 'Update Stage')], default='email', max_length=20)),
                ('email_subject_template', models.CharField(blank=True, help_text='Email subject (supports {{variable}} templates)', max_length=500)),
                ('email_body_template', models.TextField(blank=True, help_text='Email body HTML (supports {{variable}} templates)')),
                ('ai_prompt_instructions', models.TextField(blank=True, help_text='Instructions for AI: tone, focus, what to emphasize')),
                ('task_title_template', models.CharField(blank=True, help_text='Task title template', max_length=200)),
                ('task_type', models.CharField(blank=True, choices=[('Call', 'Phone Call'), ('Email', 'Email'), ('Follow-up', 'Follow-up'), ('Meeting', 'Meeting'), ('Other', 'Other')], max_length=20)),
                ('stage_to_set', models.CharField(blank=True, help_text='Stage to set on the opportunity', max_length=50)),
                ('sequence', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='steps', to='crm_app.prospectsequence')),
            ],
            options={
                'verbose_name': 'Sequence Step',
                'verbose_name_plural': 'Sequence Steps',
                'ordering': ['sequence', 'step_number'],
                'unique_together': {('sequence', 'step_number')},
            },
        ),

        # ProspectEnrollment
        migrations.CreateModel(
            name='ProspectEnrollment',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('status', models.CharField(choices=[('active', 'Active'), ('paused', 'Paused'), ('completed', 'Completed'), ('cancelled', 'Cancelled'), ('replied', 'Replied')], default='active', max_length=20)),
                ('current_step', models.IntegerField(default=0, help_text='Current step number (0 = not started)')),
                ('enrolled_at', models.DateTimeField(auto_now_add=True)),
                ('paused_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('cancelled_at', models.DateTimeField(blank=True, null=True)),
                ('pause_reason', models.CharField(blank=True, choices=[('reply_received', 'Reply Received'), ('manual', 'Manually Paused'), ('meeting_booked', 'Meeting Booked'), ('out_of_office', 'Out of Office'), ('error', 'Error Occurred')], max_length=20)),
                ('enrollment_source', models.CharField(default='manual', help_text="'manual' or 'auto_trigger'", max_length=20)),
                ('sequence', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='crm_app.prospectsequence')),
                ('opportunity', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='prospect_enrollments', to='crm_app.opportunity')),
                ('contact', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='prospect_enrollments', to='crm_app.contact')),
            ],
            options={
                'verbose_name': 'Prospect Enrollment',
                'verbose_name_plural': 'Prospect Enrollments',
                'ordering': ['-enrolled_at'],
                'indexes': [
                    models.Index(fields=['status', 'sequence'], name='crm_app_pros_status_seq_idx'),
                    models.Index(fields=['opportunity', 'status'], name='crm_app_pros_opp_status_idx'),
                    models.Index(fields=['contact', 'status'], name='crm_app_pros_contact_status_idx'),
                ],
            },
        ),

        # ProspectStepExecution
        migrations.CreateModel(
            name='ProspectStepExecution',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('scheduled_for', models.DateTimeField(help_text='When this step should be executed')),
                ('executed_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('pending_approval', 'Pending Approval'), ('sent', 'Sent'), ('skipped', 'Skipped'), ('failed', 'Failed'), ('expired', 'Expired')], default='pending', max_length=20)),
                ('ai_draft_subject', models.CharField(blank=True, max_length=500)),
                ('ai_draft_body', models.TextField(blank=True)),
                ('error_message', models.TextField(blank=True)),
                ('enrollment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='executions', to='crm_app.prospectenrollment')),
                ('step', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='executions', to='crm_app.prospectsequencestep')),
                ('email_log', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='prospect_executions', to='crm_app.emaillog')),
                ('task_created', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='prospect_executions', to='crm_app.task')),
            ],
            options={
                'verbose_name': 'Step Execution',
                'verbose_name_plural': 'Step Executions',
                'ordering': ['scheduled_for'],
                'indexes': [
                    models.Index(fields=['status', 'scheduled_for'], name='crm_app_pse_status_sched_idx'),
                    models.Index(fields=['enrollment', 'status'], name='crm_app_pse_enroll_status_idx'),
                ],
            },
        ),

        # AIEmailDraft
        migrations.CreateModel(
            name='AIEmailDraft',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('subject', models.CharField(max_length=500)),
                ('body_html', models.TextField()),
                ('status', models.CharField(choices=[('pending_review', 'Pending Review'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('edited', 'Edited & Approved'), ('expired', 'Expired')], default='pending_review', max_length=20)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(help_text='Draft expires and is skipped after this time (24h TTL)')),
                ('edited_subject', models.CharField(blank=True, help_text='Edited subject (if reviewer modified)', max_length=500)),
                ('edited_body_html', models.TextField(blank=True, help_text='Edited body (if reviewer modified)')),
                ('auto_approved', models.BooleanField(default=False, help_text='Whether this was auto-approved by graduated trust')),
                ('execution', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='ai_draft', to='crm_app.prospectstepexecution')),
                ('reviewer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_drafts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'AI Email Draft',
                'verbose_name_plural': 'AI Email Drafts',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['status', 'expires_at'], name='crm_app_aid_status_exp_idx'),
                ],
            },
        ),
    ]
