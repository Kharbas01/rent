"""Agreement document management: upload, store on Google Drive, track status."""

import re
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response

from app import google_drive
from app.config import get_settings
from app.crud import delete_row, fetch_all, fetch_one, insert_row, update_row
from app.dependencies import AuthContext, require_api_user
from app.errors import AppError, bad_request
from app.pdf_utils import images_to_pdf

router = APIRouter(prefix="/api/agreements", tags=["agreements"])
settings = get_settings()

COLUMNS = (
    "id,property_id,tenant_id,file_name,original_file_name,drive_file_id,drive_link,"
    "file_size,page_count,agreement_start,agreement_end,notes,created_at,updated_at,"
    "properties(name),tenants(name)"
)

ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


def _status_for(agreement_end: str | None) -> str:
    if not agreement_end:
        return "Active"
    end = date.fromisoformat(agreement_end)
    today = date.today()
    days_left = (end - today).days
    if days_left < 0:
        return "Expired"
    if days_left <= 30:
        return "Expiring Soon"
    return "Active"


def _with_status(row: dict) -> dict:
    row["status"] = _status_for(row.get("agreement_end"))
    return row


def _slugify(value: str) -> str:
    value = re.sub(r"[^\w\s-]", "", value or "").strip()
    value = re.sub(r"[\s]+", "_", value)
    return value or "Unknown"


async def _build_filename(
    client, owner_id: str, property_name: str | None, tenant_name: str | None,
    start: date | None, end: date | None, extension: str,
) -> str:
    if property_name or tenant_name:
        parts = [_slugify(property_name or "Property"), _slugify(tenant_name or "Tenant")]
        if start:
            parts.append(start.isoformat())
        if end:
            parts.append(end.isoformat())
        base = "_".join(parts)
    else:
        base = f"Agreement_{datetime.now().strftime('%Y-%m-%d_%H-%M')}"

    filename = f"{base}{extension}"

    # Avoid duplicate names for this owner: Base.pdf, Base_2.pdf, Base_3.pdf ...
    existing = (
        client.table("agreements")
        .select("file_name")
        .eq("owner_id", owner_id)
        .ilike("file_name", f"{base}%{extension}")
        .execute()
        .data
        or []
    )
    existing_names = {row["file_name"] for row in existing}
    if filename not in existing_names:
        return filename

    counter = 2
    while f"{base}_{counter}{extension}" in existing_names:
        counter += 1
    return f"{base}_{counter}{extension}"


def _validate_upload(content: bytes, content_type: str) -> str:
    if content_type not in ALLOWED_TYPES:
        raise bad_request("Only PDF, JPG and PNG files are supported.")
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.max_upload_mb:
        raise bad_request(f"File is too large. Maximum allowed size is {settings.max_upload_mb} MB.")
    if len(content) == 0:
        raise bad_request("The uploaded file is empty.")
    return ALLOWED_TYPES[content_type]


@router.get("")
async def list_agreements(
    search: str | None = Query(default=None, max_length=80),
    status: str | None = Query(default=None),
    property_id: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    user: AuthContext = Depends(require_api_user),
):
    filters: dict = {}
    if property_id:
        filters["property_id"] = property_id
    if tenant_id:
        filters["tenant_id"] = tenant_id

    rows = fetch_all(
        user.client,
        "agreements",
        user.user_id,
        columns=COLUMNS,
        search=search,
        search_columns=("file_name", "original_file_name"),
        filters=filters,
    )
    rows = [_with_status(r) for r in rows]
    if status and status != "all":
        rows = [r for r in rows if r["status"] == status]

    return {"items": rows, "count": len(rows)}


@router.get("/{agreement_id}")
async def get_agreement(agreement_id: str, user: AuthContext = Depends(require_api_user)):
    row = fetch_one(user.client, "agreements", user.user_id, agreement_id, columns=COLUMNS)
    return _with_status(row)


@router.post("", status_code=201)
async def create_agreement(
    file: UploadFile | None = File(default=None),
    pages: list[UploadFile] | None = File(default=None),
    property_id: str | None = Form(default=None),
    tenant_id: str | None = Form(default=None),
    agreement_start: str | None = Form(default=None),
    agreement_end: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    user: AuthContext = Depends(require_api_user),
):
    if not file and not pages:
        raise bad_request("Please attach a file or capture at least one page.")

    page_count = 1
    if pages:
        image_bytes: list[bytes] = []
        for page in pages:
            raw = await page.read()
            if (page.content_type or "") not in ("image/jpeg", "image/png"):
                raise bad_request("Captured pages must be JPG or PNG images.")
            if not raw:
                raise bad_request("One of the captured pages is empty.")
            image_bytes.append(raw)
        content = images_to_pdf(image_bytes)
        content_type = "application/pdf"
        page_count = len(image_bytes)
        original_filename = f"{page_count}-page-scan.pdf"
    else:
        content = await file.read()
        content_type = file.content_type or ""
        original_filename = file.filename

    extension = _validate_upload(content, content_type)

    property_name = None
    tenant_name = None
    if property_id:
        prop = fetch_one(user.client, "properties", user.user_id, property_id, columns="name")
        property_name = prop.get("name")
    if tenant_id:
        tenant = fetch_one(user.client, "tenants", user.user_id, tenant_id, columns="name")
        tenant_name = tenant.get("name")

    start_date = date.fromisoformat(agreement_start) if agreement_start else None
    end_date = date.fromisoformat(agreement_end) if agreement_end else None
    if start_date and end_date and end_date < start_date:
        raise bad_request("Agreement end date must be after the start date.")

    final_name = await _build_filename(
        user.client, user.user_id, property_name, tenant_name, start_date, end_date, extension
    )

    drive_result = google_drive.upload_bytes(content, final_name, content_type or "application/pdf")

    data = {
        "owner_id": user.user_id,
        "property_id": property_id or None,
        "tenant_id": tenant_id or None,
        "file_name": final_name,
        "original_file_name": original_filename,
        "drive_file_id": drive_result["drive_file_id"],
        "drive_link": drive_result["drive_link"],
        "file_size": len(content),
        "page_count": max(page_count, 1),
        "agreement_start": start_date.isoformat() if start_date else None,
        "agreement_end": end_date.isoformat() if end_date else None,
        "notes": (notes or "").strip() or None,
    }
    created = insert_row(user.client, "agreements", data)
    return _with_status(created)


@router.put("/{agreement_id}")
async def update_agreement_meta(
    agreement_id: str,
    property_id: str | None = Form(default=None),
    tenant_id: str | None = Form(default=None),
    agreement_start: str | None = Form(default=None),
    agreement_end: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    user: AuthContext = Depends(require_api_user),
):
    """Update agreement metadata only (property/tenant link, dates, notes)."""
    start_date = date.fromisoformat(agreement_start) if agreement_start else None
    end_date = date.fromisoformat(agreement_end) if agreement_end else None
    if start_date and end_date and end_date < start_date:
        raise bad_request("Agreement end date must be after the start date.")

    data = {
        "property_id": property_id or None,
        "tenant_id": tenant_id or None,
        "agreement_start": start_date.isoformat() if start_date else None,
        "agreement_end": end_date.isoformat() if end_date else None,
        "notes": (notes or "").strip() or None,
    }
    updated = update_row(user.client, "agreements", user.user_id, agreement_id, data)
    return _with_status(updated)


@router.put("/{agreement_id}/file")
async def replace_agreement_file(
    agreement_id: str, file: UploadFile = File(...), user: AuthContext = Depends(require_api_user)
):
    """Replace the stored document, keeping the same metadata row."""
    existing = fetch_one(
        user.client, "agreements", user.user_id, agreement_id,
        columns="id,drive_file_id,file_name",
    )
    content = await file.read()
    extension = _validate_upload(content, file.content_type or "")

    # Reuse the existing filename's base so history stays recognisable.
    base = existing["file_name"].rsplit(".", 1)[0]
    new_name = f"{base}{extension}"

    drive_result = google_drive.upload_bytes(content, new_name, file.content_type or "application/pdf")
    google_drive.delete_file(existing.get("drive_file_id"))

    data = {
        "file_name": new_name,
        "original_file_name": file.filename,
        "drive_file_id": drive_result["drive_file_id"],
        "drive_link": drive_result["drive_link"],
        "file_size": len(content),
    }
    updated = update_row(user.client, "agreements", user.user_id, agreement_id, data)
    return _with_status(updated)


@router.get("/{agreement_id}/download")
async def download_agreement(agreement_id: str, user: AuthContext = Depends(require_api_user)):
    row = fetch_one(
        user.client, "agreements", user.user_id, agreement_id,
        columns="drive_file_id,file_name",
    )
    if not row.get("drive_file_id"):
        raise AppError("This agreement has no file stored yet.")
    content, mime_type = google_drive.download_bytes(row["drive_file_id"])
    return Response(
        content=content,
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{row["file_name"]}"'},
    )


@router.delete("/{agreement_id}")
async def delete_agreement(agreement_id: str, user: AuthContext = Depends(require_api_user)):
    existing = fetch_one(user.client, "agreements", user.user_id, agreement_id, columns="drive_file_id")
    google_drive.delete_file(existing.get("drive_file_id"))
    delete_row(user.client, "agreements", user.user_id, agreement_id)
    return {"ok": True}