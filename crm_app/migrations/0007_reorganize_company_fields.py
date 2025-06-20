# Generated by Django 5.2.2 on 2025-06-10 09:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0006_rename_zone_to_region'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='company',
            name='crm_app_com_industr_ad13c1_idx',
        ),
        migrations.RemoveIndex(
            model_name='company',
            name='crm_app_com_name_53ec02_idx',
        ),
        migrations.RemoveField(
            model_name='company',
            name='company_size',
        ),
        migrations.RemoveField(
            model_name='company',
            name='is_corporate_account',
        ),
        migrations.RemoveField(
            model_name='company',
            name='region',
        ),
        migrations.AddField(
            model_name='company',
            name='country',
            field=models.CharField(blank=True, db_index=True, max_length=100),
        ),
        migrations.AddIndex(
            model_name='company',
            index=models.Index(fields=['name', 'country'], name='crm_app_com_name_0a64b2_idx'),
        ),
        migrations.AddIndex(
            model_name='company',
            index=models.Index(fields=['industry'], name='crm_app_com_industr_a763b7_idx'),
        ),
    ]
