"""Global search across properties and tenants."""

from fastapi import APIRouter, Depends, Query

from app.crud import fetch_all
from app.dependencies import AuthContext, require_api_user

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
async def global_search(
    q: str = Query(min_length=1, max_length=80),
    user: AuthContext = Depends(require_api_user),
):
    properties = fetch_all(
        user.client,
        "properties",
        user.user_id,
        columns="id,name,type,address,status,monthly_rent",
        search=q,
        search_columns=("name", "address", "type"),
        limit=6,
    )
    tenants = fetch_all(
        user.client,
        "tenants",
        user.user_id,
        columns="id,name,phone,email,rent_amount,is_active,properties(name)",
        search=q,
        search_columns=("name", "phone", "email"),
        limit=6,
    )
    return {
        "query": q,
        "properties": properties,
        "tenants": tenants,
        "total": len(properties) + len(tenants),
    }
