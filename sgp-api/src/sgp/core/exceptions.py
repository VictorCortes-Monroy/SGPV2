"""Excepciones de dominio reutilizables a través de los módulos."""

from typing import Any


class SGPError(Exception):
    """Excepción base del sistema."""

    code: str = "SGP_ERROR"
    http_status: int = 500

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(SGPError):
    code = "NOT_FOUND"
    http_status = 404


class ValidationError(SGPError):
    code = "VALIDATION_ERROR"
    http_status = 400


class PermissionDenied(SGPError):
    code = "PERMISSION_DENIED"
    http_status = 403


class Unauthorized(SGPError):
    code = "UNAUTHORIZED"
    http_status = 401


class InvalidTransitionError(SGPError):
    """Se intentó hacer una transición de estado no permitida."""

    code = "INVALID_TRANSITION"
    http_status = 409


class BusinessRuleViolation(SGPError):
    """Una regla de negocio impide la operación."""

    code = "BUSINESS_RULE_VIOLATION"
    http_status = 422
