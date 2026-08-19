"""
Generates a tax-invoice PDF for a SalesInvoice, in the same general
layout as the sample "Preflex Solutions" tax invoice: company header on
the left / "TAX INVOICE" + invoice# on the right, Bill To / Ship To side
by side, a details strip (dates, PO#, PAN, MSME no), a line-items table,
and a totals block with a CGST/SGST/IGST breakdown.

Line items and bill_to/ship_to are read as plain dicts (JSON columns on
the invoice row), matching the supervisor's spec sheet exactly.

This is a first pass at the layout — expect to adjust once specific
styling feedback comes in.
"""
import io
from datetime import date as date_type
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)
from reportlab.lib.enums import TA_RIGHT

from app.models import SalesInvoice


def _fmt_date(d: Optional[date_type]) -> str:
    if not d:
        return ""
    return d.strftime("%d/%m/%Y")


def _fmt_amount(value) -> str:
    if value is None:
        value = 0
    return f"{value:,.2f}"


def build_sales_invoice_pdf(invoice: SalesInvoice) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
    )

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    small = ParagraphStyle("small", parent=normal, fontSize=8, leading=10)
    bold = ParagraphStyle("bold", parent=normal, fontName="Helvetica-Bold")
    section_heading = ParagraphStyle(
        "sectionHeading", parent=normal, fontName="Helvetica-Bold", fontSize=10
    )
    title_style = ParagraphStyle(
        "title", parent=normal, fontName="Helvetica-Bold", fontSize=22, leading=28, alignment=TA_RIGHT
    )
    company_name_style = ParagraphStyle(
        "companyName", parent=normal, fontName="Helvetica-Bold", fontSize=13, leading=16
    )

    company_name = invoice.company_name or "Your Company"
    company_address = invoice.company_address or ""
    company_gstin = invoice.company_gstin or "N/A"
    company_pan = invoice.company_pan or "N/A"
    cin = invoice.cin or ""
    msme_no = invoice.msme_no or "N/A"

    bill_to = invoice.bill_to or {}
    ship_to = invoice.ship_to or {}
    items = invoice.items or []

    story = []

    # --- Header: company block (left) / TAX INVOICE + invoice# (right) ---
    company_block = [
        Paragraph(company_name, company_name_style),
    ]
    if company_address:
        company_block.append(Paragraph(company_address.replace("\n", "<br/>"), small))
    company_block.append(Paragraph(f"GSTIN: {company_gstin}", small))
    if cin:
        company_block.append(Paragraph(f"CIN: {cin}", small))

    invoice_block = [
        Paragraph("TAX INVOICE", title_style),
    ]
    if invoice.lut_arn:
        invoice_block.append(Paragraph(f"LUT ARN: {invoice.lut_arn}", ParagraphStyle(
            "lut", parent=small, alignment=TA_RIGHT
        )))
    if invoice.lut_filing_date:
        invoice_block.append(Paragraph(
            f"Date of Filing LUT: {_fmt_date(invoice.lut_filing_date)}",
            ParagraphStyle("lutDate", parent=small, alignment=TA_RIGHT),
        ))

    header_table = Table(
        [[company_block, invoice_block]],
        colWidths=[100 * mm, 72 * mm],
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(header_table)

    status = (invoice.status or "Draft").upper()
    status_colors = {
        "DRAFT": colors.HexColor("#9CA3AF"),
        "SENT": colors.HexColor("#2563EB"),
        "PAID": colors.HexColor("#16A34A"),
        "OVERDUE": colors.HexColor("#DC2626"),
        "CANCELLED": colors.HexColor("#6B7280"),
    }
    status_style = ParagraphStyle(
        "status", parent=normal, fontName="Helvetica-Bold", fontSize=10,
        alignment=TA_RIGHT, textColor=status_colors.get(status, colors.HexColor("#9CA3AF")),
    )
    story.append(Paragraph(status, status_style))
    story.append(Spacer(1, 10 * mm))

    # --- Details grid: company name, invoice #, dates, PO#, PAN, MSME no ---
    # Laid out as a 4-column x 2-row-group grid (label row + value row,
    # twice) rather than one cramped 8-column strip — long values like a
    # full invoice number or a due date need real room to avoid wrapping
    # mid-word.
    dh_style = ParagraphStyle("dh", parent=small, fontName="Helvetica-Bold", textColor=colors.HexColor("#374151"))
    dv_style = ParagraphStyle("dv", parent=normal, fontSize=9, leading=12)

    details_grid = [
        [Paragraph("Company Name", dh_style), Paragraph("Invoice #", dh_style),
         Paragraph("Invoice Date", dh_style), Paragraph("Payment Due Date", dh_style)],
        [Paragraph(company_name, dv_style), Paragraph(invoice.invoice_number, dv_style),
         Paragraph(_fmt_date(invoice.invoice_date), dv_style), Paragraph(_fmt_date(invoice.payment_due_date), dv_style)],
        [Paragraph("PO#", dh_style), Paragraph("PO Date", dh_style),
         Paragraph("PAN", dh_style), Paragraph("MSME No", dh_style)],
        [Paragraph(invoice.po_number or "—", dv_style), Paragraph(_fmt_date(invoice.po_date) or "—", dv_style),
         Paragraph(company_pan, dv_style), Paragraph(msme_no, dv_style)],
    ]

    col_w = 40.5 * mm
    details_table = Table(details_grid, colWidths=[col_w] * 4)
    details_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE6F1")),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#DCE6F1")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 6 * mm))

    # --- Line items table (each item is a plain dict: desc/hsn/qty/rate/amount) ---
    item_headers = ["#", "Item & Description", "HSN/SAC", "Qty", "Rate", "Amount"]
    item_rows = [item_headers]
    for idx, item in enumerate(items, start=1):
        qty = item.get("qty", 0) or 0
        item_rows.append([
            str(idx),
            Paragraph(item.get("desc") or "", small),
            item.get("hsn") or "",
            f"{qty:g}" if isinstance(qty, (int, float)) else str(qty),
            _fmt_amount(item.get("rate")),
            _fmt_amount(item.get("amount")),
        ])

    items_table = Table(
        item_rows,
        colWidths=[8 * mm, 76 * mm, 24 * mm, 16 * mm, 24 * mm, 24 * mm],
        repeatRows=1,
    )
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE6F1")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 6 * mm))

    # --- Totals block, with discount, CGST/SGST/IGST breakdown, round-off ---
    currency = invoice.currency or "INR"
    totals_rows = [["Sub Total", f"{currency} {_fmt_amount(invoice.subtotal)}"]]

    if invoice.discount_amount:
        totals_rows.append(["Discount", f"- {currency} {_fmt_amount(invoice.discount_amount)}"])

    breakdown = invoice.tax_breakdown or {}
    if invoice.reverse_charge:
        totals_rows.append(["Tax (Reverse Charge — payable by recipient)", f"{currency} {_fmt_amount(invoice.tax_amount)}"])
    else:
        if breakdown.get("cgst"):
            totals_rows.append(["CGST", f"{currency} {_fmt_amount(breakdown.get('cgst'))}"])
        if breakdown.get("sgst"):
            totals_rows.append(["SGST", f"{currency} {_fmt_amount(breakdown.get('sgst'))}"])
        if breakdown.get("igst"):
            totals_rows.append(["IGST", f"{currency} {_fmt_amount(breakdown.get('igst'))}"])
        if not breakdown and invoice.tax_amount:
            totals_rows.append(["Tax", f"{currency} {_fmt_amount(invoice.tax_amount)}"])

    if invoice.round_off:
        sign = "+" if invoice.round_off > 0 else "-"
        totals_rows.append(["Round Off", f"{sign} {currency} {_fmt_amount(abs(invoice.round_off))}"])

    totals_rows.append(["Total", f"{currency} {_fmt_amount(invoice.total)}"])

    if invoice.currency and invoice.currency != "INR" and invoice.exchange_rate and invoice.exchange_rate != 1.0:
        inr_total = invoice.total * invoice.exchange_rate
        totals_rows.append([
            f"Total (INR @ {invoice.exchange_rate:g})",
            f"INR {_fmt_amount(inr_total)}",
        ])

    totals_rows.append(["Balance Due", f"{currency} {_fmt_amount(invoice.balance_due)}"])

    totals_table = Table(totals_rows, colWidths=[55 * mm, 45 * mm], hAlign="RIGHT")
    totals_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 8 * mm))

    if invoice.eway_bill_number:
        story.append(Paragraph(f"E-Way Bill No: {invoice.eway_bill_number}", small))
        story.append(Spacer(1, 4 * mm))

    # --- Bill To / Ship To ---
    def _party_block(heading, name, address_text, gstin=None, pan=None):
        block = [Paragraph(heading, section_heading), Paragraph(name or "", bold)]
        if address_text:
            block.append(Paragraph(address_text, small))
        if gstin:
            block.append(Paragraph(f"GSTIN: {gstin}", small))
        if pan:
            block.append(Paragraph(f"PAN: {pan}", small))
        return block

    bill_to_block = _party_block(
        "Bill To",
        bill_to.get("name") or invoice.counterparty_name,
        bill_to.get("address"),
        invoice.counterparty_gstin,
        invoice.counterparty_pan,
    )
    ship_to_block = _party_block(
        "Ship To",
        ship_to.get("name") or bill_to.get("name") or invoice.counterparty_name,
        ship_to.get("address") or bill_to.get("address"),
    )

    addr_table = Table([[bill_to_block, ship_to_block]], colWidths=[86 * mm, 86 * mm])
    addr_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(addr_table)
    story.append(Spacer(1, 6 * mm))

    if invoice.place_of_supply:
        story.append(Paragraph(f"Place Of Supply: {invoice.place_of_supply}", small))
        story.append(Spacer(1, 4 * mm))

    if invoice.is_sez_export:
        story.append(Paragraph(
            "SUPPLY MEANT FOR EXPORT / SUPPLY TO SEZ UNIT/SEZ DEVELOPER FOR "
            "AUTHORIZED OPERATIONS UNDER BOND OR LETTER OF UNDERTAKING WITHOUT "
            "PAYMENT OF INTEGRATED TAX",
            small,
        ))
        story.append(Spacer(1, 6 * mm))

    if invoice.payment_terms:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(f"Payment Terms: {invoice.payment_terms}", small))

    if any([invoice.bank_account_name, invoice.bank_account_number, invoice.bank_ifsc, invoice.bank_name, invoice.bank_upi_id]):
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph("Payment Details", section_heading))
        if invoice.bank_name:
            story.append(Paragraph(f"Bank: {invoice.bank_name}", small))
        if invoice.bank_account_name:
            story.append(Paragraph(f"Account Name: {invoice.bank_account_name}", small))
        if invoice.bank_account_number:
            story.append(Paragraph(f"Account No: {invoice.bank_account_number}", small))
        if invoice.bank_ifsc:
            story.append(Paragraph(f"IFSC: {invoice.bank_ifsc}", small))
        if invoice.bank_upi_id:
            story.append(Paragraph(f"UPI ID: {invoice.bank_upi_id}", small))

    if invoice.document_url:
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph(
            f'Attachment: <link href="{invoice.document_url}">{invoice.document_url}</link>',
            small,
        ))

    if invoice.notes:
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph("Notes", section_heading))
        story.append(Paragraph(invoice.notes.replace("\n", "<br/>"), small))

    doc.build(story)
    return buffer.getvalue()
