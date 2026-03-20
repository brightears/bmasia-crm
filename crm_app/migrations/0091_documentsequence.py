from django.db import migrations, models


def seed_sequences(apps, schema_editor):
    """Seed DocumentSequence with current max values to avoid number conflicts."""
    DocumentSequence = apps.get_model('crm_app', 'DocumentSequence')

    # Current max numbers as of 20.03.2026:
    # HK-CT26: 004 (HK-CT26001 through HK-CT26004)
    # TH-CT26: none yet
    # HK-QT26: none yet (all old format Q-2026-XXXX)
    # TH-QT26: 003 (TH-QT26001 through TH-QT26003)
    seeds = [
        ('HK', 'CT', '26', 5),
        ('TH', 'CT', '26', 1),
        ('HK', 'QT', '26', 1),
        ('TH', 'QT', '26', 4),
    ]
    for region, doc_type, year, next_seq in seeds:
        DocumentSequence.objects.get_or_create(
            region=region,
            doc_type=doc_type,
            year=year,
            defaults={'next_sequence': next_seq}
        )


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0090_contractservicelocation_price'),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentSequence',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('region', models.CharField(choices=[('HK', 'Hong Kong'), ('TH', 'Thailand')], max_length=2)),
                ('doc_type', models.CharField(choices=[('CT', 'Contract'), ('QT', 'Quote'), ('IV', 'Invoice')], max_length=2)),
                ('year', models.CharField(max_length=2)),
                ('next_sequence', models.IntegerField(default=1)),
            ],
            options={
                'unique_together': {('region', 'doc_type', 'year')},
            },
        ),
        migrations.RunPython(seed_sequences, migrations.RunPython.noop),
    ]
