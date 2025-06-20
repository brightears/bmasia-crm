# Generated by Django 5.2.2 on 2025-06-14 04:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0013_add_email_attachments'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emailtemplate',
            name='body_html',
            field=models.TextField(blank=True, help_text='HTML email body. Use variables like {{company_name}}, {{contact_name}}, {{days_until_expiry}}'),
        ),
    ]
