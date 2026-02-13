# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0065_invoice_improvements_pom_feedback'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='avatar_url',
            field=models.CharField(
                blank=True,
                help_text='URL or base64 data URL for user avatar',
                max_length=500,
                null=True,
            ),
        ),
    ]
