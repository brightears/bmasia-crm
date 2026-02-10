from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0056_ticket_zone_fk'),
    ]

    operations = [
        migrations.AddField(
            model_name='opportunity',
            name='service_type',
            field=models.CharField(
                blank=True,
                choices=[('soundtrack', 'Soundtrack'), ('beatbreeze', 'Beat Breeze')],
                help_text='Primary service/product for this opportunity',
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddIndex(
            model_name='opportunity',
            index=models.Index(fields=['service_type', 'stage'], name='crm_app_opp_service_stage_idx'),
        ),
    ]
