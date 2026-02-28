from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0081_prospect_reply_model'),
    ]

    operations = [
        migrations.AlterField(
            model_name='opportunity',
            name='lead_source',
            field=models.CharField(
                blank=True,
                choices=[
                    ('Website', 'Website'),
                    ('Website Inquiry', 'Website Inquiry'),
                    ('Referral', 'Referral'),
                    ('Cold Call', 'Cold Call'),
                    ('Email Campaign', 'Email Campaign'),
                    ('Social Media', 'Social Media'),
                    ('Trade Show', 'Trade Show'),
                    ('Partner', 'Partner'),
                    ('Direct Mail', 'Direct Mail'),
                    ('Webinar', 'Webinar'),
                    ('Other', 'Other'),
                ],
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name='opportunity',
            name='contact_method',
            field=models.CharField(
                blank=True,
                choices=[
                    ('Email', 'Email'),
                    ('Phone', 'Phone Call'),
                    ('Meeting', 'In-Person Meeting'),
                    ('In-person Meeting', 'In-Person Meeting'),
                    ('Video Call', 'Video Call'),
                    ('Chat', 'Chat'),
                    ('Social Media', 'Social Media'),
                    ('Demo', 'Product Demo'),
                    ('Presentation', 'Presentation'),
                    ('Other', 'Other'),
                ],
                max_length=20,
            ),
        ),
    ]
