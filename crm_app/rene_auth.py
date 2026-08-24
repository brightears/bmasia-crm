"""Least-privilege bearer authentication for Rene's renewal-book reader."""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission


_SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
_TOKEN_RE = re.compile(r'^[A-Za-z0-9._~+\-/=]{16,4096}$')


@dataclass(frozen=True)
class ReneRenewalPrincipal:
    token_fingerprint_sha256: str
    pk: str = 'rene-renewal-reader'
    id: str = 'rene-renewal-reader'
    username: str = 'rene'
    is_authenticated: bool = True
    is_active: bool = True
    is_staff: bool = False
    is_superuser: bool = False
    is_rene_renewal_reader: bool = True


def _configured_capability():
    fingerprint = getattr(settings, 'RENE_RENEWAL_BOOK_TOKEN_SHA256', '')
    expires_at = getattr(settings, 'RENE_RENEWAL_BOOK_TOKEN_EXPIRES_AT', '')
    if not isinstance(fingerprint, str) or _SHA256_RE.fullmatch(fingerprint) is None:
        raise AuthenticationFailed('Rene renewal-book credential is not configured')
    if not isinstance(expires_at, str):
        raise AuthenticationFailed('Rene renewal-book credential expiry is not configured')
    try:
        expires = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
    except ValueError as exc:
        raise AuthenticationFailed(
            'Rene renewal-book credential expiry is invalid'
        ) from exc
    if expires.tzinfo is None or expires.astimezone(timezone.utc) <= datetime.now(timezone.utc):
        raise AuthenticationFailed('Rene renewal-book credential is expired')
    return fingerprint, expires_at


class ReneRenewalBearerAuthentication(BaseAuthentication):
    """Accept Rene's token or defer JWT/session/token to their own classes."""

    keyword = 'Bearer'

    def authenticate(self, request):
        header = request.headers.get('Authorization', '')
        if not header:
            return None
        parts = header.split(' ', 1)
        if len(parts) != 2 or parts[0] != self.keyword:
            return None
        token = parts[1]
        # JWTAuthentication owns JWT-shaped Bearer values on the existing
        # renewal-book action; Rene's opaque token is never interpreted as JWT.
        if token.count('.') == 2:
            return None
        if _TOKEN_RE.fullmatch(token) is None:
            raise AuthenticationFailed('Invalid Rene renewal-book bearer credential')
        configured, _ = _configured_capability()
        observed = hashlib.sha256(token.encode('ascii')).hexdigest()
        if not hmac.compare_digest(observed, configured):
            raise AuthenticationFailed('Invalid Rene renewal-book bearer credential')
        principal = ReneRenewalPrincipal(token_fingerprint_sha256=observed)
        return principal, None

    def authenticate_header(self, request):
        return self.keyword


class IsExactReneRenewalReader(BasePermission):
    def has_permission(self, request, view):
        return bool(
            getattr(request.user, 'is_authenticated', False)
            and getattr(request.user, 'is_rene_renewal_reader', False)
        )


class IsReneRenewalReaderOrAuthenticatedUser(BasePermission):
    """Preserve the existing authenticated CRM readers without widening access."""

    def has_permission(self, request, view):
        return bool(getattr(request.user, 'is_authenticated', False))


def capability_receipt(principal: ReneRenewalPrincipal):
    configured, expires_at = _configured_capability()
    if not isinstance(principal, ReneRenewalPrincipal):
        raise AuthenticationFailed('Capability receipt requires Rene')
    if not hmac.compare_digest(principal.token_fingerprint_sha256, configured):
        raise AuthenticationFailed('Capability receipt belongs to another credential')
    return {
        'schema': 'bmasia.crm.token-capabilities.v1',
        'subject': 'rene',
        'token_fingerprint_sha256': configured,
        'permissions': ['contracts.renewal_book.read'],
        'allowed_methods': ['GET'],
        'allowed_paths': ['/api/v1/contracts/renewal-book/'],
        'expires_at': expires_at,
    }
