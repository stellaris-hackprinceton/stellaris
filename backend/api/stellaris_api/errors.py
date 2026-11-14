"""Contract-shaped JSON error envelope (Contracts.md section 9)."""

import logging

from flask import g, jsonify
from werkzeug.exceptions import HTTPException

log = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, status, code, message, *, retryable=False, details=None, headers=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}
        self.headers = headers or {}


def validation_error(field_errors, message="Request validation failed."):
    return ApiError(422, "VALIDATION_FAILED", message, details={"field_errors": field_errors})


def error_response(status, code, message, *, retryable=False, details=None, headers=None):
    response = jsonify(
        {
            "error": {
                "code": code,
                "message": message,
                "request_id": g.get("request_id"),
                "retryable": retryable,
                "details": details or {},
            }
        }
    )
    response.status_code = status
    for name, value in (headers or {}).items():
        response.headers[name] = value
    return response


_HTTP_CODES = {
    400: "BAD_REQUEST",
    404: "RESOURCE_NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    413: "REQUEST_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
}


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def _api_error(err):
        return error_response(
            err.status, err.code, err.message,
            retryable=err.retryable, details=err.details, headers=err.headers,
        )

    @app.errorhandler(HTTPException)
    def _http_error(err):
        status = err.code or 500
        code = _HTTP_CODES.get(status, "INTERNAL_ERROR" if status >= 500 else "BAD_REQUEST")
        message = "Resource not found." if status == 404 else (err.description or err.name)
        return error_response(status, code, message)

    @app.errorhandler(Exception)
    def _unexpected(err):
        log.exception("Unhandled error (request_id=%s)", g.get("request_id"))
        return error_response(500, "INTERNAL_ERROR", "An internal error occurred.", retryable=True)
