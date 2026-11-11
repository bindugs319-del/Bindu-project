"""
Generates a purchase-order PDF for a PurchaseOrder, in the same visual
style as the sales tax-invoice PDF (app/services/sales_invoice_pdf.py):
buyer company header on the left / "PURCHASE ORDER" + PO# on the right,
a details grid (dates, payment window, status), vendor and address
blocks, an amount table and notes.

Amounts are written as "Rs." because the built-in PDF fonts have no
rupee glyph (same convention as the invoice PDF's plain numbers).
"""
import io
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from app.models import PurchaseOrder

BORDER = colors.HexColor("#E2E8F0")
HEADER_BG = colors.HexColor("#F1F5F9")
INK = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#475569")

STATUS_COLORS = {
    "OPEN": colors.HexColor("#1E3A8A"),
    "PENDING DOCS": colors.HexColor("#B45309"),
    "CLOSED": colors.HexColor("#15803D"),
    "PAID": colors.HexColor("#15803D"),
}


def _fmt_date(d) -> str:
    if not d:
        return "—"
    if isinstance(d, str):
        try:
            d = datetime.fromisoformat(d)
        except ValueError:
            return d
    return d.strftime("%d/%m/%Y")


def _fmt_amount(value) -> str:
    """Rs. 4,85,000.00 — Indian digit grouping (lakh / crore)."""
    n = float(value or 0)
    sign = "-" if n < 0 else ""
    whole, frac = f"{abs(n):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"Rs. {sign}{whole}.{frac}"


def _esc(text: Optional[str]) -> str:
    """Escape for reportlab's mini-HTML and keep line breaks."""
    if not text:
        return ""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>"))


def build_purchase_order_pdf(po: PurchaseOrder, company_name: Optional[str], company_gstin: Optional[str]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
        title=f"Purchase Order {po.po_number}", author=company_name or "CreditDataWatch",
    )

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    small = ParagraphStyle("small", parent=normal, fontSize=8, leading=10, textColor=MUTED)
    body = ParagraphStyle("body", parent=normal, fontSize=9, leading=12, textColor=INK)
    label = ParagraphStyle("label", parent=small, fontName="Helvetica-Bold", textColor=MUTED)
    section = ParagraphStyle("section", parent=normal, fontName="Helvetica-Bold", fontSize=10, textColor=INK)
    title = ParagraphStyle("title", parent=normal, fontName="Helvetica-Bold", fontSize=20, leading=26,
                           alignment=TA_RIGHT, textColor=INK)
    right_small = ParagraphStyle("rs", parent=small, alignment=TA_RIGHT)
    company_style = ParagraphStyle("company", parent=normal, fontName="Helvetica-Bold", fontSize=13, leading=16,
                                   textColor=INK)

    story = []

    # --- Header -------------------------------------------------------
    left = [Paragraph(_esc(company_name or "Your Company"), company_style),
            Paragraph(f"GSTIN: {_esc(company_gstin) or 'N/A'}", small)]
    status = (po.status or "Open").upper()
    status_style = ParagraphStyle("status", parent=normal, fontName="Helvetica-Bold", fontSize=10,
                                  alignment=TA_RIGHT, textColor=STATUS_COLORS.get(status, MUTED))
    right = [Paragraph("PURCHASE ORDER", title),
             Paragraph(f"PO # {_esc(po.po_number)}", ParagraphStyle("pon", parent=body, alignment=TA_RIGHT,
                                                                    fontName="Helvetica-Bold")),
             Paragraph(status + (" · ARCHIVED" if po.archived else ""), status_style)]
    header = Table([[left, right]], colWidths=[95 * mm, 79 * mm])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [header, Spacer(1, 8 * mm)]

    # --- Details grid -------------------------------------------------
    paid_on = _fmt_date(po.payment_completed_at) if po.payment_completed_at else "Not paid"
    details = [
        [Paragraph("PO date", label), Paragraph("Payment due", label),
         Paragraph("Payment window", label), Paragraph("Paid on", label)],
        [Paragraph(_fmt_date(po.created_at), body), Paragraph(_fmt_date(po.due_date), body),
         Paragraph(f"{po.payment_window_days} days" if po.payment_window_days else "—", body),
         Paragraph(paid_on, body)],
    ]
    grid = Table(details, colWidths=[43.5 * mm] * 4)
    grid.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [grid, Spacer(1, 7 * mm)]

    # --- Vendor / addresses -------------------------------------------
    vendor_lines = [Paragraph("Vendor", section), Spacer(1, 2 * mm), Paragraph(_esc(po.vendor), body)]
    if po.gstin:
        vendor_lines.append(Paragraph(f"GSTIN: {_esc(po.gstin)}", small))
    if po.vendor_email:
        vendor_lines.append(Paragraph(_esc(po.vendor_email), small))
    if po.vendor_phone:
        vendor_lines.append(Paragraph(_esc(po.vendor_phone), small))
    if po.supplier_address:
        vendor_lines += [Spacer(1, 1.5 * mm), Paragraph(_esc(po.supplier_address), small)]

    addr_lines = []
    if po.delivery_address:
        addr_lines += [Paragraph("Deliver to", section), Spacer(1, 2 * mm), Paragraph(_esc(po.delivery_address), small),
                       Spacer(1, 4 * mm)]
    if po.invoice_address:
        addr_lines += [Paragraph("Invoice to", section), Spacer(1, 2 * mm), Paragraph(_esc(po.invoice_address), small)]
    if not addr_lines:
        addr_lines = [Paragraph("Deliver to", section), Spacer(1, 2 * mm), Paragraph("—", small)]

    parties = Table([[vendor_lines, addr_lines]], colWidths=[87 * mm, 87 * mm])
    parties.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (0, 0), 0.6, BORDER), ("BOX", (1, 0), (1, 0), 0.6, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [parties, Spacer(1, 7 * mm)]

    # --- Amount -------------------------------------------------------
    amount_style = ParagraphStyle("amt", parent=body, alignment=TA_RIGHT)
    amount_bold = ParagraphStyle("amtb", parent=amount_style, fontName="Helvetica-Bold", fontSize=11)
    rows = [
        [Paragraph("Description", label), Paragraph("Amount", ParagraphStyle("al", parent=label, alignment=TA_RIGHT))],
        [Paragraph(f"Purchase order {_esc(po.po_number)} — {_esc(po.vendor)}", body),
         Paragraph(_fmt_amount(po.amount), amount_style)],
        [Paragraph("Total", ParagraphStyle("tl", parent=body, fontName="Helvetica-Bold")),
         Paragraph(_fmt_amount(po.amount), amount_bold)],
    ]
    amounts = Table(rows, colWidths=[129 * mm, 45 * mm])
    amounts.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("LINEABOVE", (0, 2), (-1, 2), 0.8, INK),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(amounts)

    if po.notes:
        story += [Spacer(1, 7 * mm), Paragraph("Notes", section), Spacer(1, 2 * mm), Paragraph(_esc(po.notes), body)]

    if po.document_url:
        story += [Spacer(1, 5 * mm), Paragraph("A supporting document is attached to this PO in CreditDataWatch.", small)]

    story += [Spacer(1, 10 * mm),
              Paragraph(f"Generated by CreditDataWatch on {datetime.now().strftime('%d/%m/%Y %H:%M')}", right_small)]

    doc.build(story)
    return buffer.getvalue()
