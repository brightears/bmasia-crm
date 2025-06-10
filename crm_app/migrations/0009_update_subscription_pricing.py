# Generated manually by BMAsia CRM

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0008_add_subscription_plans'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='subscriptionplan',
            name='monthly_price_per_zone',
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='billing_period',
            field=models.CharField(choices=[('Monthly', 'Monthly'), ('Yearly', 'Yearly')], default='Monthly', max_length=20),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='currency',
            field=models.CharField(choices=[('USD', 'USD - US Dollar'), ('THB', 'THB - Thai Baht')], default='USD', max_length=3),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='price_per_zone',
            field=models.IntegerField(blank=True, help_text='Price per zone (no decimals)', null=True),
        ),
    ]