"""Custom exceptions and shared error helpers."""

from fastapi import HTTPException, status


class AppError(Exception):
    """Base error carrying a user friendly message."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AuthRequiredError(Exception):
    """Raised when a browser page requires a signed-in user."""


class NotConfiguredError(Exception):
    """Raised when Supabase credentials are missing."""


def unauthorized(message: str = "Your session has expired. Please sign in again.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)


def not_found(message: str = "Record not found.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)


def bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def clean_supabase_error(exc: Exception) -> str:
    """Turn a raw Supabase/PostgREST exception into a readable message."""
    raw = str(exc) or exc.__class__.__name__
    lowered = raw.lower()

    if "invalid login credentials" in lowered:
        return "Invalid email or password."
    if "email not confirmed" in lowered:
        return "Please confirm your email address before signing in."
    if "user already registered" in lowered:
        return "An account with this email already exists."
    if "password should be at least" in lowered:
        return "Password is too short. Use at least 6 characters."
    if "duplicate key" in lowered:
        return "This record already exists."
    if "violates foreign key" in lowered:
        return "Related record is missing or already deleted."
    if "row-level security" in lowered or "permission denied" in lowered:
        return "You do not have permission to perform this action."
    if "relation" in lowered and "does not exist" in lowered:
        return "Database tables are missing. Run database/schema.sql in Supabase."
    if len(raw) > 220:
        return raw[:220] + "..."
    return raw
