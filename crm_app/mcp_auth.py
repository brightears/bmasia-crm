"""
Custom authentication for MCP endpoint.
Accepts token via query parameter (?token=xxx) or standard Authorization header.
This allows Claude.ai connectors (which don't support custom headers) to authenticate.
"""
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class QueryParamTokenAuthentication(TokenAuthentication):
    """Token auth that also checks for ?token= query parameter."""

    def authenticate(self, request):
        # First try standard header auth
        result = super().authenticate(request)
        if result is not None:
            return result

        # Fall back to query parameter
        token = request.query_params.get('token')
        if token:
            return self.authenticate_credentials(token)

        return None
