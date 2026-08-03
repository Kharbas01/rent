"""Property CRUD endpoints."""

from fastapi import APIRouter, Depends, Query

from app.crud import delete_row, fetch_all, fetch_one, insert_row, update_row
from app.dependencies import AuthContext, require_api_user
from app.errors import bad_request
from app.schemas import PropertyIn

router = APIRouter(prefix="/api/properties", tags=["properties"])

COLUMNS = "id,name,type,address,monthly_rent,status,notes,created_at"


@router.get("")
async def list_properties(
    search: str | None = Query(default=None, max_length=80),
    status: str | None = Query(default=None),
    user: AuthContext = Depends(require_api_user),
):
    rows = fetch_all(
        user.client,
        "properties",
        user.user_id,
        columns=COLUMNS,
        search=search,
        search_columns=("name", "address", "type"),
        filters={"status": status},
    )
    return {"items": rows, "count": len(rows)}


@router.get("/{property_id}")
async def get_property(property_id: str, user: AuthContext = Depends(require_api_user)):
    return fetch_one(user.client, "properties", user.user_id, property_id, columns=COLUMNS)


@router.post("", status_code=201)
async def create_property(payload: PropertyIn, user: AuthContext = Depends(require_api_user)):
    data = payload.model_dump()
    data["owner_id"] = user.user_id
    return insert_row(user.client, "properties", data)


@router.put("/{property_id}")
async def update_property(
    property_id: str, payload: PropertyIn, user: AuthContext = Depends(require_api_user)
):
    return update_row(user.client, "properties", user.user_id, property_id, payload.model_dump())


@router.delete("/{property_id}")
async def delete_property(property_id: str, user: AuthContext = Depends(require_api_user)):
    linked = (
        user.client.table("tenants")
        .select("id")
        .eq("owner_id", user.user_id)
        .eq("property_id", property_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if linked.data:
        raise bad_request(
            "This property has an active tenant. Move or deactivate the tenant first."
        )

    delete_row(user.client, "properties", user.user_id, property_id)
    return {"ok": True}
