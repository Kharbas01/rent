"""Rent payment endpoints: history, invoices and marking rent as paid."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.crud import (
    delete_row,
    fetch_all,
    fetch_one,
    insert_row,
    month_to_date,
    payment_status,
    update_row,
)
from app.dependencies import AuthContext, require_api_user
from app.errors import AppError, bad_request, clean_supabase_error
from app.reports import build_report_pdf, period_start
from app.schemas import GenerateIn, MarkPaidIn, PaymentIn

router = APIRouter(prefix="/api/payments", tags=["payments"])

COLUMNS = (
    "id,tenant_id,property_id,period_month,amount_due,amount_paid,status,"
    "payment_date,payment_method,payment_type,payment_type_note,notes,created_at,"
    "tenants(name,phone,due_day_of_month),properties(name)"
)


@router.get("")
async def list_payments(
    search: str | None = Query(default=None, max_length=80),
    status: str | None = Query(default=None),
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    user: AuthContext = Depends(require_api_user),
):
    query = (
        user.client.table("payments")
        .select(COLUMNS)
        .eq("owner_id", user.user_id)
        .order("period_month", desc=True)
        .order("created_at", desc=True)
    )
    if status and status != "all":
        query = query.eq("status", status)
    if month:
        query = query.eq("period_month", month_to_date(month))

    try:
        rows = query.execute().data or []
    except Exception as exc:  # noqa: BLE001
        raise AppError(clean_supabase_error(exc)) from exc

    if search:
        term = search.lower().strip()
        rows = [
            r
            for r in rows
            if term in ((r.get("tenants") or {}).get("name") or "").lower()
            or term in ((r.get("properties") or {}).get("name") or "").lower()
        ]

    total_due = sum(float(r.get("amount_due") or 0) for r in rows)
    total_paid = sum(float(r.get("amount_paid") or 0) for r in rows)
    return {
        "items": rows,
        "count": len(rows),
        "totals": {
            "due": round(total_due, 2),
            "paid": round(total_paid, 2),
            "pending": round(max(total_due - total_paid, 0), 2),
        },
    }


@router.get("/report")
async def download_report(
    range: str = Query(default="all", pattern="^(6m|12m|24m|all)$"),
    user: AuthContext = Depends(require_api_user),
):
    """Generate and download a PDF rent-collection report for the given period."""
    query = (
        user.client.table("payments")
        .select(COLUMNS)
        .eq("owner_id", user.user_id)
        .order("period_month", desc=True)
    )
    start = period_start(range)
    if start:
        query = query.gte("period_month", start.isoformat())

    try:
        rows = query.execute().data or []
    except Exception as exc:  # noqa: BLE001
        raise AppError(clean_supabase_error(exc)) from exc

    labels = {
        "6m": "Last 6 months",
        "12m": "Last 12 months",
        "24m": "Last 2 years",
        "all": "All time (till today)",
    }

    owner_email = ""
    try:
        profile = (
            user.client.table("profiles")
            .select("email")
            .eq("id", user.user_id)
            .single()
            .execute()
        )
        owner_email = (profile.data or {}).get("email", "")
    except Exception:  # noqa: BLE001
        pass  # email is optional in the report header

    pdf_bytes = build_report_pdf("RentFlow", owner_email, labels[range], rows)
    filename = f"rentflow-report-{range}-{date.today().isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("", status_code=201)
async def create_payment(payload: PaymentIn, user: AuthContext = Depends(require_api_user)):
    tenant = fetch_one(
        user.client, "tenants", user.user_id, payload.tenant_id, columns="id,property_id"
    )
    data = {
        "owner_id": user.user_id,
        "tenant_id": payload.tenant_id,
        "property_id": tenant.get("property_id"),
        "period_month": month_to_date(payload.period_month),
        "amount_due": payload.amount_due,
        "amount_paid": payload.amount_paid,
        "payment_date": payload.payment_date.isoformat() if payload.payment_date else None,
        "payment_method": payload.payment_method,
        "payment_type": payload.payment_type,
        "payment_type_note": payload.payment_type_note,
        "notes": payload.notes,
        "status": payment_status(payload.amount_due, payload.amount_paid),
    }
    if data["amount_paid"] > data["amount_due"]:
        raise bad_request("Paid amount cannot be greater than the amount due.")
    return insert_row(user.client, "payments", data)


@router.put("/{payment_id}")
async def update_payment(
    payment_id: str, payload: PaymentIn, user: AuthContext = Depends(require_api_user)
):
    if payload.amount_paid > payload.amount_due:
        raise bad_request("Paid amount cannot be greater than the amount due.")
    tenant = fetch_one(
        user.client, "tenants", user.user_id, payload.tenant_id, columns="id,property_id"
    )
    data = {
        "tenant_id": payload.tenant_id,
        "property_id": tenant.get("property_id"),
        "period_month": month_to_date(payload.period_month),
        "amount_due": payload.amount_due,
        "amount_paid": payload.amount_paid,
        "payment_date": payload.payment_date.isoformat() if payload.payment_date else None,
        "payment_method": payload.payment_method,
        "payment_type": payload.payment_type,
        "payment_type_note": payload.payment_type_note,
        "notes": payload.notes,
        "status": payment_status(payload.amount_due, payload.amount_paid),
    }
    return update_row(user.client, "payments", user.user_id, payment_id, data)


@router.patch("/{payment_id}/pay")
async def mark_paid(
    payment_id: str, payload: MarkPaidIn, user: AuthContext = Depends(require_api_user)
):
    existing = fetch_one(
        user.client, "payments", user.user_id, payment_id, columns="id,amount_due,amount_paid"
    )
    due = float(existing.get("amount_due") or 0)
    if payload.amount_paid > due:
        raise bad_request("Paid amount cannot be greater than the amount due.")

    data = {
        "amount_paid": payload.amount_paid,
        "payment_date": payload.payment_date.isoformat(),
        "payment_method": payload.payment_method,
        "payment_type": payload.payment_type,
        "payment_type_note": payload.payment_type_note,
        "status": payment_status(due, payload.amount_paid),
    }
    if payload.notes:
        data["notes"] = payload.notes
    return update_row(user.client, "payments", user.user_id, payment_id, data)


@router.delete("/{payment_id}")
async def delete_payment(payment_id: str, user: AuthContext = Depends(require_api_user)):
    delete_row(user.client, "payments", user.user_id, payment_id)
    return {"ok": True}


@router.post("/generate")
async def generate_month(payload: GenerateIn, user: AuthContext = Depends(require_api_user)):
    """Create pending rent records for every active tenant for the given month."""
    period = month_to_date(payload.period_month)
    tenants = fetch_all(
        user.client,
        "tenants",
        user.user_id,
        columns="id,property_id,rent_amount,agreement_start,agreement_end",
        filters={"is_active": True},
    )
    if not tenants:
        raise bad_request("No active tenants found. Add a tenant first.")

    period_date = date.fromisoformat(period)
    rows = []
    for tenant in tenants:
        start = tenant.get("agreement_start")
        end = tenant.get("agreement_end")
        if start and date.fromisoformat(start).replace(day=1) > period_date:
            continue
        if end and date.fromisoformat(end) < period_date:
            continue
        rows.append(
            {
                "owner_id": user.user_id,
                "tenant_id": tenant["id"],
                "property_id": tenant.get("property_id"),
                "period_month": period,
                "amount_due": float(tenant.get("rent_amount") or 0),
                "amount_paid": 0,
                "status": "Pending",
            }
        )

    if not rows:
        raise bad_request("No tenant agreements are active for that month.")

    try:
        result = (
            user.client.table("payments")
            .upsert(rows, on_conflict="tenant_id,period_month", ignore_duplicates=True)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise AppError(clean_supabase_error(exc)) from exc

    created = len(result.data or [])
    return {
        "ok": True,
        "created": created,
        "skipped": len(rows) - created,
        "message": f"{created} rent record(s) created, {len(rows) - created} already existed.",
    }