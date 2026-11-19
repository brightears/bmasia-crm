"""User.smtp_password becomes an encrypted field.

Schema only: the column type widens from varchar(255) to text, because an encrypted
value is longer than the plain one (a 255-character value encrypts to about 440
characters). No stored value is changed here. Existing plain values keep working
(reads accept both forms) until `manage.py encrypt_smtp_passwords --execute` encrypts
them. Reversing this migration narrows the column again, so run
`encrypt_smtp_passwords --decrypt-to-plain --execute` first if any value is encrypted.
"""
import crm_app.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0105_care_touch'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='smtp_password',
            field=crm_app.fields.EncryptedSecretField(
                blank=True, help_text='Gmail app password (stored encrypted)', max_length=255, null=True,
            ),
        ),
    ]
