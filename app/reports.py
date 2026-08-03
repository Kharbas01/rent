"""Generates a professional PDF rent-collection report."""

from datetime import date, timedelta
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT

BRAND = colors.HexColor("#4f46e5")
MUTED = colors.HexColor("#64748b")
LIGHT = colors.HexColor("#f1f5f9")
DANGER = colors.HexColor("#dc2626")
SUCCESS = colors.HexColor("#059669")


def period_start(range_key: str) -> date | None:
    """Return the earliest date to include for a given range key, or None for 'all'."""
    today = date.today()
    if range_key == "6m":
        return today - timedelta(days=182)
    if range_key == "12m":
        return today - timedelta(days=365)
    if range_key == "24m":
        return today - timedelta(days=730)
    return None  # "all"


def build_report_pdf(app_name: str, owner_email: str, range_label: str, rows: list[dict]) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=22 * mm, bottomMargin=18 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "title", parent=styles["Heading1"], fontSize=20, textColor=BRAND, spaceAfter=2
    )
    sub_style = ParagraphStyle(
        "sub", parent=styles["Normal"], fontSize=9.5, textColor=MUTED
    )
    section_style = ParagraphStyle(
        "section", parent=styles["Heading2"], fontSize=12.5,
        textColor=colors.HexColor("#0f172a"), spaceBefore=14, spaceAfter=6,
    )
    right_style = ParagraphStyle(
        "right", parent=styles["Normal"], alignment=TA_RIGHT, fontSize=9.5, textColor=MUTED
    )

    story = []

    # ---- Header ----
    story.append(Paragraph(app_name, title_style))
    story.append(Paragraph("Rent Collection Report", sub_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Account: {owner_email} &nbsp;&nbsp;|&nbsp;&nbsp; Period: {range_label} "
        f"&nbsp;&nbsp;|&nbsp;&nbsp; Generated on: {date.today().strftime('%d %b %Y')}",
        sub_style,
    ))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0")))
    story.append(Spacer(1, 14))

    # ---- Summary ----
    total_due = sum(float(r.get("amount_due") or 0) for r in rows)
    total_paid = sum(float(r.get("amount_paid") or 0) for r in rows)
    total_pending = max(total_due - total_paid, 0)
    collection_rate = (total_paid / total_due * 100) if total_due else 0

    def money(v: float) -> str:
        return f"Rs. {v:,.2f}"

    summary_data = [
        ["Total billed", "Total collected", "Pending", "Collection rate"],
        [money(total_due), money(total_paid), money(total_pending), f"{collection_rate:.1f}%"],
    ]
    summary_table = Table(summary_data, colWidths=[43 * mm] * 4)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, 1), 13),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("TEXTCOLOR", (2, 1), (2, 1), DANGER),
        ("TEXTCOLOR", (1, 1), (1, 1), SUCCESS),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 1), (-1, 1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 12),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#e2e8f0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#e2e8f0")),
    ]))
    story.append(summary_table)

    # ---- Transactions table ----
    story.append(Paragraph("Payment Records", section_style))

    header = [
        "Tenant", "Property", "Month", "Due day", "Type",
        "Due", "Paid", "Balance", "Status", "Paid on",
    ]
    table_rows = [header]
    for r in sorted(rows, key=lambda x: x.get("period_month") or "", reverse=True):
        due = float(r.get("amount_due") or 0)
        paid = float(r.get("amount_paid") or 0)
        balance = max(due - paid, 0)
        tenant_info = r.get("tenants") or {}
        tenant = tenant_info.get("name") or "\u2014"
        due_day = tenant_info.get("due_day_of_month")
        due_day_label = str(due_day) if due_day else "\u2014"
        prop = (r.get("properties") or {}).get("name") or "\u2014"
        month = str(r.get("period_month") or "")[:7]
        payment_type = r.get("payment_type") or "\u2014"
        table_rows.append([
            tenant, prop, month, due_day_label, payment_type,
            money(due), money(paid), money(balance),
            r.get("status") or "\u2014", r.get("payment_date") or "\u2014",
        ])

    if len(table_rows) == 1:
        story.append(Paragraph("No payment records found for this period.", sub_style))
    else:
        col_widths = [
            24 * mm, 22 * mm, 14 * mm, 14 * mm, 16 * mm,
            18 * mm, 18 * mm, 18 * mm, 14 * mm, 18 * mm,
        ]
        t = Table(table_rows, colWidths=col_widths, repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), BRAND),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.3),
            ("ALIGN", (3, 0), (3, -1), "CENTER"),
            ("ALIGN", (5, 0), (7, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        for i, row in enumerate(table_rows[1:], start=1):
            if row[8] == "Paid":
                style.append(("TEXTCOLOR", (8, i), (8, i), SUCCESS))
            elif row[8] == "Pending":
                style.append(("TEXTCOLOR", (8, i), (8, i), DANGER))
        t.setStyle(TableStyle(style))
        story.append(t)

    story.append(Spacer(1, 18))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#e2e8f0")))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Generated automatically by {app_name} \u00b7 {len(rows)} record(s) included",
        right_style,
    ))

    doc.build(story)
    return buffer.getvalue()