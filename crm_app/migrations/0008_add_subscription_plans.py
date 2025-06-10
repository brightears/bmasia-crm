# Generated manually by BMAsia CRM

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0007_reorganize_company_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='SubscriptionPlan',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('tier', models.CharField(choices=[('Soundtrack Essential (Serviced)', 'Soundtrack Essential (Serviced)'), ('Soundtrack Essential (Self-Managed)', 'Soundtrack Essential (Self-Managed)'), ('Soundtrack Unlimited (Serviced)', 'Soundtrack Unlimited (Serviced)'), ('Soundtrack Unlimited (Self-Managed)', 'Soundtrack Unlimited (Self-Managed)'), ('Beat Breeze', 'Beat Breeze')], max_length=100)),
                ('zone_count', models.IntegerField(default=1, help_text='Number of music zones for this tier')),
                ('monthly_price_per_zone', models.DecimalField(blank=True, decimal_places=2, help_text='Monthly price per zone for this tier', max_digits=10, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subscription_plans', to='crm_app.company')),
            ],
            options={
                'ordering': ['company', 'tier'],
                'indexes': [
                    models.Index(fields=['company', 'is_active'], name='crm_app_sub_company_1234ab_idx'),
                    models.Index(fields=['tier'], name='crm_app_sub_tier_5678cd_idx'),
                ],
            },
        ),
    ]