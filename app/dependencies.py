"""Request dependencies: session handling and authentication."""

from dataclasses import dataclass, field
from typing import Any

from fastapi import Request, Response
from supabase import Client

from app.config import get_settings
from app.errors import AuthRequiredError, unauthorized
from app.supabase_client import build_client

ACCESS_COOKIE = "rms_access_token"
REFRESH_COOKIE = "rms_refresh_token"
ACCESS_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


@dataclass
class AuthContext:
    """Everything a route needs to talk to Supabase as the current user."""

    user_id: str
    email: str
    access_token: str
    client: Client
    raw_user: Any = field(default=None, repr=False)


def set_session_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    settings = get_settings()
    common = {
        "httponly": True,
        "samesite": "lax",
        "secure": settings.cookie_secure,
        "path": "/",
        "max_age": ACCESS_MAX_AGE,
    }
    response.set_cookie(ACCESS_COOKIE, access_token, **common)
    response.set_cookie(REFRESH_COOKIE, refresh_token, **common)


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")


def _resolve_context(request: Request, response: Response) -> AuthContext | None:
    """Validate cookies, refreshing the session when the token expired."""
    access_token = request.cookies.get(ACCESS_COOKIE)
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not access_token:
        return None

    client = build_client()
    user = None
    active_token = access_token

    try:
        user = client.auth.get_user(access_token).user
    except Exception:
        user = None

    if user is None and refresh_token:
        try:
            result = client.auth.set_session(access_token, refresh_token)
            session = getattr(result, "session", None)
            user = getattr(result, "user", None) or (session.user if session else None)
            if session and session.access_token:
                active_token = session.access_token
                set_session_cookies(response, session.access_token, session.refresh_token)
        except Exception:
            user = None

    if user is None:
        clear_session_cookies(response)
        return None

    client.postgrest.auth(active_token)
    return AuthContext(
        user_id=str(user.id),
        email=user.email or "",
        access_token=active_token,
        client=client,
        raw_user=user,
    )


def optional_user(request: Request, response: Response) -> AuthContext | None:
    """Returns the user when signed in, otherwise None (never raises)."""
    try:
        return _resolve_context(request, response)
    except Exception:
        return None


def require_api_user(request: Request, response: Response) -> AuthContext:
    """Dependency for /api routes -> raises 401 JSON when signed out."""
    context = _resolve_context(request, response)
    if context is None:
        raise unauthorized()
    return context


def require_page_user(request: Request, response: Response) -> AuthContext:
    """Dependency for HTML pages -> redirects to /login when signed out."""
    context = _resolve_context(request, response)
    if context is None:
        raise AuthRequiredError()
    return context
