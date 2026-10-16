from django.http import HttpResponse, JsonResponse

from apps.common.exceptions import nest_error_body


def health(request):
    """GET / — 기존 NestJS AppController와 같은 응답."""
    return HttpResponse("Hello World!", content_type="text/html; charset=utf-8")


def not_found(request, exception=None):
    message = f"Cannot {request.method} {request.path}"
    return JsonResponse(nest_error_body(404, message), status=404)


def server_error(request):
    return JsonResponse(nest_error_body(500, "Internal server error"), status=500)
