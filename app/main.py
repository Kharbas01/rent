"""FastAPI application factory and global error handling."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.config import get_settings
from app.errors import AppError, AuthRequiredError
from app.routers import (
    agreements,
    auth,
    chatbot,
    dashboard,
    pages,
    payments,
    properties,
    search,
    settings as settings_router,
    tenants,
)
from app.templating import render

settings = get_settings()

app = FastAPI(
    title=f"{settings.app_name} - Rent Management System",
    version=__version__,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(properties.router)
app.include_router(tenants.router)
app.include_router(payments.router)
app.include_router(agreements.router)
app.include_router(search.router)
app.include_router(settings_router.router)
app.include_router(chatbot.router)


def _is_api(request: Request) -> bool:
    return request.url.path.startswith("/api")


@app.exception_handler(AuthRequiredError)
async def auth_required_handler(request: Request, exc: AuthRequiredError):
    if _is_api(request):
        return JSONResponse({"detail": "Not authenticated."}, status_code=401)
    return RedirectResponse(url="/login", status_code=303)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    if _is_api(request):
        return JSONResponse({"detail": exc.message}, status_code=exc.status_code)
    return render(request, "login.html", {"error": exc.message})


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", [])[1:]) or "input"
    message = first.get("msg", "Invalid input.").replace("Value error, ", "")
    return JSONResponse({"detail": f"{field}: {message}"}, status_code=422)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if _is_api(request):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    if exc.status_code == 401:
        return RedirectResponse(url="/login", status_code=303)
    if exc.status_code == 404:
        return RedirectResponse(url="/", status_code=303)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):  # pragma: no cover
    message = str(exc) if settings.debug else "Something went wrong on the server."
    if _is_api(request):
        return JSONResponse({"detail": message}, status_code=500)
    return render(request, "login.html", {"error": message})


@app.get("/api/health", tags=["system"])
async def health():
    return {
        "status": "ok",
        "version": __version__,
        "supabase_configured": settings.is_configured,
        "drive_configured": settings.drive_is_configured,
    }