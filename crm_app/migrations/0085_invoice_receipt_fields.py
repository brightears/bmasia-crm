from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0084_contact_document_email_prefs'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='receipt_number',
            field=models.CharField(
                blank=True,
                help_text='Auto-generated when marked as paid',
                max_length=50,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name='invoice',
            name='receipt_sent',
            field=models.BooleanField(default=False),
        ),
    ]
