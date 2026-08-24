"""Canonical identity helpers shared by Rene's read and Cira-only lanes."""

from __future__ import annotations

import hashlib
import json
from datetime import timezone


def canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(',', ':'),
    )


def canonical_sha256(value):
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


def rfc3339(value):
    if value is None or value.tzinfo is None:
        raise ValueError('timestamp must be timezone-aware')
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def contract_version(contract):
    """Stable optimistic version derived only from immutable ID + updated_at."""

    updated_at = rfc3339(contract.updated_at)
    return canonical_sha256({'contract_id': str(contract.id), 'updated_at': updated_at})
