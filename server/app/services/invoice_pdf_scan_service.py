"""
Scans an uploaded Sales Invoice PDF and extracts the fields InvoiceCSVImportModal
uses. Same design as po_pdf_scan_service.py: text-based PDFs only, a
"counterparty block" (Bill To / Customer / Client) is located and used to
disambiguate email/phone/GSTIN from the issuing company's own letterhead
info, and money labels are ranked so "Total"/"Grand Total" beats a bare
"Amount". Line items are NOT extracted — only the invoice-level fields.
"""
import io
import re
from datetime import datetime
from typing import Optional

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    from PyPDF2 import PdfReader  # type: ignore

from app.services.po_pdf_scan_service import (
    _normalize_lines, _find_label_value, _find_all_label_values,
    _parse_date, _parse_amount, _looks_like_money, EMAIL_RE, PHONE_RE, GSTIN_RE,
)

INVOICE_NUMBER_LABELS = ["invoice number", "invoice #", "invoice no", "bill no", "reference"]
COUNTERPARTY_LABELS = ["counterparty name", "counterparty", "customer name", "customer", "client", "bill to"]
GSTIN_LABELS = ["counterparty gstin", "customer gstin", "client gstin", "gstin", "gstin/uin", "gst no"]
EMAIL_LABELS = ["counterparty email", "customer email", "client email", "email"]
PHONE_LABELS = ["counterparty phone", "customer phone", "client phone", "phone", "mobile", "contact"]
SUBTOTAL_LABELS = ["subtotal", "sub total", "taxable amount"]
TAX_LABELS = ["tax amount", "gst amount", "tax"]
TOTAL_STRONG_LABELS = ["grand total", "total amount", "invoice amount", "amount payable", "amount due"]
TOTAL_WEAK_LABELS = ["total", "amount"]
INVOICE_DATE_LABELS = ["invoice date", "bill date"]
DUE_DATE_LABELS = ["due date", "payment due date", "payment due"]

COUNTERPARTY_SECTION_HEADINGS = ["bill to", "customer details", "client details", "counterparty details", "invoice to"]
SECTION_HEADING_HINTS = ["items", "item details", "payment terms", "terms & conditions", "terms and conditions", "bank details", "authorized signatory"]


def _counterparty_block_range(lines: list):
    start = None
    for i, ln in enumerate(lines):
        if any(h in ln.lower() for h in COUNTERPARTY_SECTION_HEADINGS):
            start = i + 1
            break
    if start is None:
        return None
    end = len(lines)
    for i in range(start, len(lines)):
        if any(h in lines[i].lower() for h in SECTION_HEADING_HINTS):
            end = i
            break
    return range(start, end)


def extract_invoice_fields(pdf_bytes: bytes, filename: str = "upload.pdf") -> dict:
    warnings = []
    from app.services.ocr_utils import IMAGE_EXTENSIONS, get_document_text
    is_image = filename.lower().endswith(IMAGE_EXTENSIONS)

    pdf_text = ""
    if not is_image:
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            pdf_text = reader.pages[0].extract_text() or ""
            if len(pdf_text.strip()) < 20 and len(reader.pages) > 1:
                pdf_text = "\n".join((p.extract_text() or "") for p in reader.pages[:3])
        except Exception:
            pdf_text = ""

    doc = get_document_text(pdf_bytes, filename, existing_text=pdf_text)
    text = doc["text"]
    used_ocr = doc["source"] in ("ocr_pdf", "ocr_image")

    if doc["ocr_unavailable"] and len((pdf_text or "").strip()) < 10:
        return {
            "fields": {},
            "warnings": [
                "This looks like a scanned/photographed document with no embedded text, and OCR isn't "
                "available on this server right now (missing tesseract/poppler). Ask your admin to enable "
                "OCR support, or upload a text-based PDF instead."
            ],
            "raw_text_available": False,
            "used_ocr": False,
        }

    if len(text.strip()) < 10:
        return {
            "fields": {},
            "warnings": ["Couldn't find or recognize any text in this file."],
            "raw_text_available": False,
            "used_ocr": used_ocr,
        }

    if used_ocr:
        warnings.append(
            "This was read using OCR (scanned/photographed document) rather than a text layer — "
            "recognition can misread characters, especially in GSTINs and currency amounts. "
            "Please double-check every field below before confirming."
        )

    lines = _normalize_lines(text)
    block = _counterparty_block_range(lines)

    fields = {}

    fields["invoice_number"] = _find_label_value(lines, INVOICE_NUMBER_LABELS, allow_same_line_no_colon=used_ocr)

    counterparty = _find_label_value(lines, COUNTERPARTY_LABELS, block, allow_same_line_no_colon=used_ocr) if block else None
    if not counterparty:
        counterparty = _find_label_value(lines, COUNTERPARTY_LABELS, allow_same_line_no_colon=used_ocr)
    fields["counterparty_name"] = counterparty

    gstin = _find_label_value(lines, GSTIN_LABELS, block, allow_same_line_no_colon=used_ocr) if block else None
    if not gstin:
        all_gstins = list(dict.fromkeys(GSTIN_RE.findall(text)))
        if len(all_gstins) == 1:
            gstin = all_gstins[0]
        elif len(all_gstins) > 1:
            warnings.append(f"Found {len(all_gstins)} possible GSTINs on the page; couldn't tell which is the counterparty's, so it was left blank.")
    fields["counterparty_gstin"] = gstin.upper() if gstin else None

    email = _find_label_value(lines, EMAIL_LABELS, block) if block else None
    if not email:
        candidates = EMAIL_RE.findall(text)
        if block:
            in_block = [c for c in candidates if any(c in lines[i] for i in block)]
            if len(in_block) == 1:
                email = in_block[0]
            elif len(in_block) > 1:
                warnings.append("Multiple emails found in the counterparty section; please confirm the correct one.")
        elif len(set(candidates)) == 1:
            email = candidates[0]
        elif len(set(candidates)) > 1:
            warnings.append("Multiple emails found on the page and no clear counterparty section; email left blank — please fill it in.")
    fields["counterparty_email"] = email

    phone = _find_label_value(lines, PHONE_LABELS, block) if block else None
    if phone:
        m = PHONE_RE.search(phone)
        phone = m.group(0) if m else phone
    if not phone:
        candidates = PHONE_RE.findall(text)
        if block:
            in_block = [c for c in candidates if any(c in lines[i] for i in block)]
            if len(in_block) == 1:
                phone = in_block[0]
            elif len(in_block) > 1:
                warnings.append("Multiple phone numbers found in the counterparty section; please confirm the correct one.")
        elif len(set(candidates)) == 1:
            phone = candidates[0]
        elif len(set(candidates)) > 1:
            warnings.append("Multiple phone numbers found on the page and no clear counterparty section; phone left blank — please fill it in.")
    fields["counterparty_phone"] = re.sub(r"[\s\-]", "", phone) if phone else None

    fields["subtotal"] = _parse_amount(_find_label_value(lines, SUBTOTAL_LABELS, value_check=_looks_like_money, allow_same_line_no_colon=used_ocr))
    fields["tax_amount"] = _parse_amount(_find_label_value(lines, TAX_LABELS, value_check=_looks_like_money, allow_same_line_no_colon=used_ocr))

    strong = _find_all_label_values(lines, TOTAL_STRONG_LABELS, value_check=_looks_like_money)
    total_raw = strong[-1] if strong else _find_label_value(
        lines, TOTAL_WEAK_LABELS, value_check=_looks_like_money, allow_same_line_no_colon=used_ocr
    )
    fields["total"] = _parse_amount(total_raw)
    if fields["total"] is None:
        warnings.append("Could not confidently find a total amount; please enter it manually.")

    fields["invoice_date"] = _parse_date(_find_label_value(lines, INVOICE_DATE_LABELS))
    if not fields["invoice_date"] and not used_ocr:
        from app.services.pdf_table_utils import find_table_header_value
        table_val = find_table_header_value(pdf_bytes, INVOICE_DATE_LABELS)
        fields["invoice_date"] = _parse_date(table_val)
    if not fields["invoice_date"]:
        warnings.append("Could not find an invoice date; please enter one manually.")

    due_raw = _find_label_value(lines, DUE_DATE_LABELS)
    if not due_raw:
        m = re.search(r"due date\s*[:\-]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
        if m:
            due_raw = m.group(1)
    fields["payment_due_date"] = _parse_date(due_raw)
    if not fields["payment_due_date"] and not used_ocr:
        from app.services.pdf_table_utils import find_table_header_value
        table_val = find_table_header_value(pdf_bytes, DUE_DATE_LABELS)
        fields["payment_due_date"] = _parse_date(table_val)
    if not fields["payment_due_date"]:
        warnings.append("Could not find a payment due date; please enter one manually.")

    if not fields.get("invoice_number"):
        warnings.append("Could not find an Invoice Number on this page; please enter it manually.")
    if not fields.get("counterparty_name"):
        warnings.append("Could not find a Counterparty Name; please enter it manually.")

    return {"fields": fields, "warnings": warnings, "raw_text_available": True, "used_ocr": used_ocr}
