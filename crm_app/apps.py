from django.apps import AppConfig


class CrmAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'crm_app'

    def ready(self):
        import crm_app.signals  # noqa - registers signal handlers
        self._patch_mcp_server()

    @staticmethod
    def _patch_mcp_server():
        """Fix django-mcp-server v0.5.7 bug: _patched_initialize_request
        crashes on normal (non-MCP) requests because it assumes all requests
        have 'original_request'. This patch adds a fallback to DRF's default."""
        try:
            from mcp_server.djangomcp import BaseAPIViewCallerTool
            from rest_framework.views import APIView

            original_initialize = APIView.initialize_request

            @staticmethod
            def safe_patched_initialize_request(self, request, *args, **kwargs):
                if hasattr(request, 'original_request'):
                    # MCP request — use the MCP flow
                    original_request = request.original_request
                    original_request.request = request
                    original_request.method = request.method
                    return original_request
                # Normal request — use standard DRF initialization
                return original_initialize(self, request, *args, **kwargs)

            BaseAPIViewCallerTool._patched_initialize_request = safe_patched_initialize_request
        except ImportError:
            pass  # mcp_server not installed — nothing to patch
