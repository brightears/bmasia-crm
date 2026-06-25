from django.db import migrations, models


class Migration(migrations.Migration):
    """0094 added property_name as NOT NULL with no DB default, so any contract INSERT that
    omitted it failed (caught on the Melia create). Give it an explicit default='' AND a
    DB-level DEFAULT '' so every insert path (ORM, raw, MCP/Cira) works without providing it."""

    dependencies = [
        ('crm_app', '0094_contract_property_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contract',
            name='property_name',
            field=models.CharField(blank=True, default='', help_text="Trading/venue name to print in the Section-2 schedule (e.g. 'Soneva Jani'). Bill-To, preamble and signature blocks always stay the legal company. Falls back to company name when blank.", max_length=200),
        ),
        migrations.RunSQL(
            sql="ALTER TABLE crm_app_contract ALTER COLUMN property_name SET DEFAULT '';",
            reverse_sql="ALTER TABLE crm_app_contract ALTER COLUMN property_name DROP DEFAULT;",
        ),
    ]
