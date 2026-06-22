import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_handler

logger = logging.getLogger("trips")


def handle_exception(exc, context):
    """Wrap DRF's default exception handler so that *any* unhandled
    exception - not just APIException/Http404/PermissionDenied - is logged
    server-side and returned to the client as a generic, safe JSON error
    instead of a stack trace or an opaque 500.
    """
    response = drf_default_handler(exc, context)

    if response is not None:
        # A recognized DRF/Django exception already produced a clean
        # response (e.g. ValidationError -> 400). Just make sure it has a
        # consistent shape.
        if isinstance(response.data, dict) and "detail" not in response.data:
            response.data = {"detail": response.data}
        return response

    # Anything else is unexpected: log it with full context, but never
    # surface internals (file paths, query params, exception args) to the
    # caller.
    request = context.get("request")
    view = context.get("view")
    logger.exception(
        "Unhandled exception in %s (%s %s)",
        getattr(view, "__class__", view),
        getattr(request, "method", "?"),
        getattr(request, "path", "?"),
        exc_info=exc,
    )
    return Response(
        {"detail": "An unexpected error occurred. Please try again."},
        status=500,
    )
