from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0068_quote_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='quote',
            name='first_followup_sent',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='quote',
            name='second_followup_sent',
            field=models.BooleanField(default=False),
        ),
    ]
