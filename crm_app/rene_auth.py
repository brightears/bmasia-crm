"""Least-privilege authentication for Rene's read and scoped MCP lanes."""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission


_SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
_TOKEN_RE = re.compile(r'^[A-Za-z0-9._~+\-/=]{16,4096}$')
_MCP_TOKEN_RE = re.compile(r'^[A-Za-z0-9._~+\-/=]{32,4096}$')


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


@dataclass(frozen=True)
class RenePhase2MCPCredential:
    """Request-local proof that only the dedicated Rene MCP auth can mint."""

    token_fingerprint_sha256: str
    user_id: str
    is_rene_phase2_mcp: bool = True


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


def _configured_rene_phase2_mcp():
    fingerprint = getattr(settings, 'CIRA_RENE_MCP_TOKEN_SHA256', '')
    configured_user_id = getattr(settings, 'CIRA_RENE_MCP_USER_ID', '')
    if not isinstance(fingerprint, str) or _SHA256_RE.fullmatch(fingerprint) is None:
        raise AuthenticationFailed('Rene Phase 2 MCP credential is not configured')
    if not isinstance(configured_user_id, str):
        raise AuthenticationFailed('Rene Phase 2 MCP principal is not configured')
    try:
        canonical_user_id = str(UUID(configured_user_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise AuthenticationFailed(
            'Rene Phase 2 MCP principal is not configured'
        ) from exc
    if configured_user_id != canonical_user_id:
        raise AuthenticationFailed('Rene Phase 2 MCP principal is not canonical')
    return fingerprint, canonical_user_id


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


class RenePhase2MCPAuthentication(BaseAuthentication):
    """Authenticate the dedicated MCP endpoint with an isolated secret."""

    keyword = 'Rene'

    def authenticate(self, request):
        header = request.headers.get('Authorization', '')
        if not header:
            return None
        parts = header.split(' ', 1)
        if len(parts) != 2 or parts[0] != self.keyword:
            return None
        token = parts[1]
        if _MCP_TOKEN_RE.fullmatch(token) is None:
            raise AuthenticationFailed('Invalid Rene Phase 2 MCP credential')

        configured, user_id = _configured_rene_phase2_mcp()
        observed = hashlib.sha256(token.encode('ascii')).hexdigest()
        if not hmac.compare_digest(observed, configured):
            raise AuthenticationFailed('Invalid Rene Phase 2 MCP credential')

        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist as exc:
            raise AuthenticationFailed(
                'Rene Phase 2 MCP principal is not configured'
            ) from exc
        credential = RenePhase2MCPCredential(
            token_fingerprint_sha256=observed,
            user_id=user_id,
        )
        return user, credential

    def authenticate_header(self, request):
        return self.keyword


def is_exact_rene_phase2_mcp_request(request):
    """Fail closed unless this request bears the exact scoped credential."""

    try:
        configured, user_id = _configured_rene_phase2_mcp()
    except AuthenticationFailed:
        return False
    user = getattr(request, 'user', None)
    credential = getattr(request, 'auth', None)
    return bool(
        getattr(user, 'is_authenticated', False)
        and getattr(user, 'is_active', False)
        and str(getattr(user, 'pk', '')) == user_id
        and isinstance(credential, RenePhase2MCPCredential)
        and credential.is_rene_phase2_mcp
        and credential.user_id == user_id
        and hmac.compare_digest(
            credential.token_fingerprint_sha256,
            configured,
        )
    )


class IsExactRenePhase2MCPPrincipal(BasePermission):
    def has_permission(self, request, view):
        return is_exact_rene_phase2_mcp_request(request)


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
