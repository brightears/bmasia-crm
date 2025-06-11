# Generated manually by BMAsia CRM

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0010_remove_annual_revenue_add_zones'),
    ]

    operations = [
        # Add soundtrack_account_id to Company
        migrations.AddField(
            model_name='company',
            name='soundtrack_account_id',
            field=models.CharField(blank=True, help_text='Soundtrack Your Brand account ID for API integration', max_length=100),
        ),
        
        # Remove the foreign key to SubscriptionPlan from Zone
        migrations.RemoveField(
            model_name='zone',
            name='subscription_plan',
        ),
        
        # Add foreign key to Company
        migrations.AddField(
            model_name='zone',
            name='company',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, related_name='zones', to='crm_app.company'),
            preserve_default=False,
        ),
        
        # Remove soundtrack_account_id from Zone (now using company's)
        migrations.RemoveField(
            model_name='zone',
            name='soundtrack_account_id',
        ),
        
        # Update indexes
        migrations.RemoveIndex(
            model_name='zone',
            name='crm_app_zon_subscri_9876ab_idx',
        ),
        migrations.RemoveIndex(
            model_name='zone',
            name='crm_app_zon_platfor_5432cd_idx',
        ),
        migrations.AddIndex(
            model_name='zone',
            index=models.Index(fields=['company', 'status'], name='crm_app_zon_company_1234ab_idx'),
        ),
        migrations.AddIndex(
            model_name='zone',
            index=models.Index(fields=['platform', 'company'], name='crm_app_zon_platfor_5678cd_idx'),
        ),
        
        # Update default platform
        migrations.AlterField(
            model_name='zone',
            name='platform',
            field=models.CharField(choices=[('soundtrack', 'Soundtrack Your Brand'), ('beatbreeze', 'Beat Breeze')], default='soundtrack', max_length=20),
        ),
    ]