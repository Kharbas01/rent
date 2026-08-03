"""Thin, reusable data-access helpers on top of the Supabase client."""

from datetime import date
from typing import Any, Iterable

from supabase import Client

from app.errors import AppError, clean_supabase_error, not_found


def _execute(query) -> Any:
    """Run a PostgREST query and normalise errors."""
    try:
        return query.execute()
    except Exception as exc:  # noqa: BLE001 - surfaced as a friendly message
        raise AppError(clean_supabase_error(exc)) from exc


def fetch_all(
    client: Client,
    table: str,
    owner_id: str,
    columns: str = "*",
    order_by: str = "created_at",
    descending: bool = True,
    search: str | None = None,
    search_columns: Iterable[str] = (),
    filters: dict[str, Any] | None = None,
    limit: int | None = None,
) -> list[dict]:
    query = client.table(table).select(columns).eq("owner_id", owner_id)

    for key, value in (filters or {}).items():
        if value not in (None, "", "all"):
            query = query.eq(key, value)

    if search and search_columns:
        term = search.replace(",", " ").replace("%", "").strip()
        if term:
            clause = ",".join(f"{col}.ilike.%{term}%" for col in search_columns)
            query = query.or_(clause)

    query = query.order(order_by, desc=descending)
    if limit:
        query = query.limit(limit)

    result = _execute(query)
    return result.data or []


def fetch_one(client: Client, table: str, owner_id: str, row_id: str, columns: str = "*") -> dict:
    result = _execute(
        client.table(table).select(columns).eq("owner_id", owner_id).eq("id", row_id).limit(1)
    )
    rows = result.data or []
    if not rows:
        raise not_found(f"{table[:-1].capitalize()} not found.")
    return rows[0]


def insert_row(client: Client, table: str, payload: dict) -> dict:
    result = _execute(client.table(table).insert(payload))
    rows = result.data or []
    if not rows:
        raise AppError("Could not create the record.")
    return rows[0]


def update_row(client: Client, table: str, owner_id: str, row_id: str, payload: dict) -> dict:
    result = _execute(
        client.table(table).update(payload).eq("owner_id", owner_id).eq("id", row_id)
    )
    rows = result.data or []
    if not rows:
        raise not_found("Record not found or you do not have access to it.")
    return rows[0]


def delete_row(client: Client, table: str, owner_id: str, row_id: str) -> None:
    result = _execute(client.table(table).delete().eq("owner_id", owner_id).eq("id", row_id))
    if not (result.data or []):
        raise not_found("Record not found or already deleted.")


def set_property_status(client: Client, owner_id: str, property_id: str | None, status: str) -> None:
    """Keep property occupancy in sync with tenant assignments."""
    if not property_id:
        return
    try:
        client.table("properties").update({"status": status}).eq("owner_id", owner_id).eq(
            "id", property_id
        ).execute()
    except Exception:  # noqa: BLE001 - status sync must never break the main action
        pass


def property_has_active_tenant(
    client: Client, owner_id: str, property_id: str, exclude_tenant_id: str | None = None
) -> bool:
    query = (
        client.table("tenants")
        .select("id")
        .eq("owner_id", owner_id)
        .eq("property_id", property_id)
        .eq("is_active", True)
    )
    if exclude_tenant_id:
        query = query.neq("id", exclude_tenant_id)
    result = _execute(query.limit(1))
    return bool(result.data)


def compute_next_increase_date(agreement_start, duration_months: int | None) -> "date | None":
    """First rent-increase date for an agreement: start + one cycle length.

    Cycle length is the agreement duration in months, defaulting to 12 (annual)
    when no duration is set. Returns None when there is no start date.
    """
    from app.schemas import add_months

    if not agreement_start:
        return None
    cycle = duration_months if (duration_months and duration_months > 0) else 12
    return add_months(agreement_start, cycle)


def apply_due_rent_increases(client: Client, owner_id: str, tenant: dict) -> dict:
    """Lazily apply any rent increases that came due, catching up missed cycles.

    Called whenever a tenant is read (list/get), so the rent shown is always
    current even though this app has no background job scheduler. Never
    touches base_rent_amount; every change is recorded in rent_history.
    """
    from datetime import date as date_cls

    from app.schemas import add_months

    pct = float(tenant.get("rent_increase_percentage") or 0)
    next_due = tenant.get("next_rent_increase_date")
    if not tenant.get("is_active") or pct <= 0 or not next_due:
        return tenant

    if isinstance(next_due, str):
        next_due = date_cls.fromisoformat(next_due)

    cycle = tenant.get("agreement_duration_months") or 12
    today = date_cls.today()
    current_rent = float(tenant.get("rent_amount") or 0)
    history_rows = []
    changed = False

    # Safety cap so a badly-configured agreement can never loop forever.
    for _ in range(240):
        if next_due > today:
            break
        previous_rent = current_rent
        new_rent = round(previous_rent * (1 + pct / 100), 2)
        history_rows.append(
            {
                "owner_id": owner_id,
                "tenant_id": tenant["id"],
                "previous_rent": previous_rent,
                "new_rent": new_rent,
                "increase_percentage": pct,
                "increase_date": next_due.isoformat(),
            }
        )
        current_rent = new_rent
        next_due = add_months(next_due, cycle)
        changed = True

    if not changed:
        return tenant

    try:
        for row in history_rows:
            client.table("rent_history").insert(row).execute()
        updated = update_row(
            client,
            "tenants",
            owner_id,
            tenant["id"],
            {"rent_amount": current_rent, "next_rent_increase_date": next_due.isoformat()},
        )
        tenant = {**tenant, **updated}
    except Exception:  # noqa: BLE001 - never let auto-increase break a page load
        pass

    return tenant


def apply_due_rent_increases_bulk(client: Client, owner_id: str, tenants: list[dict]) -> list[dict]:
    return [apply_due_rent_increases(client, owner_id, t) for t in tenants]


def month_to_date(period_month: str) -> str:
    """'2026-08' -> '2026-08-01' (stored as a real DATE in Postgres)."""
    year, month = period_month.split("-")
    return date(int(year), int(month), 1).isoformat()


def payment_status(amount_due: float, amount_paid: float) -> str:
    if amount_paid <= 0:
        return "Pending"
    if amount_paid + 0.001 >= amount_due:
        return "Paid"
    return "Partial"
