"""Authentication endpoints backed by Supabase Auth."""

from fastapi import APIRouter, Depends, Response

from app.config import get_settings
from app.dependencies import (
    AuthContext,
    clear_session_cookies,
    require_api_user,
    set_session_cookies,
)
from app.errors import AppError, bad_request, clean_supabase_error
from app.schemas import LoginIn, SignupIn
from app.supabase_client import build_client

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


@router.post("/login")
async def login(payload: LoginIn, response: Response):
    client = build_client()
    try:
        result = client.auth.sign_in_with_password(
            {"email": payload.email, "password": payload.password}
        )
    except Exception as exc:  # noqa: BLE001
        raise AppError(clean_supabase_error(exc), status_code=401) from exc

    session = result.session
    if not session or not session.access_token:
        raise AppError("Sign in failed. Please try again.", status_code=401)

    set_session_cookies(response, session.access_token, session.refresh_token)
    return {"ok": True, "email": result.user.email if result.user else payload.email}


@router.post("/signup")
async def signup(payload: SignupIn):
    if not settings.allow_signup:
        raise bad_request("Account creation is disabled. Ask the administrator for access.")

    client = build_client()
    try:
        result = client.auth.sign_up(
            {
                "email": payload.email,
                "password": payload.password,
                "options": {"data": {"full_name": payload.full_name}},
            }
        )
    except Exception as exc:  # noqa: BLE001
        raise AppError(clean_supabase_error(exc)) from exc

    needs_confirmation = result.session is None
    return {
        "ok": True,
        "needs_confirmation": needs_confirmation,
        "message": (
            "Account created. Check your inbox to confirm your email, then sign in."
            if needs_confirmation
            else "Account created. You can sign in now."
        ),
    }


@router.post("/logout")
async def logout(response: Response):
    clear_session_cookies(response)
    return {"ok": True}


@router.get("/me")
async def me(user: AuthContext = Depends(require_api_user)):
    profile = {}
    try:
        result = (
            user.client.table("profiles").select("*").eq("id", user.user_id).limit(1).execute()
        )
        profile = (result.data or [{}])[0]
    except Exception:  # noqa: BLE001 - profile row may not exist yet
        profile = {}

    return {
        "id": user.user_id,
        "email": user.email,
        "full_name": profile.get("full_name") or user.email.split("@")[0],
        "company_name": profile.get("company_name"),
        "phone": profile.get("phone"),
        "currency": profile.get("currency") or "INR",
    }
