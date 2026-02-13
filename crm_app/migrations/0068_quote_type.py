from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0067_avatar_url_textfield'),
    ]

    operations = [
        migrations.AddField(
            model_name='quote',
            name='quote_type',
            field=models.CharField(
                choices=[('new', 'New Business'), ('renewal', 'Renewal'), ('addon', 'Add-on')],
                default='new',
                max_length=20,
            ),
        ),
    ]
