# Generated manually by BMAsia CRM

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0009_update_subscription_pricing'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='company',
            name='annual_revenue',
        ),
        migrations.CreateModel(
            name='Zone',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text="Zone name (e.g., 'Lobby', 'Restaurant', 'Pool Area')", max_length=100)),
                ('platform', models.CharField(choices=[('soundtrack', 'Soundtrack Your Brand'), ('beatbreeze', 'Beat Breeze')], max_length=20)),
                ('status', models.CharField(choices=[('online', 'Online'), ('offline', 'Offline'), ('no_device', 'No Device Paired'), ('expired', 'Subscription Expired'), ('pending', 'Pending Activation')], default='pending', max_length=20)),
                ('soundtrack_account_id', models.CharField(blank=True, help_text='Soundtrack account ID for API integration', max_length=100)),
                ('soundtrack_zone_id', models.CharField(blank=True, max_length=100)),
                ('soundtrack_admin_email', models.EmailField(blank=True, help_text='Admin email from Soundtrack API', max_length=254)),
                ('device_name', models.CharField(blank=True, max_length=100)),
                ('last_seen_online', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('last_api_sync', models.DateTimeField(blank=True, null=True)),
                ('api_raw_data', models.JSONField(blank=True, null=True)),
                ('subscription_plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='zones', to='crm_app.subscriptionplan')),
            ],
            options={
                'ordering': ['subscription_plan__company', 'name'],
                'indexes': [
                    models.Index(fields=['subscription_plan', 'status'], name='crm_app_zon_subscri_9876ab_idx'),
                    models.Index(fields=['platform', 'soundtrack_account_id'], name='crm_app_zon_platfor_5432cd_idx'),
                ],
            },
        ),
    ]