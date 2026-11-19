"""EncryptedSecretField: a text value stored encrypted with FIELD_ENCRYPTION_KEY (Fernet).

Why not ``encrypted_model_fields.fields.EncryptedCharField`` (already in requirements):
it builds its key once at import time, and on Django 5 an update with an expression
reaches its save hook, which encrypts the expression's text instead of the value.
This field keeps the same storage format: a Fernet token as text, with MultiFernet when
FIELD_ENCRYPTION_KEY is a list (key rotation, see settings.FIELD_ENCRYPTION_KEY_PREVIOUS).

What a stored value reads as
- empty or NULL: as stored;
- a token that a configured key decrypts: the text (a ``DecryptedSecret``, a str that
  also remembers the stored form);
- a token-shaped value that no configured key decrypts: an ``UnreadableSecret``. It is
  truthy, keeps the stored form, and raises ``UndecryptableSecret`` the moment anything
  tries to use it as text, so it can never be sent anywhere as a password;
- anything else: a value stored before encryption, used as it is.

Token-shaped means what Fernet produces: padded urlsafe base64 (A-Z, a-z, 0-9, "-", "_",
"=" padding, length a multiple of 4) that decodes to at least 73 bytes, starts with the
version byte 0x80, and whose length minus 57 is a multiple of 16 (1 version + 8 time +
16 IV bytes, whole 16-byte cipher blocks, 32 HMAC bytes). Such a value is at least 100
characters long and starts with "gAAAAA"; a 16-letter Gmail app password never is.

Every ORM write encrypts: save, create, bulk_create, update with a string, bulk_update
and loaddata. A token-shaped value is written as it is (it is already encrypted), so a
dump and load round trip or a save of an unreadable value never encrypts twice.
Assigning a database expression (F(), Value(), a function) to the field is refused, and
so is every lookup except ``isnull`` and ``exact`` with an empty string: a lookup cannot
compare encrypted values.

In production (RENDER set) the field refuses to encrypt with the built-in development key.
A value saved unchanged (as loaded) is written back as stored when it is already encrypted,
or when no usable key is configured; a new value is refused then (``secret_input_error``
gives forms and views a plain message to show instead).
"""
import base64
import logging
import os
import re
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import FieldError, ImproperlyConfigured
from django.db import models
from django.db.models.lookups import Exact, IsNull

logger = logging.getLogger('crm_app.fields')

_B64URL = re.compile(r'^[A-Za-z0-9_-]+={0,2}$')
_MIN_TOKEN_BYTES = 73
_OVERHEAD_BYTES = 57


class UndecryptableSecret(Exception):
    """A stored secret is an encrypted token that no configured key can decrypt."""


def is_token_shaped(value):
    """True when ``value`` has the structure of a Fernet token (see the module docstring)."""
    if not isinstance(value, str) or len(value) < 100 or len(value) % 4 or not _B64URL.match(value):
        return False
    try:
        raw = base64.urlsafe_b64decode(value.encode('ascii'))
    except Exception:
        return False
    return (
        len(raw) >= _MIN_TOKEN_BYTES
        and raw[0] == 0x80
        and (len(raw) - _OVERHEAD_BYTES) % 16 == 0
    )


class DecryptedSecret(str):
    """The readable text of a stored secret; ``stored`` is what the database holds."""

    stored = None

    def __new__(cls, text, stored):
        obj = super().__new__(cls, text)
        obj.stored = stored
        return obj

    def __repr__(self):
        return '<secret>'


class UnreadableSecret:
    """A stored token that no configured key decrypts. Never usable as text."""

    def __init__(self, stored):
        self.stored = stored

    def __bool__(self):
        return True

    def _refuse(self, *args, **kwargs):
        raise UndecryptableSecret(
            'The stored value cannot be decrypted with the configured FIELD_ENCRYPTION_KEY; '
            'it has to be entered again.'
        )

    __str__ = _refuse
    encode = _refuse
    __len__ = _refuse
    __iter__ = _refuse

    def __repr__(self):
        return '<unreadable secret>'

    def __eq__(self, other):
        return isinstance(other, UnreadableSecret) and other.stored == self.stored

    def __hash__(self):
        return hash(('unreadable', self.stored))


def configured_keys():
    keys = getattr(settings, 'FIELD_ENCRYPTION_KEY', None)
    if not keys:
        raise ImproperlyConfigured('FIELD_ENCRYPTION_KEY must be set to read or write encrypted fields.')
    return tuple(keys) if isinstance(keys, (list, tuple)) else (keys,)


@lru_cache(maxsize=8)
def _fernets_for(keys):
    try:
        primary = Fernet(keys[0])
    except Exception:
        raise ImproperlyConfigured('FIELD_ENCRYPTION_KEY is not in the expected format.') from None
    others = []
    for key in keys[1:]:
        try:
            others.append(Fernet(key))
        except Exception:
            logger.warning('FIELD_ENCRYPTION_KEY_PREVIOUS is not in the expected format; it is ignored')
    return primary, MultiFernet([primary, *others])


def crypter():
    """MultiFernet over every usable configured key; encrypts with the first one."""
    return _fernets_for(configured_keys())[1]


def current_fernet():
    """Fernet for the first configured key only."""
    return _fernets_for(configured_keys())[0]


def _builtin_key():
    try:
        from bmasia_crm import settings as project_settings
    except Exception:  # pragma: no cover - settings module renamed
        return None
    return getattr(project_settings, '_BUILTIN_FIELD_ENCRYPTION_KEY', None)


def refuse_builtin_key_in_production():
    if os.environ.get('RENDER') and configured_keys()[0] == _builtin_key():
        raise ImproperlyConfigured(
            'FIELD_ENCRYPTION_KEY is the built-in development default; production does not '
            'encrypt with it. Set FIELD_ENCRYPTION_KEY in the environment of this service.'
        )


def encrypt_text(text):
    refuse_builtin_key_in_production()
    return crypter().encrypt(text.encode('utf-8')).decode('utf-8')


def can_encrypt():
    """False while no usable key is configured, or the built-in key is configured in production."""
    try:
        refuse_builtin_key_in_production()
        current_fernet()
        return True
    except ImproperlyConfigured:
        return False


TOKEN_INPUT_MESSAGE = 'This looks like an encrypted value, not a password. Enter the mail password itself.'
KEY_NOT_CONFIGURED_MESSAGE = 'Mail passwords cannot be saved until the encryption key is configured.'


def secret_input_error(text):
    """Why a typed secret cannot be stored, or None. For forms, serializers and views."""
    if not text:
        return None
    if is_token_shaped(text):
        return TOKEN_INPUT_MESSAGE
    if not can_encrypt():
        return KEY_NOT_CONFIGURED_MESSAGE
    return None


def read_stored(stored):
    """What a stored value reads as (see the module docstring)."""
    if stored is None or stored == '':
        return stored
    try:
        return DecryptedSecret(crypter().decrypt(stored.encode('utf-8')).decode('utf-8'), stored)
    except InvalidToken:
        pass
    except ImproperlyConfigured:
        logger.warning('FIELD_ENCRYPTION_KEY is not usable; an encrypted value cannot be read')
        return UnreadableSecret(stored) if is_token_shaped(stored) else DecryptedSecret(stored, stored)
    if is_token_shaped(stored):
        return UnreadableSecret(stored)
    return DecryptedSecret(stored, stored)


def _expression_is_allowed(expression):
    """Only the Case/When/Value(output_field=this field) shape that bulk_update builds."""
    from django.db.models import Case, Value, When
    from django.db.models.functions import Cast

    if isinstance(expression, Value):
        if expression.value is None:
            return True
        return isinstance(getattr(expression, '_output_field_or_none', None), EncryptedSecretField)
    if isinstance(expression, Cast):
        return _expression_is_allowed(expression.source_expressions[0])
    if isinstance(expression, When):
        return _expression_is_allowed(expression.result)
    if isinstance(expression, Case):
        return all(_expression_is_allowed(c) for c in expression.cases) and _expression_is_allowed(expression.default)
    return False


class _EmptyOnlyExact(Exact):
    def __init__(self, lhs, rhs):
        if rhs not in ('', None):
            raise FieldError('Encrypted fields cannot be compared; only isnull and an exact empty string work.')
        super().__init__(lhs, rhs)


class EncryptedSecretField(models.CharField):
    description = 'Text stored encrypted with FIELD_ENCRYPTION_KEY'

    def get_internal_type(self):
        # A token is much longer than the text it holds: store it in an unbounded column.
        return 'TextField'

    # ---------------------------------------------------------------- reading
    def from_db_value(self, value, expression, connection):
        return read_stored(value)

    def to_python(self, value):
        if isinstance(value, (UnreadableSecret, DecryptedSecret)) or value is None:
            return value
        return super().to_python(value)

    # ---------------------------------------------------------------- writing
    def get_prep_value(self, value):
        return value

    def get_db_prep_value(self, value, connection, prepared=False):
        if value is None:
            return None
        if isinstance(value, UnreadableSecret):
            return value.stored
        if isinstance(value, DecryptedSecret) and value.stored is not None:
            # The value as loaded, unchanged: an encrypted one is written back as stored;
            # a plain one stored before encryption is encrypted now when a usable key is
            # configured, and otherwise written back exactly as stored.
            if is_token_shaped(value.stored) or not can_encrypt():
                return value.stored
        if hasattr(value, 'resolve_expression'):
            raise FieldError(f'{self.name} cannot be written from a database expression; assign the text.')
        text = value if isinstance(value, str) else str(value)
        if text == '':
            return ''
        if is_token_shaped(text):
            return str(text)  # already encrypted (a dump and load, or a stored unreadable value)
        return encrypt_text(str(text))

    def get_placeholder(self, value, compiler, connection):
        if hasattr(value, 'resolve_expression') and not _expression_is_allowed(value):
            raise FieldError(
                f'{self.name} cannot be written from a database expression (F(), Value(), a function); '
                'assign the text so it is encrypted.'
            )
        return '%s'

    # ---------------------------------------------------------------- dumpdata
    def value_to_string(self, obj):
        """The stored (encrypted) form, never the decrypted text."""
        value = self.value_from_object(obj)
        if value is None or value == '':
            return value
        stored = getattr(value, 'stored', None)
        if stored is not None:
            return stored
        return self.get_db_prep_value(value, connection=None)

    # ---------------------------------------------------------------- lookups
    def get_lookup(self, lookup_name):
        if lookup_name == 'isnull':
            return IsNull
        if lookup_name == 'exact':
            return _EmptyOnlyExact
        raise FieldError(f'{self.name} is encrypted; the lookup "{lookup_name}" cannot be used on it.')

    def get_transform(self, lookup_name):
        raise FieldError(f'{self.name} is encrypted; "{lookup_name}" cannot be used on it.')
