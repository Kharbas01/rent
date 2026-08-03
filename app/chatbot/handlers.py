"""Read-only data lookups backing each chatbot intent.

Every function here only ever SELECTs, scoped to the signed-in owner via
the same `fetch_all`/`fetch_one` helpers (and Supabase RLS) the rest of the
app already uses — the chatbot cannot see another landlord's data, and it
cannot write/update/delete anything.
"""

from __future__ import annotations

from datetime import date

from supabase import Client

from app.crud import apply_due_rent_increases_bulk, fetch_all

TENANT_COLUMNS = (
    "id,name,rent_amount,agreement_end,due_day_of_month,is_active,"
    "rent_increase_percentage,agreement_duration_months,next_rent_increase_date,"
    "property_id,properties(name,type,address)"
)
PROPERTY_COLUMNS = "id,name,type,address,monthly_rent,status"
PAYMENT_COLUMNS = (
    "id,tenant_id,property_id,period_month,amount_due,amount_paid,status,"
    "payment_date,payment_method,notes,tenants(name),properties(name)"
)


def _tenants(client: Client, owner_id: str) -> list[dict]:
    rows = fetch_all(client, "tenants", owner_id, columns=TENANT_COLUMNS)
    return apply_due_rent_increases_bulk(client, owner_id, rows)


def _properties(client: Client, owner_id: str) -> list[dict]:
    return fetch_all(client, "properties", owner_id, columns=PROPERTY_COLUMNS)


def _payments(client: Client, owner_id: str) -> list[dict]:
    return fetch_all(
        client, "payments", owner_id, columns=PAYMENT_COLUMNS,
        order_by="period_month", descending=True,
    )


def known_tenant_names(client: Client, owner_id: str) -> list[str]:
    return [t["name"] for t in _tenants(client, owner_id) if t.get("name")]


def known_property_names(client: Client, owner_id: str) -> list[str]:
    return [p["name"] for p in _properties(client, owner_id) if p.get("name")]


def next_renewal(client: Client, owner_id: str) -> dict | None:
    today = date.today()
    upcoming = [
        t for t in _tenants(client, owner_id)
        if t.get("is_active") and t.get("agreement_end") and t["agreement_end"] >= today.isoformat()
    ]
    if not upcoming:
        return None
    upcoming.sort(key=lambda t: t["agreement_end"])
    t = upcoming[0]
    end = date.fromisoformat(t["agreement_end"])
    return {
        "tenant": t["name"],
        "property": (t.get("properties") or {}).get("name") or "—",
        "renewal_date": end,
        "days_remaining": (end - today).days,
    }


def pending_rent(client: Client, owner_id: str) -> dict:
    rows = [p for p in _payments(client, owner_id) if p.get("status") != "Paid"]
    items = []
    total = 0.0
    for p in rows:
        outstanding = max(float(p.get("amount_due") or 0) - float(p.get("amount_paid") or 0), 0.0)
        if outstanding <= 0:
            continue
        total += outstanding
        items.append({
            "tenant": (p.get("tenants") or {}).get("name") or "Unknown",
            "property": (p.get("properties") or {}).get("name") or "—",
            "amount": outstanding,
            "period_month": p.get("period_month"),
        })
    items.sort(key=lambda r: r["amount"], reverse=True)
    return {"items": items[:8], "total": round(total, 2), "count": len(items)}


def vacant_properties(client: Client, owner_id: str) -> list[dict]:
    return [
        {
            "name": p["name"],
            "type": p.get("type") or "—",
            "location": p.get("address") or "—",
            "rent": float(p.get("monthly_rent") or 0),
        }
        for p in _properties(client, owner_id)
        if (p.get("status") or "").lower() != "occupied"
    ]


def monthly_income(client: Client, owner_id: str) -> dict:
    today = date.today()
    current_key = today.strftime("%Y-%m")
    rows = [p for p in _payments(client, owner_id) if (p.get("period_month") or "")[:7] == current_key]
    due = sum(float(p.get("amount_due") or 0) for p in rows)
    paid = sum(float(p.get("amount_paid") or 0) for p in rows)
    pending = max(due - paid, 0.0)
    pct = round((paid / due) * 100) if due else 0
    return {
        "total_due": round(due, 2),
        "collected": round(paid, 2),
        "pending": round(pending, 2),
        "collection_pct": pct,
    }


def payment_history(client: Client, owner_id: str, tenant_name: str | None, limit: int = 12) -> dict:
    rows = _payments(client, owner_id)
    if tenant_name:
        rows = [p for p in rows if (p.get("tenants") or {}).get("name") == tenant_name]
    rows = rows[:limit]
    items = [
        {
            "date": p.get("payment_date"),
            "amount": float(p.get("amount_paid") or 0),
            "method": p.get("payment_method") or "—",
            "reference": (p.get("id") or "")[:8],
            "status": p.get("status"),
        }
        for p in rows
    ]
    return {"tenant": tenant_name, "items": items}


def expiring_agreements(client: Client, owner_id: str) -> list[dict]:
    today = date.today()
    current_key = today.strftime("%Y-%m")
    out = []
    for t in _tenants(client, owner_id):
        end = t.get("agreement_end")
        if not t.get("is_active") or not end:
            continue
        if end[:7] != current_key:
            continue
        end_date = date.fromisoformat(end)
        out.append({
            "tenant": t["name"],
            "property": (t.get("properties") or {}).get("name") or "—",
            "expiry_date": end_date,
            "days_remaining": (end_date - today).days,
            "status": "Expired" if end_date < today else "Expiring",
        })
    out.sort(key=lambda r: r["expiry_date"])
    return out


def overdue_rent(client: Client, owner_id: str) -> list[dict]:
    today = date.today()
    current_month_start = today.replace(day=1)
    out = []
    for p in _payments(client, owner_id):
        if p.get("status") == "Paid":
            continue
        period = p.get("period_month")
        if not period:
            continue
        period_date = date.fromisoformat(period)
        if period_date >= current_month_start:
            continue  # not yet overdue, just due this month
        outstanding = max(float(p.get("amount_due") or 0) - float(p.get("amount_paid") or 0), 0.0)
        if outstanding <= 0:
            continue
        out.append({
            "tenant": (p.get("tenants") or {}).get("name") or "Unknown",
            "property": (p.get("properties") or {}).get("name") or "—",
            "amount": outstanding,
            "overdue_days": (today - period_date).days,
        })
    out.sort(key=lambda r: r["overdue_days"], reverse=True)
    return out[:8]


def property_info(client: Client, owner_id: str, property_name: str | None) -> dict | None:
    props = _properties(client, owner_id)
    if property_name:
        props = [p for p in props if p["name"] == property_name]
    if not props:
        return None
    prop = props[0]

    tenants = _tenants(client, owner_id)
    current_tenant = next(
        (t for t in tenants if t.get("property_id") == prop["id"] and t.get("is_active")), None
    )
    return {
        "name": prop["name"],
        "type": prop.get("type") or "—",
        "location": prop.get("address") or "—",
        "status": prop.get("status") or "—",
        "monthly_rent": float(prop.get("monthly_rent") or 0),
        "tenant": current_tenant["name"] if current_tenant else None,
        "current_rent": float(current_tenant["rent_amount"]) if current_tenant else None,
        "agreement_end": current_tenant.get("agreement_end") if current_tenant else None,
    }
