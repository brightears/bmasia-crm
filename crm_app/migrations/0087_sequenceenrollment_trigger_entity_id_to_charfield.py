from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0086_revenue_recognition_module'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sequenceenrollment',
            name='trigger_entity_id',
            field=models.CharField(
                blank=True,
                help_text='ID of the triggering entity for deduplication (UUID or string key)',
                max_length=255,
                null=True,
            ),
        ),
    ]
