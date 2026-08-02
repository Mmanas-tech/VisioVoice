"""Custom exception classes and handlers."""

import html
import re
from typing import Any, Optional


def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent XSS and injection attacks."""
    if not isinstance(text, str):
        return text
    text = html.escape(text)
    text = re.sub(r'[<>"\']', '', text)
    return text.strip()


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str = "An error occurred",
        status_code: int = 500,
        details: Optional[Any] = None,
    ):
        self.message = sanitize_input(message) if isinstance(message, str) else message
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class AuthenticationError(AppException):
    """Authentication failed."""

    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(message=message, status_code=401)


class AuthorizationError(AppException):
    """Insufficient permissions."""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message=message, status_code=403)


class NotFoundError(AppException):
    """Resource not found."""

    def __init__(self, resource: str = "Resource", resource_id: str = ""):
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} with id '{resource_id}' not found"
        super().__init__(message=message, status_code=404)


class ConflictError(AppException):
    """Resource conflict (duplicate)."""

    def __init__(self, message: str = "Resource already exists"):
        super().__init__(message=message, status_code=409)


class ValidationError(AppException):
    """Input validation failed."""

    def __init__(self, message: str = "Validation error", details: Optional[Any] = None):
        super().__init__(message=message, status_code=422, details=details)


class FileTooLargeError(AppException):
    """File exceeds size limit."""

    def __init__(self, max_size_mb: int = 2048):
        message = f"File exceeds maximum size of {max_size_mb}MB"
        super().__init__(message=message, status_code=413)


class UnsupportedFileTypeError(AppException):
    """Unsupported file type."""

    def __init__(self, file_type: str = "", allowed: Optional[list[str]] = None):
        message = f"Unsupported file type: {file_type}"
        if allowed:
            message += f". Allowed types: {', '.join(allowed)}"
        super().__init__(message=message, status_code=422)


class RateLimitExceededError(AppException):
    """Rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded. Try again later."):
        super().__init__(message=message, status_code=429)


class VideoProcessingError(AppException):
    """Video processing failed."""

    def __init__(self, message: str = "Video processing failed", details: Optional[Any] = None):
        super().__init__(message=message, status_code=500, details=details)


class ModelInferenceError(AppException):
    """ML model inference failed."""

    def __init__(self, message: str = "Model inference failed", details: Optional[Any] = None):
        super().__init__(message=message, status_code=500, details=details)


class StorageError(AppException):
    """Storage operation failed."""

    def __init__(self, message: str = "Storage operation failed", details: Optional[Any] = None):
        super().__init__(message=message, status_code=500, details=details)


class TranscriptionError(AppException):
    """Transcription processing failed."""

    def __init__(self, message: str = "Transcription failed", details: Optional[Any] = None):
        super().__init__(message=message, status_code=500, details=details)


class DatabaseError(AppException):
    """Database operation failed."""

    def __init__(self, message: str = "Database error", details: Optional[Any] = None):
        super().__init__(message=message, status_code=500, details=details)


class ServiceUnavailableError(AppException):
    """Service temporarily unavailable."""

    def __init__(self, service: str = "Service"):
        super().__init__(message=f"{service} is currently unavailable", status_code=503)
