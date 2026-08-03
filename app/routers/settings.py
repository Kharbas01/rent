"""Profile settings endpoints."""

from fastapi import APIRouter, Depends

from app.dependencies import AuthContext, require_api_user
from app.errors import AppError, clean_supabase_error
from app.schemas import PasswordIn, ProfileIn

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/profile")
async def get_profile(user: AuthContext = Depends(require_api_user)):
    try:
        result = (
            user.client.table("profiles").select("*").eq("id", user.user_id).limit(1).execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise AppError(clean_supabase_error(exc)) from exc

    rows = result.data or []
    if rows:
        return rows[0]

    # Create the profile row on first visit if the DB trigger did not run.
    payload = {"id": user.user_id, "full_name": user.email.split("@")[0], "currency": "INR"}
    try:
        created = user.client.table("profiles").insert(payload).execute()
        return (created.data or [payload])[0]
    except Exception:  # noqa: BLE001
        return payload


@router.put("/profile")
async def update_profile(payload: ProfileIn, user: AuthContext = Depends(require_api_user)):
    data = payload.model_dump()
    data["id"] = user.user_id
    try:
        result = user.client.table("profiles").upsert(data, on_conflict="id").execute()
    except Exception as exc:  # noqa: BLE001
        raise AppError(clean_supabase_error(exc)) from exc
    return (result.data or [data])[0]


@router.put("/password")
async def change_password(payload: PasswordIn, user: AuthContext = Depends(require_api_user)):
    try:
        user.client.auth.set_session(user.access_token, user.access_token)
    except Exception:  # noqa: BLE001 - set_session may reject a reused token
        pass

    try:
        user.client.auth.update_user({"password": payload.new_password})
    except Exception as exc:  # noqa: BLE001
        raise AppError(clean_supabase_error(exc)) from exc
    return {"ok": True, "message": "Password updated successfully."}
