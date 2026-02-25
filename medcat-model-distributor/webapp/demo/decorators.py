from functools import wraps
from django.http import JsonResponse
from .models import APIKey


def require_valid_api_key(view_func):
    """
    Decorator to protect endpoints with API key authentication

    Usage:
        @require_valid_api_key
        def my_protected_view(request):
            # Your view logic
            pass
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Check for API key in header or query parameter
        api_key = (
            request.headers.get('X-API-Key') or 
            request.GET.get('api_key') or
            request.POST.get('api_key')
        )

        if not api_key:
            return JsonResponse({
                'error': 'API key required',
                'message': 'Please provide an API key via X-API-Key header or api_key parameter'
            }, status=401)

        if not APIKey.is_valid(api_key):
            return JsonResponse({
                'error': 'Invalid or expired API key',
                'message': 'Please obtain a valid API key'
            }, status=401)

        # API key is valid, proceed with the view
        return view_func(request, *args, **kwargs)

    return wrapper


# Example usage in views.py:
"""
from .decorators import require_valid_api_key

@require_valid_api_key
def protected_endpoint(request):
    return JsonResponse({
        'message': 'You have access to this protected resource!',
        'data': {'example': 'data'}
    })
"""
