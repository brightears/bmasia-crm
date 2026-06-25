from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0093_company_contracted_product_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='property_name',
            field=models.CharField(blank=True, help_text="Trading/venue name to print in the Section-2 schedule (e.g. 'Soneva Jani'). Bill-To, preamble and signature blocks always stay the legal company. Falls back to company name when blank.", max_length=200),
        ),
    ]
