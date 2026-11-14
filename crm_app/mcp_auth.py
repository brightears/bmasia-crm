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
            result = self.authenticate_credentials(token)
            # Observability only: lets audit records and logs name the method.
            from crm_app.auth_observability import mark_query_token
            mark_query_token(request)
            return result

        return None
