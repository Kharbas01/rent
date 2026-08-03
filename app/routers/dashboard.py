"""Dashboard aggregation endpoint."""

from collections import OrderedDict
from datetime import date

from fastapi import APIRouter, Depends

from app.crud import apply_due_rent_increases_bulk, fetch_all
from app.dependencies import AuthContext, require_api_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _month_key(value: str | None) -> str:
    return (value or "")[:7]


def _shift_month(anchor: date, months_back: int) -> str:
    total = anchor.year * 12 + (anchor.month - 1) - months_back
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


@router.get("/summary")
async def summary(user: AuthContext = Depends(require_api_user)):
    client, owner = user.client, user.user_id

    properties = fetch_all(
        client, "properties", owner, columns="id,name,status,monthly_rent", order_by="created_at"
    )
    tenants = fetch_all(
        client,
        "tenants",
        owner,
        columns="id,name,is_active,agreement_end,rent_amount,next_rent_increase_date,"
        "agreement_duration_months",
        order_by="created_at",
    )
    # Make sure any rent increases that came due are applied before we sum
    # rent, so the dashboard reflects the tenant's *current* rent, not a
    # stale figure copied from the property record.
    tenants = apply_due_rent_increases_bulk(client, owner, tenants)
    payments = fetch_all(
        client,
        "payments",
        owner,
        columns="id,amount_due,amount_paid,status,period_month,payment_date,payment_method,"
        "tenants(name),properties(name)",
        order_by="period_month",
    )

    total_properties = len(properties)
    occupied = sum(1 for p in properties if p.get("status") == "Occupied")
    vacant = total_properties - occupied
    # Use each active tenant's actual current rent (kept up to date by
    # apply_due_rent_increases_bulk above) rather than the property's static
    # monthly_rent field, so edits and auto rent-increases show up here.
    monthly_rent = sum(float(t.get("rent_amount") or 0) for t in tenants if t.get("is_active"))
    active_tenants = sum(1 for t in tenants if t.get("is_active"))

    pending_rent = 0.0
    collected_this_month = 0.0
    today = date.today()
    current_key = today.strftime("%Y-%m")

    for row in payments:
        due = float(row.get("amount_due") or 0)
        paid = float(row.get("amount_paid") or 0)
        outstanding = max(due - paid, 0.0)
        pending_rent += outstanding
        if _month_key(row.get("period_month")) == current_key:
            collected_this_month += paid

    # Last 6 months collection trend
    trend_keys = [_shift_month(today, offset) for offset in range(5, -1, -1)]
    trend = OrderedDict((key, 0.0) for key in trend_keys)
    for row in payments:
        key = _month_key(row.get("period_month"))
        if key in trend:
            trend[key] += float(row.get("amount_paid") or 0)

    recent = sorted(
        [r for r in payments if r.get("payment_date")],
        key=lambda r: r.get("payment_date") or "",
        reverse=True,
    )[:5]

    overdue = [
        {
            "id": r["id"],
            "tenant": (r.get("tenants") or {}).get("name") or "Unknown tenant",
            "property": (r.get("properties") or {}).get("name"),
            "period_month": r.get("period_month"),
            "outstanding": max(float(r.get("amount_due") or 0) - float(r.get("amount_paid") or 0), 0.0),
        }
        for r in payments
        if r.get("status") != "Paid"
    ]
    overdue.sort(key=lambda r: r["period_month"] or "")

    return {
        "stats": {
            "total_properties": total_properties,
            "occupied_properties": occupied,
            "vacant_properties": vacant,
            "active_tenants": active_tenants,
            "monthly_rent": round(monthly_rent, 2),
            "pending_rent": round(pending_rent, 2),
            "collected_this_month": round(collected_this_month, 2),
            "occupancy_rate": round((occupied / total_properties) * 100) if total_properties else 0,
        },
        "trend": [{"month": key, "amount": round(value, 2)} for key, value in trend.items()],
        "recent_payments": [
            {
                "id": r["id"],
                "tenant": (r.get("tenants") or {}).get("name") or "Unknown tenant",
                "property": (r.get("properties") or {}).get("name"),
                "amount_paid": float(r.get("amount_paid") or 0),
                "payment_date": r.get("payment_date"),
                "payment_method": r.get("payment_method"),
                "status": r.get("status"),
            }
            for r in recent
        ],
        "overdue": overdue[:5],
    }
