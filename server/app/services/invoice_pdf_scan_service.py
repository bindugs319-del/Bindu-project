"""
Scans an uploaded Sales Invoice PDF and extracts the fields the Add
Invoice form uses. Same design as po_pdf_scan_service.py: text-based
PDFs only, a "counterparty block" (Bill To / Customer / Client) is
located and used to disambiguate email/phone/GSTIN/PAN/address from the
issuing company's own letterhead info, and money labels are ranked so
"Total"/"Grand Total" beats a bare "Amount". Line items are also
extracted, best-effort, via pdfplumber's table-grid detection (see
pdf_table_utils.extract_line_items) for text-layer PDFs.
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
    _parse_date, _parse_amount, _looks_like_money, _read_document_text,
    EMAIL_RE, PHONE_RE, GSTIN_RE,
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
PO_NUMBER_LABELS = ["po number", "po no", "p.o. number", "p.o. no", "purchase order number", "purchase order no", "p.o.#", "po#"]
PO_DATE_LABELS = ["po date", "purchase order date"]
DELIVERY_DATE_LABELS = ["expected delivery date", "delivery date"]
PAYMENT_TERMS_LABELS = ["payment terms", "terms of payment"]
PLACE_OF_SUPPLY_LABELS = ["place of supply"]

COUNTERPARTY_SECTION_HEADINGS = ["bill to", "customer details", "client details", "counterparty details", "invoice to"]
SECTION_HEADING_HINTS = [
    "items", "item &", "item and", "item description", "item details",
    "ship to", "place of supply", "payment terms", "terms & conditions",
    "terms and conditions", "bank details", "authorized signatory",
]
PAN_LABELS = ["counterparty pan", "customer pan", "client pan", "pan", "pan no"]
PAN_RE = re.compile(r"\b[A-Za-z]{5}[0-9]{4}[A-Za-z]\b")
_NON_VALUES = {"nil", "n/a", "na", "none", "-", "--"}


def _clean_or_none(value):
    """Some templates print a literal 'Nil'/'N/A' instead of leaving a
    field blank (e.g. 'P.O.# : Nil' on an invoice with no PO). Treat those
    the same as not having found anything, rather than filling the form
    with the word "Nil"."""
    if not value:
        return None
    return None if value.strip().lower() in _NON_VALUES else value


_ADDRESS_STOP_RE = re.compile(r"^[A-Za-z][A-Za-z .#/&]{1,30}:")
_BARE_LABEL_LINES = {"pan", "gstin", "cin", "overseas", "msme no"}


def _extract_name_and_address(lines, heading_words):
    """Finds a heading line (e.g. 'Bill To' / 'Ship To') and reads the
    block that follows it as (name, address): the first non-empty line is
    the name, subsequent lines are joined into the address until hitting
    another known section heading, a bare GSTIN/PAN/CIN/'Overseas'-style
    marker line, or a 'Label: value' line (real street-address lines don't
    normally contain a colon, invoice metadata fields do)."""
    start = None
    for i, ln in enumerate(lines):
        if ln.strip().lower() in heading_words:
            start = i + 1
            break
    if start is None:
        return None, None

    name = None
    address_lines = []
    for i in range(start, len(lines)):
        raw = lines[i].strip()
        if not raw:
            if name is not None:
                break
            continue
        low = raw.lower()
        if any(h in low for h in SECTION_HEADING_HINTS) or low in COUNTERPARTY_SECTION_HEADINGS:
            break
        if low in _BARE_LABEL_LINES or _ADDRESS_STOP_RE.match(raw):
            break
        if name is None:
            name = raw
            continue
        address_lines.append(raw.rstrip(","))

    address = ", ".join(address_lines) if address_lines else None
    return name, address

# Symbol/code -> ISO 4217 currency code. Checked in this order (longer,
# more specific tokens first) so "US$" doesn't get missed by a bare "$"
# check, etc. This intentionally only covers the currencies actually
# likely to show up on an invoice CreditDataWatch users would upload.
CURRENCY_MARKERS = [
    ("US$", "USD"), ("USD", "USD"),
    ("A$", "AUD"), ("AUD", "AUD"),
    ("C$", "CAD"), ("CAD", "CAD"),
    ("€", "EUR"), ("EUR", "EUR"),
    ("£", "GBP"), ("GBP", "GBP"),
    ("₹", "INR"), ("INR", "INR"), ("RS.", "INR"), ("RS ", "INR"),
    ("$", "USD"),  # bare "$" with no country prefix defaults to USD
]


def _detect_currency(text: str, total_line: Optional[str]) -> str:
    """Figures out which currency the invoice is actually in, rather than
    always assuming INR. Checks the line the total amount was found on
    first (most reliable — that's the actual money figure), then falls
    back to scanning the whole document. Defaults to INR only when no
    currency marker is found anywhere, preserving old behavior for plain
    domestic invoices that never mention a currency at all."""
    for source in (total_line, text):
        if not source:
            continue
        upper = source.upper()
        for marker, code in CURRENCY_MARKERS:
            if marker in upper:
                return code
    return "INR"


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
    doc_result = _read_document_text(pdf_bytes, filename)
    if doc_result["early_result"] is not None:
        return doc_result["early_result"]
    text = doc_result["text"]
    used_ocr = doc_result["used_ocr"]

    warnings = []
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
    if not fields["invoice_number"]:
        # Common invoice-template pattern: the number appears as a bare
        # "# SOME-CODE" line right under the "Tax Invoice" title, with no
        # "Invoice Number:" label at all (e.g. "# PS/INV/26/08/886"). Only
        # match a line that's JUST "#" + one token — this deliberately
        # excludes lines like "P.O.# : Nil" (doesn't start with #) and
        # "# Item & Description ..." (a table header, not a single token).
        for ln in lines:
            m = re.match(r"^#\s*([A-Za-z0-9][A-Za-z0-9\-/.]{3,40})$", ln.strip())
            if m:
                fields["invoice_number"] = m.group(1)
                break

    counterparty = _find_label_value(lines, COUNTERPARTY_LABELS, block, allow_same_line_no_colon=used_ocr) if block else None
    if not counterparty:
        counterparty = _find_label_value(lines, COUNTERPARTY_LABELS, allow_same_line_no_colon=used_ocr)
    fields["counterparty_name"] = counterparty

    gstin = _find_label_value(lines, GSTIN_LABELS, block, allow_same_line_no_colon=used_ocr) if block else None
    if not gstin:
        # Restrict the "only one GSTIN on the page" fallback to text from
        # the Bill To heading onward — otherwise, on an invoice where the
        # counterparty has no GSTIN of their own (e.g. an overseas
        # customer), the one GSTIN on the page is the ISSUER's own
        # letterhead GSTIN and would get wrongly assigned as the
        # counterparty's.
        bill_to_idx = next((i for i, ln in enumerate(lines) if ln.strip().lower() in COUNTERPARTY_SECTION_HEADINGS), None)
        search_text = "\n".join(lines[bill_to_idx:]) if bill_to_idx is not None else text
        all_gstins = list(dict.fromkeys(GSTIN_RE.findall(search_text)))
        if len(all_gstins) == 1:
            gstin = all_gstins[0]
        elif len(all_gstins) > 1:
            warnings.append(f"Found {len(all_gstins)} possible GSTINs on the page; couldn't tell which is the counterparty's, so it was left blank.")
    fields["counterparty_gstin"] = gstin.upper() if gstin else None

    pan_raw = _find_label_value(lines, PAN_LABELS, block) if block else _find_label_value(lines, PAN_LABELS)
    pan_match = PAN_RE.search(pan_raw) if pan_raw else None
    # The label-match above sometimes grabs the next line's text when a
    # 'PAN :' cell renders with no value at all (e.g. an overseas
    # customer's "Overseas" note sitting right under a blank PAN field) —
    # validating against the actual PAN format filters that kind of
    # false match out instead of filling the form with junk.
    fields["counterparty_pan"] = pan_match.group(0).upper() if pan_match else None

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

    # allow_same_line_no_colon=True (not just for OCR'd docs): plenty of
    # real, text-layer PDFs render "Total $25.00" or "Sub-Total 25.00" as
    # one line with no colon at all — this isn't an OCR-specific quirk, so
    # gating it to used_ocr was silently failing on ordinary digital
    # invoices. value_check=_looks_like_money still guards against false
    # positives either way.
    fields["subtotal"] = _parse_amount(_find_label_value(lines, SUBTOTAL_LABELS, value_check=_looks_like_money, allow_same_line_no_colon=True))
    fields["tax_amount"] = _parse_amount(_find_label_value(lines, TAX_LABELS, value_check=_looks_like_money, allow_same_line_no_colon=True))

    strong = _find_all_label_values(lines, TOTAL_STRONG_LABELS, value_check=_looks_like_money)
    total_raw = strong[-1] if strong else _find_label_value(
        lines, TOTAL_WEAK_LABELS, value_check=_looks_like_money, allow_same_line_no_colon=True
    )
    fields["total"] = _parse_amount(total_raw)
    if fields["total"] is None:
        warnings.append("Could not confidently find a total amount; please enter it manually.")

    fields["currency"] = _detect_currency(text, total_raw)

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

    # Extra invoice-form fields (PO reference, delivery, terms, GST
    # place-of-supply) beyond the original field set — best-effort,
    # same label-matching approach as everything above.
    fields["po_number"] = _clean_or_none(_find_label_value(lines, PO_NUMBER_LABELS, allow_same_line_no_colon=used_ocr))
    fields["po_date"] = _parse_date(_find_label_value(lines, PO_DATE_LABELS))
    fields["expected_delivery_date"] = _parse_date(_find_label_value(lines, DELIVERY_DATE_LABELS))
    fields["payment_terms"] = _find_label_value(lines, PAYMENT_TERMS_LABELS, allow_same_line_no_colon=True)
    fields["place_of_supply"] = _find_label_value(lines, PLACE_OF_SUPPLY_LABELS, allow_same_line_no_colon=used_ocr)

    # Bill To / Ship To name + address blocks — read directly from the
    # lines following each heading rather than a single label lookup,
    # since an address is several lines, not one "Label: value" pair.
    bill_name, bill_address = _extract_name_and_address(lines, set(COUNTERPARTY_SECTION_HEADINGS))
    if bill_name and not fields.get("counterparty_name"):
        fields["counterparty_name"] = bill_name
    fields["bill_to_address"] = bill_address

    ship_name, ship_address = _extract_name_and_address(lines, {"ship to"})
    fields["ship_to_name"] = ship_name
    fields["ship_to_address"] = ship_address

    # Line items: only attempted for real text-layer PDFs (needs the
    # PDF's own drawn table-cell borders, same constraint as the
    # pdf_table_utils fallback used above for due/invoice date). A
    # scanned/photographed page has no cell borders to detect, so this
    # is skipped for OCR'd documents rather than guessing from raw text.
    items = []
    if not used_ocr:
        from app.services.pdf_table_utils import extract_line_items
        items = extract_line_items(pdf_bytes)
    if not items:
        warnings.append("Could not read a line-items table from this file; please add items manually.")

    return {"fields": fields, "items": items, "warnings": warnings, "raw_text_available": True, "used_ocr": used_ocr}
