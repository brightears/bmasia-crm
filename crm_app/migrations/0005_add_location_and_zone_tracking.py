# Generated by Django 5.2.2 on 2025-06-10 06:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0004_update_company_size_choices'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='is_corporate_account',
            field=models.BooleanField(default=False, help_text='Is this a corporate account managing multiple locations?'),
        ),
        migrations.AddField(
            model_name='company',
            name='location_count',
            field=models.IntegerField(default=1, help_text='Number of physical locations'),
        ),
        migrations.AddField(
            model_name='company',
            name='music_zone_count',
            field=models.IntegerField(default=1, help_text='Total number of music zones across all locations'),
        ),
    ]
