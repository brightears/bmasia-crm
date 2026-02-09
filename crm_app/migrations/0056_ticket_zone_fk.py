import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0055_contracttemplate_pdf_format'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='zone',
            field=models.ForeignKey(
                blank=True,
                help_text='Music zone related to this ticket (optional)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='tickets',
                to='crm_app.zone',
            ),
        ),
    ]
