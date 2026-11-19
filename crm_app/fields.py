"""EncryptedSecretField: a text value stored encrypted with FIELD_ENCRYPTION_KEY (Fernet).

Why not ``encrypted_model_fields.fields.EncryptedCharField`` (already in requirements):
- it builds its key at import time, so the key cannot change without a restart and
  tests cannot use their own key;
- on Django 5 an update with an expression (``update(field=Value(...))``) reaches its
  ``get_db_prep_save``, which encrypts the expression's text instead of the value.
This field keeps the same storage format (a Fernet token as text, MultiFernet when
FIELD_ENCRYPTION_KEY is a list for key rotation) and fixes both.

Reads accept both forms: a stored value that decrypts under a configured key is
returned decrypted; anything else is a value stored before encryption and is returned
as it is. Every save encrypts with the first configured key. An expression is written
as given (used only by the rollback path of ``encrypt_smtp_passwords``).
"""
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


def configured_keys():
    keys = getattr(settings, 'FIELD_ENCRYPTION_KEY', None)
    if not keys:
        raise ImproperlyConfigured('FIELD_ENCRYPTION_KEY must be set to read or write encrypted fields.')
    return tuple(keys) if isinstance(keys, (list, tuple)) else (keys,)


@lru_cache(maxsize=8)
def _crypter_for(keys):
    try:
        return MultiFernet([Fernet(k) for k in keys])
    except Exception:
        raise ImproperlyConfigured('FIELD_ENCRYPTION_KEY is not in the expected format.') from None


def crypter():
    return _crypter_for(configured_keys())


def decrypt_or_none(stored):
    """The decrypted text, or None when ``stored`` is not a token under a configured key."""
    try:
        return crypter().decrypt(stored.encode('utf-8')).decode('utf-8')
    except InvalidToken:
        return None


class EncryptedSecretField(models.CharField):
    description = 'Text stored encrypted with FIELD_ENCRYPTION_KEY'

    def get_internal_type(self):
        # A token is much longer than the text it holds: store it in an unbounded column.
        return 'TextField'

    def from_db_value(self, value, expression, connection):
        if value is None or value == '':
            return value
        decrypted = decrypt_or_none(value)
        return value if decrypted is None else decrypted

    def get_db_prep_save(self, value, connection):
        if value is None or hasattr(value, 'as_sql') or hasattr(value, 'resolve_expression'):
            return value
        return crypter().encrypt(str(value).encode('utf-8')).decode('utf-8')
