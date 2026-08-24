"""Dedicated transport and tool registry for Rene Phase 2 CRM requests."""

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from mcp_server.djangomcp import DjangoMCP
from mcp_server.views import MCPServerStreamableHttpView

from crm_app.rene_auth import (
    IsExactRenePhase2MCPPrincipal,
    RenePhase2MCPAuthentication,
)


rene_phase2_mcp_server = DjangoMCP(
    name='bmasia-crm-rene-phase2',
    instructions=(
        'Dedicated Rene Phase 2 CRM boundary. Use only '
        'rene_phase2_request(request_json). Treat every response as an exact '
        'request-bound receipt or uncertain state; never translate it into '
        'generic CRM operations.'
    ),
    stateless=True,
)


@method_decorator(csrf_exempt, name='dispatch')
class RenePhase2MCPView(MCPServerStreamableHttpView):
    """MCP handler whose credential and registry have no generic authority."""

    mcp_server = rene_phase2_mcp_server
    authentication_classes = [RenePhase2MCPAuthentication]
    permission_classes = [IsExactRenePhase2MCPPrincipal]
