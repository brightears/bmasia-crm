from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0063_contract_line_items'),
    ]

    operations = [
        # Add phone and email to Company
        migrations.AddField(
            model_name='company',
            name='phone',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='company',
            name='email',
            field=models.EmailField(blank=True, max_length=254),
        ),
        # Add mobile and preferred_contact_method to Contact
        migrations.AddField(
            model_name='contact',
            name='mobile',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='contact',
            name='preferred_contact_method',
            field=models.CharField(
                blank=True,
                choices=[('Email', 'Email'), ('Phone', 'Phone'), ('Mobile', 'Mobile'), ('LinkedIn', 'LinkedIn')],
                max_length=20,
            ),
        ),
    ]
