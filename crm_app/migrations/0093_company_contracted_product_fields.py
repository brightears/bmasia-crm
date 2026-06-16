from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0092_quote_billing_pdf_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='contracted_product',
            field=models.CharField(blank=True, choices=[('beatbreeze', 'Beat Breeze'), ('soundtrack', 'Soundtrack'), ('mixed', 'Mixed')], help_text='Contracted music product per the renewal funnel (source of truth).', max_length=20),
        ),
        migrations.AddField(
            model_name='company',
            name='contracted_zone_count',
            field=models.IntegerField(blank=True, help_text='Contracted zone count per the renewal funnel (source of truth).', null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='contracted_synced_at',
            field=models.DateField(blank=True, help_text='Date contracted_product/contracted_zone_count were last reconciled from the funnel.', null=True),
        ),
    ]
