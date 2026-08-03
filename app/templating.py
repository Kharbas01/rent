"""Shared Jinja2 environment."""

from fastapi.templating import Jinja2Templates

from app.config import get_settings

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.templates_dir))
templates.env.globals["app_name"] = settings.app_name
templates.env.globals["allow_signup"] = settings.allow_signup


def render(request, template_name: str, context: dict | None = None):
    data = {"request": request}
    data.update(context or {})
    return templates.TemplateResponse(template_name, data)
