# Generated by Django 5.2.2 on 2025-06-14 03:04

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0011_simplify_zone_tracking'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailCampaign',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('campaign_type', models.CharField(choices=[('renewal_sequence', 'Renewal Reminder Sequence'), ('payment_sequence', 'Payment Reminder Sequence'), ('seasonal', 'Seasonal Campaign'), ('quarterly', 'Quarterly Check-in'), ('custom', 'Custom Campaign')], max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField(blank=True, null=True)),
                ('emails_sent', models.IntegerField(default=0)),
                ('last_email_sent', models.DateTimeField(blank=True, null=True)),
                ('stop_on_reply', models.BooleanField(default=True)),
                ('replied', models.BooleanField(default=False)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='EmailLog',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('email_type', models.CharField(choices=[('renewal', 'Renewal Reminder'), ('invoice', 'Invoice'), ('payment', 'Payment Reminder'), ('quarterly', 'Quarterly Check-in'), ('seasonal', 'Seasonal Campaign'), ('support', 'Technical Support'), ('manual', 'Manual Email')], max_length=20)),
                ('from_email', models.EmailField(max_length=254)),
                ('to_email', models.EmailField(max_length=254)),
                ('cc_emails', models.TextField(blank=True, help_text='Comma-separated CC emails')),
                ('subject', models.CharField(max_length=200)),
                ('body_html', models.TextField()),
                ('body_text', models.TextField()),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed'), ('bounced', 'Bounced'), ('opened', 'Opened'), ('clicked', 'Clicked'), ('unsubscribed', 'Unsubscribed')], default='pending', max_length=20)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('opened_at', models.DateTimeField(blank=True, null=True)),
                ('clicked_at', models.DateTimeField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True)),
                ('message_id', models.CharField(blank=True, help_text='Email message ID for tracking', max_length=255)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='EmailTemplate',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('template_type', models.CharField(choices=[('renewal_30_days', '30-Day Renewal Reminder'), ('renewal_14_days', '14-Day Renewal Reminder'), ('renewal_7_days', '7-Day Renewal Reminder'), ('renewal_urgent', 'Urgent Renewal Notice'), ('invoice_new', 'New Invoice'), ('payment_reminder_7_days', '7-Day Payment Reminder'), ('payment_reminder_14_days', '14-Day Payment Reminder'), ('payment_overdue', 'Payment Overdue Notice'), ('quarterly_checkin', 'Quarterly Check-in'), ('seasonal_christmas', 'Christmas Season Preparation'), ('seasonal_newyear', 'Chinese New Year Preparation'), ('seasonal_songkran', 'Songkran Preparation'), ('seasonal_ramadan', 'Ramadan Preparation'), ('zone_offline_48h', 'Zone Offline 48 Hours'), ('zone_offline_7d', 'Zone Offline 7 Days'), ('welcome', 'Welcome Email'), ('contract_signed', 'Contract Signed Confirmation')], max_length=50, unique=True)),
                ('language', models.CharField(choices=[('en', 'English'), ('th', 'Thai')], default='en', max_length=2)),
                ('subject', models.CharField(max_length=200)),
                ('body_html', models.TextField(help_text='HTML email body. Use variables like {{company_name}}, {{contact_name}}, {{days_until_expiry}}')),
                ('body_text', models.TextField(help_text='Plain text email body for non-HTML clients')),
                ('is_active', models.BooleanField(default=True)),
                ('department', models.CharField(blank=True, choices=[('Sales', 'Sales'), ('Finance', 'Finance'), ('Tech', 'Tech Support'), ('Music', 'Music Design'), ('Admin', 'Admin')], max_length=20)),
                ('notes', models.TextField(blank=True, help_text='Internal notes about when to use this template')),
            ],
            options={
                'ordering': ['template_type', 'language'],
            },
        ),
        migrations.AlterModelOptions(
            name='zone',
            options={'ordering': ['company', 'name']},
        ),
        migrations.RenameIndex(
            model_name='subscriptionplan',
            new_name='crm_app_sub_company_0c5602_idx',
            old_name='crm_app_sub_company_1234ab_idx',
        ),
        migrations.RenameIndex(
            model_name='subscriptionplan',
            new_name='crm_app_sub_tier_803553_idx',
            old_name='crm_app_sub_tier_5678cd_idx',
        ),
        migrations.RenameIndex(
            model_name='zone',
            new_name='crm_app_zon_company_de8665_idx',
            old_name='crm_app_zon_company_1234ab_idx',
        ),
        migrations.RenameIndex(
            model_name='zone',
            new_name='crm_app_zon_platfor_5191f7_idx',
            old_name='crm_app_zon_platfor_5678cd_idx',
        ),
        migrations.AddField(
            model_name='contact',
            name='notification_types',
            field=models.JSONField(blank=True, default=list, help_text='List of notification types this contact should receive'),
        ),
        migrations.AddField(
            model_name='contact',
            name='preferred_language',
            field=models.CharField(choices=[('en', 'English'), ('th', 'Thai')], default='en', max_length=2),
        ),
        migrations.AddField(
            model_name='contact',
            name='receives_notifications',
            field=models.BooleanField(default=True, help_text='Whether this contact receives automated emails'),
        ),
        migrations.AddField(
            model_name='contact',
            name='unsubscribe_token',
            field=models.CharField(blank=True, help_text='Token for unsubscribe links', max_length=64),
        ),
        migrations.AddField(
            model_name='contact',
            name='unsubscribed',
            field=models.BooleanField(default=False, help_text='Has unsubscribed from all emails'),
        ),
        migrations.AlterField(
            model_name='company',
            name='country',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='contract',
            name='currency',
            field=models.CharField(choices=[('USD', 'USD - US Dollar'), ('THB', 'THB - Thai Baht')], default='USD', max_length=3),
        ),
        migrations.AlterField(
            model_name='invoice',
            name='currency',
            field=models.CharField(choices=[('USD', 'USD - US Dollar'), ('THB', 'THB - Thai Baht')], default='USD', max_length=3),
        ),
        migrations.AlterField(
            model_name='subscriptionplan',
            name='price_per_zone',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='subscriptionplan',
            name='zone_count',
            field=models.IntegerField(default=1),
        ),
        migrations.AlterField(
            model_name='zone',
            name='name',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='zone',
            name='soundtrack_zone_id',
            field=models.CharField(blank=True, help_text='Zone ID from Soundtrack API', max_length=100),
        ),
        migrations.AddField(
            model_name='emailcampaign',
            name='company',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_campaigns', to='crm_app.company'),
        ),
        migrations.AddField(
            model_name='emailcampaign',
            name='contract',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='email_campaigns', to='crm_app.contract'),
        ),
        migrations.AddField(
            model_name='emaillog',
            name='company',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_logs', to='crm_app.company'),
        ),
        migrations.AddField(
            model_name='emaillog',
            name='contact',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='email_logs', to='crm_app.contact'),
        ),
        migrations.AddField(
            model_name='emaillog',
            name='contract',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='email_logs', to='crm_app.contract'),
        ),
        migrations.AddField(
            model_name='emaillog',
            name='in_reply_to',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='replies', to='crm_app.emaillog'),
        ),
        migrations.AddField(
            model_name='emaillog',
            name='invoice',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='email_logs', to='crm_app.invoice'),
        ),
        migrations.AddIndex(
            model_name='emailtemplate',
            index=models.Index(fields=['template_type', 'language', 'is_active'], name='crm_app_ema_templat_8f39ef_idx'),
        ),
        migrations.AddField(
            model_name='emaillog',
            name='template_used',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='crm_app.emailtemplate'),
        ),
        migrations.AddIndex(
            model_name='emailcampaign',
            index=models.Index(fields=['company', 'is_active'], name='crm_app_ema_company_c5ff78_idx'),
        ),
        migrations.AddIndex(
            model_name='emailcampaign',
            index=models.Index(fields=['campaign_type', 'is_active'], name='crm_app_ema_campaig_7e3b89_idx'),
        ),
        migrations.AddIndex(
            model_name='emaillog',
            index=models.Index(fields=['company', 'status', '-created_at'], name='crm_app_ema_company_e914b9_idx'),
        ),
        migrations.AddIndex(
            model_name='emaillog',
            index=models.Index(fields=['email_type', 'status'], name='crm_app_ema_email_t_24da76_idx'),
        ),
        migrations.AddIndex(
            model_name='emaillog',
            index=models.Index(fields=['contact', '-created_at'], name='crm_app_ema_contact_f0eabd_idx'),
        ),
    ]
