"""HTML page routes (server rendered shells; data is fetched via /api)."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse

from app.config import get_settings
from app.dependencies import AuthContext, optional_user, require_page_user
from app.templating import render

router = APIRouter(tags=["pages"])
settings = get_settings()


@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(settings.static_dir / "favicon.svg")


@router.get("/login")
async def login_page(request: Request, user: AuthContext | None = Depends(optional_user)):
    if user:
        return RedirectResponse(url="/", status_code=303)
    return render(
        request,
        "login.html",
        {"configured": settings.is_configured},
    )


@router.get("/")
async def dashboard_page(request: Request, user: AuthContext = Depends(require_page_user)):
    return render(request, "dashboard.html", {"page": "dashboard", "email": user.email})


@router.get("/properties")
async def properties_page(request: Request, user: AuthContext = Depends(require_page_user)):
    return render(request, "properties.html", {"page": "properties", "email": user.email})


@router.get("/tenants")
async def tenants_page(request: Request, user: AuthContext = Depends(require_page_user)):
    return render(request, "tenants.html", {"page": "tenants", "email": user.email})


@router.get("/payments")
async def payments_page(request: Request, user: AuthContext = Depends(require_page_user)):
    return render(request, "payments.html", {"page": "payments", "email": user.email})


@router.get("/agreements")
async def agreements_page(request: Request, user: AuthContext = Depends(require_page_user)):
    return render(
        request,
        "agreements.html",
        {"page": "agreements", "email": user.email, "drive_configured": settings.drive_is_configured},
    )


@router.get("/settings")
async def settings_page(request: Request, user: AuthContext = Depends(require_page_user)):
    return render(request, "settings.html", {"page": "settings", "email": user.email})