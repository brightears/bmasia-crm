"""Rate limits for the credential-checking login and token-obtain endpoints.

The project's default cache is a DummyCache, which turns every DRF throttle
that relies on it into a no-op. These throttles store their counters in a
dedicated in-process cache alias (``LOGIN_THROTTLE_CACHE_ALIAS``) that nothing
else uses, so adding them does not make any other request in the app start
being throttled, and the global DRF throttle settings stay untouched.

Limits are per process: with several gunicorn workers each worker counts on
its own, and a restart clears the counters. That is acceptable here: the aim
is to make password guessing slow, not to meter usage precisely.
"""
import hashlib

from django.core.cache import caches
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.throttling import SimpleRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView

LOGIN_THROTTLE_CACHE_ALIAS = 'login_throttle'


class _LoginThrottleBase(SimpleRateThrottle):
    def __init__(self):
        super().__init__()
        # Resolved per instance: never the default (dummy) cache.
        self.cache = caches[LOGIN_THROTTLE_CACHE_ALIAS]


class LoginUsernameRateThrottle(_LoginThrottleBase):
    """Caps attempts against one username, whatever address they come from."""

    scope = 'login_username'
    rate = '60/hour'

    def get_cache_key(self, request, view):
        try:
            username = request.data.get('username')
        except Exception:
            # Unparseable body: let the view report the error as it always has.
            return None
        if not isinstance(username, str) or not username.strip():
            return None
        digest = hashlib.sha256(username.strip().lower().encode('utf-8')).hexdigest()
        return self.cache_format % {'scope': self.scope, 'ident': digest}


class LoginClientRateThrottle(_LoginThrottleBase):
    """Caps attempts from one client address across all usernames."""

    scope = 'login_client'
    rate = '300/hour'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


LOGIN_THROTTLE_CLASSES = [LoginUsernameRateThrottle, LoginClientRateThrottle]


class ThrottledObtainAuthToken(ObtainAuthToken):
    """DRF's obtain_auth_token with login throttles; request and response unchanged."""

    throttle_classes = [*ObtainAuthToken.throttle_classes, *LOGIN_THROTTLE_CLASSES]


class ThrottledTokenObtainPairView(TokenObtainPairView):
    """simplejwt's TokenObtainPairView with login throttles added to its defaults."""

    throttle_classes = [*TokenObtainPairView.throttle_classes, *LOGIN_THROTTLE_CLASSES]


throttled_obtain_auth_token = ThrottledObtainAuthToken.as_view()
