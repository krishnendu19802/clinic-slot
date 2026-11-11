"""One error envelope: {"error": {code, message, fields, details}} (see docs/api/contract.md)."""
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler


class ApiError(APIException):
    """Domain error. Raise from services; the handler renders the envelope."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, code: str, message: str = "", status_code: int | None = None, **details):
        if status_code:
            self.status_code = status_code
        self.code, self.details = code, details
        super().__init__(message or code)


def handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, ApiError):
        body = {"code": exc.code, "message": str(exc.detail), "fields": {}, "details": exc.details}
    elif isinstance(exc, ValidationError):
        fields = exc.detail if isinstance(exc.detail, dict) else {"non_field_errors": exc.detail}
        body = {"code": "VALIDATION_ERROR", "message": "Invalid input", "fields": fields, "details": {}}
    else:
        code = getattr(exc, "default_code", "error").upper()
        code = {"NOT_AUTHENTICATED": "TOKEN_INVALID", "AUTHENTICATION_FAILED": "TOKEN_INVALID",
                "PERMISSION_DENIED": "ROLE_FORBIDDEN", "NOT_FOUND": "NOT_FOUND"}.get(code, code)
        details = {"retry_after_seconds": exc.wait} if hasattr(exc, "wait") and exc.wait else {}
        body = {"code": code, "message": str(exc.detail), "fields": {}, "details": details}
    response.data = {"error": body}
    return response
