"""Secret-like field names in audit payloads: redaction for new rows, counting for old ones.

A key is secret-like when its name contains password, passwd, secret, token, api_key
(or apikey) or credential, in any case. Values are never returned by ``secret_keys_in``;
only the key names are.
"""
import re

SECRET_KEY_NAME = re.compile(r'password|passwd|secret|token|api_?key|credential', re.IGNORECASE)
REDACTED = '[redacted]'


def is_secret_key(name):
    return bool(SECRET_KEY_NAME.search(str(name)))


def _redact_nested(value):
    if isinstance(value, dict):
        return {k: (REDACTED if is_secret_key(k) else _redact_nested(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_nested(v) for v in value]
    return value


def redact_changes(changes):
    """An audit ``changes`` dict with every secret-like key's value replaced, at any depth.

    A top-level change keeps its {'old', 'new'} shape: {'old': '[redacted]', 'new': '[redacted]'}.
    """
    if not isinstance(changes, dict):
        return _redact_nested(changes)
    return {
        key: ({'old': REDACTED, 'new': REDACTED} if is_secret_key(key) else _redact_nested(value))
        for key, value in changes.items()
    }


def secret_keys_in(payload, prefix=''):
    """Dotted names of every secret-like key in ``payload`` whose value is not already redacted."""
    found = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            name = f'{prefix}{key}'
            if is_secret_key(key):
                if not _is_redacted(value):
                    found.append(name)
            else:
                found.extend(secret_keys_in(value, f'{name}.'))
    elif isinstance(payload, list):
        for value in payload:
            found.extend(secret_keys_in(value, f'{prefix}[].'))
    return found


def _is_redacted(value):
    if value == REDACTED:
        return True
    return isinstance(value, dict) and set(value) <= {'old', 'new'} and all(v == REDACTED for v in value.values())
