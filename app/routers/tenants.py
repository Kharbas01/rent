"""Tenant CRUD endpoints."""

from fastapi import APIRouter, Depends, Query

from app.crud import (
    apply_due_rent_increases,
    apply_due_rent_increases_bulk,
    compute_next_increase_date,
    delete_row,
    fetch_all,
    fetch_one,
    insert_row,
    property_has_active_tenant,
    set_property_status,
    update_row,
)
from app.dependencies import AuthContext, require_api_user
from app.errors import bad_request
from app.schemas import TenantIn

router = APIRouter(prefix="/api/tenants", tags=["tenants"])

COLUMNS = (
    "id,name,phone,email,property_id,rent_amount,base_rent_amount,security_deposit,"
    "agreement_start,agreement_end,due_day_of_month,agreement_duration_months,"
    "rent_increase_percentage,next_rent_increase_date,is_active,notes,created_at,"
    "properties(name,type)"
)


def _serialise(payload: TenantIn) -> dict:
    data = payload.model_dump()
    data["email"] = str(data["email"]) if data.get("email") else None
    for key in ("agreement_start", "agreement_end"):
        data[key] = data[key].isoformat() if data.get(key) else None
    return data


def _with_next_increase_date(data: dict) -> dict:
    """Attach the computed next-increase date whenever the agreement allows it."""
    next_due = compute_next_increase_date(payload_date(data), data.get("agreement_duration_months"))
    data["next_rent_increase_date"] = next_due.isoformat() if next_due else None
    return data


def payload_date(data: dict):
    from datetime import date as date_cls

    value = data.get("agreement_start")
    return date_cls.fromisoformat(value) if value else None


@router.get("")
async def list_tenants(
    search: str | None = Query(default=None, max_length=80),
    active: str | None = Query(default=None),
    user: AuthContext = Depends(require_api_user),
):
    filters = {}
    if active in {"true", "false"}:
        filters["is_active"] = active == "true"

    rows = fetch_all(
        user.client,
        "tenants",
        user.user_id,
        columns=COLUMNS,
        search=search,
        search_columns=("name", "phone", "email"),
        filters=filters,
    )
    rows = apply_due_rent_increases_bulk(user.client, user.user_id, rows)
    return {"items": rows, "count": len(rows)}


@router.get("/{tenant_id}")
async def get_tenant(tenant_id: str, user: AuthContext = Depends(require_api_user)):
    tenant = fetch_one(user.client, "tenants", user.user_id, tenant_id, columns=COLUMNS)
    return apply_due_rent_increases(user.client, user.user_id, tenant)


@router.post("", status_code=201)
async def create_tenant(payload: TenantIn, user: AuthContext = Depends(require_api_user)):
    data = _serialise(payload)
    if data.get("property_id") and data["is_active"]:
        if property_has_active_tenant(user.client, user.user_id, data["property_id"]):
            raise bad_request("That property already has an active tenant.")

    # The rent submitted when a tenant is first created is always the
    # base/original rent. It is never overwritten by later automatic increases.
    data["base_rent_amount"] = data["rent_amount"]
    data = _with_next_increase_date(data)

    data["owner_id"] = user.user_id
    created = insert_row(user.client, "tenants", data)

    if created.get("property_id") and created.get("is_active"):
        set_property_status(user.client, user.user_id, created["property_id"], "Occupied")
    return created


@router.put("/{tenant_id}")
async def update_tenant(
    tenant_id: str, payload: TenantIn, user: AuthContext = Depends(require_api_user)
):
    existing = fetch_one(
        user.client,
        "tenants",
        user.user_id,
        tenant_id,
        columns="id,property_id,is_active,base_rent_amount,agreement_start,agreement_duration_months",
    )
    data = _serialise(payload)

    # Never overwrite the original base rent once it has been set. Only
    # backfill it (for older rows created before this field existed).
    data["base_rent_amount"] = existing.get("base_rent_amount") or data["rent_amount"]

    # Recompute the next increase date only when the agreement terms that
    # drive it have actually changed, so a manually-adjusted rent (e.g. a
    # correction) does not silently reset the schedule.
    if (
        data.get("agreement_start") != existing.get("agreement_start")
        or data.get("agreement_duration_months") != existing.get("agreement_duration_months")
    ):
        data = _with_next_increase_date(data)

    if data.get("property_id") and data["is_active"]:
        if property_has_active_tenant(
            user.client, user.user_id, data["property_id"], exclude_tenant_id=tenant_id
        ):
            raise bad_request("That property already has an active tenant.")

    updated = update_row(user.client, "tenants", user.user_id, tenant_id, data)

    old_property = existing.get("property_id")
    new_property = updated.get("property_id")

    if old_property and old_property != new_property:
        if not property_has_active_tenant(user.client, user.user_id, old_property, tenant_id):
            set_property_status(user.client, user.user_id, old_property, "Vacant")

    if new_property:
        status = "Occupied" if updated.get("is_active") else "Vacant"
        if status == "Vacant" and property_has_active_tenant(
            user.client, user.user_id, new_property, tenant_id
        ):
            status = "Occupied"
        set_property_status(user.client, user.user_id, new_property, status)

    return updated


@router.get("/{tenant_id}/rent-history")
async def tenant_rent_history(tenant_id: str, user: AuthContext = Depends(require_api_user)):
    # Confirms the tenant belongs to this user (raises 404 otherwise) and
    # applies any increases that just came due before returning history.
    tenant = fetch_one(user.client, "tenants", user.user_id, tenant_id, columns=COLUMNS)
    apply_due_rent_increases(user.client, user.user_id, tenant)

    rows = fetch_all(
        user.client,
        "rent_history",
        user.user_id,
        columns="id,previous_rent,new_rent,increase_percentage,increase_date,created_at",
        order_by="increase_date",
        filters={"tenant_id": tenant_id},
    )
    return {"items": rows, "count": len(rows)}


@router.delete("/{tenant_id}")
async def delete_tenant(tenant_id: str, user: AuthContext = Depends(require_api_user)):
    existing = fetch_one(user.client, "tenants", user.user_id, tenant_id, columns="id,property_id")
    delete_row(user.client, "tenants", user.user_id, tenant_id)

    property_id = existing.get("property_id")
    if property_id and not property_has_active_tenant(user.client, user.user_id, property_id):
        set_property_status(user.client, user.user_id, property_id, "Vacant")
    return {"ok": True}