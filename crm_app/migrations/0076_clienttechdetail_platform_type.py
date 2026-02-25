from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0075_quote_contract_duration'),
    ]

    operations = [
        migrations.AddField(
            model_name='clienttechdetail',
            name='platform_type',
            field=models.CharField(blank=True, choices=[('soundtrack', 'Soundtrack Your Brand'), ('beatbreeze', 'Beat Breeze')], help_text='Music platform type', max_length=20),
        ),
    ]
