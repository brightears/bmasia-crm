"""GET /healthz/: the web process is up. Unauthenticated; touches no database or service."""
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe


@never_cache
@require_safe
def healthz(request):
    return JsonResponse({'status': 'ok'})
