"""Transport-only parsing helpers for the dedicated Rene MCP tool."""

import json


MAX_CIRA_REQUEST_BYTES = 2 * 1024 * 1024


class CiraJsonParseError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class _DuplicateCiraJsonKey(ValueError):
    pass


def _unique_json_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateCiraJsonKey(key)
        value[key] = item
    return value


def parse_cira_json_bytes(content):
    """Decode one bounded, duplicate-free UTF-8 JSON object."""

    if not isinstance(content, bytes):
        raise TypeError('content must be bytes')
    if len(content) > MAX_CIRA_REQUEST_BYTES:
        raise CiraJsonParseError(
            'REQUEST_TOO_LARGE', 'Cira request exceeds the reviewed 2 MiB bound'
        )
    try:
        value = json.loads(
            content.decode('utf-8'), object_pairs_hook=_unique_json_object
        )
    except _DuplicateCiraJsonKey as exc:
        raise CiraJsonParseError(
            'INVALID_JSON', 'Cira request contains a duplicate JSON key'
        ) from exc
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CiraJsonParseError(
            'INVALID_JSON', 'Cira request must be one UTF-8 JSON object'
        ) from exc
    if not isinstance(value, dict):
        raise CiraJsonParseError(
            'INVALID_JSON', 'Cira request must be one JSON object'
        )
    return value
