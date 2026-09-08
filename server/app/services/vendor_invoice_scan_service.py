"""
Scans a vendor's own invoice PDF (a bill RECEIVED from them) and
extracts the fields the Add Vendor Invoice form uses.

This is the mirror of invoice_pdf_scan_service.py, but inverted: on a
Sales Invoice we issue, OUR OWN details are the letterhead and the
"Bill To" block is the customer we care about extracting. Here, the
document is the VENDOR'S invoice to US — so their letterhead IS the
party we want (vendor_name/gstin/pan/email/phone/address), and if the
document has its own "Bill To"/"Customer" block at all, that's actually
OUR OWN company's details as their customer, which is irrelevant here
and used only as a boundary marker for where the vendor's letterhead
region ends.

Line items, invoice number/dates, money fields, and currency detection
all reuse the exact same logic as invoice_pdf_scan_service.py, since
those aren't perspective-dependent.
"""
import re
from typing import Optional

from app.services.po_pdf_scan_service import (
    _normalize_lines, _find_label_value, _parse_date, _parse_amount,
    _looks_like_money, _read_document_text, _norm_key, EMAIL_RE, PHONE_RE, GSTIN_RE,
)
from app.services.invoice_pdf_scan_service import (
    INVOICE_NUMBER_LABELS, SUBTOTAL_LABELS, TAX_LABELS, TOTAL_STRONG_LABELS,
    TOTAL_WEAK_LABELS, BALANCE_DUE_LABELS, INVOICE_DATE_LABELS, DUE_DATE_LABELS,
    PAYMENT_TERMS_LABELS, PLACE_OF_SUPPLY_LABELS, PAN_RE, _clean_or_none,
    _detect_currency,
)
from app.services.po_pdf_scan_service import _find_all_label_values

# Any of these marks the end of the vendor's own letterhead region and
# the start of "our own company as their customer" — everything from
# here onward is ignored for vendor-identity purposes, since it
# describes us, not them. Checked as a substring/word match within a
# line, not exact-line equality — real PDFs often collapse a two-column
# layout into one extracted line, e.g. "Invoice Details: Bill To:",
# where "bill to" never appears alone on its own line at all.
CUSTOMER_SECTION_HEADINGS = ("bill to", "customer details", "client details", "invoice to", "billed to", "sold to")
_GENERIC_TITLE_LINES = {
    "tax invoice", "invoice", "bill", "receipt", "credit note", "debit note",
    "original for recipient", "original", "duplicate for transporter",
    "duplicate for supplier", "duplicate", "triplicate", "duplicate for recipient",
    "triplicate for supplier",
}
_LETTERHEAD_STOP_KEYWORDS = ("gstin", "cin:", "cin ", "pan:", "pan ", "tel:", "tel ", "phone:", "ph:", "www.")
_INVOICE_NUMBER_LINE_RE = re.compile(r"^#\s*[A-Za-z0-9][A-Za-z0-9\-/.]{3,40}$")
_JUNK_NAME_RE = re.compile(r"^[\d.,$₹\-\s]+$")
_ADDRESS_START_RE = re.compile(r"^(no\.|plot|#\d|door no|survey no|\d)", re.IGNORECASE)
_PAGE_NUMBER_RE = re.compile(r"^page\s+\d+\s+of\s+\d+$", re.IGNORECASE)
_BARE_HEADING_RE = re.compile(r"^[A-Za-z][A-Za-z\s]{1,30}:$")  # e.g. "Provided by:" — a heading with nothing after it on the same line
_NON_NAME_KEYWORDS = (
    "sub-total", "sub total", "subtotal", "grand total", "balance due",
    "payment made", "items in total", "invoice date", "payment due date",
    "po date", "p.o.", "igst", "cgst", "sgst", "discount", "amount in words",
    "terms of payment", "authorized signatory", "e. & o.e", "total",
)
_MONEY_LIKE_RE = re.compile(r"[$₹£€]\s?\d|\d\s?[$₹£€]")
_LABEL_VALUE_RE = re.compile(r"^[A-Za-z0-9./\-]{2,20}$")
_CODE_LIKE_TAIL_RE = re.compile(r"[A-Za-z0-9]*\d[A-Za-z0-9]*[./\-][A-Za-z0-9]*\d?[A-Za-z0-9]*$")
# Other invoice metadata fields (invoice #, dates, PO#, etc.) that can
# render as a no-colon "Label value" line just like a vendor name would
# — e.g. "Invoice number CE7D0CF1-0006" or "Date of issue September 1,
# 2026" sitting right above the real letterhead in extraction order (see
# _name_near_gstin's docstring for why order isn't reliable). Rejecting
# by known-label PREFIX, not just the colon/money/keyword checks above,
# catches these even when they don't look like money and aren't in the
# fixed non-name phrase list.
_FIELD_LABEL_PREFIXES = tuple(dict.fromkeys(
    _norm_key(l) for l in (
        list(INVOICE_NUMBER_LABELS) + list(INVOICE_DATE_LABELS) + list(DUE_DATE_LABELS)
        + list(PAYMENT_TERMS_LABELS) + list(PLACE_OF_SUPPLY_LABELS)
        + ["po_number", "po number", "end_user", "order reference", "order date",
           "tax point date", "customer id", "reseller po", "license order no",
           "license sent to", "usermail", "name of state", "chamber of commerce",
           "vat number", "registration number", "company number"]
    )
))
# Email addresses found on a line labeled like these belong to US as the
# vendor's customer, not to the vendor — e.g. Zoho's "UserMail :
# uma@ourcompany.com" sits in the same header region as the vendor's own
# letterhead, above any "Bill To" heading, so the region-based extraction
# alone can't tell the two apart; excluding lines with these labels can.
_CUSTOMER_EMAIL_LABEL_KEYWORDS = ("usermail", "sent to", "shipped", "attn", "customer", "billed to")


def _is_label_value_line(raw: str) -> bool:
    """True for lines shaped like 'Some Label : CODE123' — a short,
    code-like value after a colon, with a short label before it. Covers
    the many field labels a scanned invoice can have beyond the fixed
    list already special-cased above (e.g. 'Preflex PAN : AAHCP5797R',
    'MSME No : KR03D0050939') without needing to enumerate every
    template's own label wording."""
    if ":" not in raw:
        return False
    label_part, _, value_part = raw.partition(":")
    value_part = value_part.strip()
    return bool(value_part) and bool(_LABEL_VALUE_RE.match(value_part)) and len(label_part.split()) <= 4


def _looks_like_a_name(s: Optional[str]) -> bool:
    """Rejects obvious non-names: too short, all digits/punctuation,
    address-line-shaped, contains a currency amount, a bare page-number
    footer, a bare heading with no value ("Provided by:"), a disclaimer
    line (often starts with '*'), or one of the many "this is actually a
    totals/summary row, not a company name" phrases that a naive
    first-plausible-line scan can otherwise pick up when a PDF's
    underlying text stream doesn't come out in visual top-to-bottom
    order (see _name_near_gstin below for why that happens and how it's
    worked around)."""
    if not s or len(s.strip()) < 3:
        return False
    if _JUNK_NAME_RE.match(s.strip()):
        return False
    if _ADDRESS_START_RE.match(s.strip()):
        return False
    if _MONEY_LIKE_RE.search(s):
        return False
    if _PAGE_NUMBER_RE.match(s.strip()):
        return False
    if _BARE_HEADING_RE.match(s.strip()):
        return False
    if s.strip().startswith("*"):
        return False
    if any(kw in s.lower() for kw in _NON_NAME_KEYWORDS):
        return False
    if _norm_key(s).startswith(_FIELD_LABEL_PREFIXES):
        return False
    # General fallback for metadata labels not on the fixed list above:
    # a line whose LAST word looks like a reference code (mixes digits
    # with a dot/slash/hyphen, e.g. "NL8538.75.273.B01", a VAT/company
    # registration number) is essentially never how a real company name
    # ends, whatever the label before it happens to say.
    last_word = s.strip().split()[-1] if s.strip().split() else ""
    if _CODE_LIKE_TAIL_RE.search(last_word):
        return False
    # A bare long digit string as the last word (5+ digits, no
    # separators) is essentially always a registration/reference number
    # tacked onto a metadata label ("Chamber of Commerce 60360461"),
    # never how a real company name ends.
    if last_word.isdigit() and len(last_word) >= 5:
        return False
    return True


def _name_near_gstin(lines: list, end: int) -> Optional[str]:
    """Fallback for when the sequential 'first line of the document'
    heuristic fails — some PDFs' underlying text stream doesn't come out
    in visual reading order at all (metadata that visually sits in a
    right-hand column can extract *before* the letterhead), which
    defeats a simple top-down scan. GSTIN is a much more reliably
    located anchor (it's a distinctive, regex-matchable token), and the
    vendor's name is almost always one of the few lines immediately
    above it on a real invoice — so walk backward from wherever the
    GSTIN actually landed instead of trusting line order."""
    gstin_idx = None
    for i in range(end):
        if GSTIN_RE.search(lines[i]):
            gstin_idx = i
            break
    if gstin_idx is None:
        return None

    for i in range(gstin_idx - 1, max(gstin_idx - 8, -1), -1):
        raw = lines[i].strip()
        if not raw:
            continue
        low = raw.lower()
        if any(kw in low for kw in _LETTERHEAD_STOP_KEYWORDS) or "@" in raw:
            continue
        if low in _GENERIC_TITLE_LINES:
            continue
        if _is_label_value_line(raw):
            continue
        if _looks_like_a_name(raw):
            return raw
    return None


def _extract_vendor_identity(lines: list) -> dict:
    """Reads the vendor's name/address from whatever sits above the
    'Bill To' style heading (or the whole document, if there isn't one).
    Best-effort: assumes the first substantive line of the document is
    the vendor's name, which holds for the large majority of invoice
    templates but isn't guaranteed — logos-as-images or heavily
    stylized headers can defeat this."""
    end = len(lines)
    for i, ln in enumerate(lines):
        low = ln.strip().lower()
        if any(h in low for h in CUSTOMER_SECTION_HEADINGS):
            end = i
            break

    name = None
    address_lines = []
    for i in range(end):
        raw = lines[i].strip()
        if not raw:
            if name is not None:
                break
            continue
        low = raw.lower()
        if name is None:
            if low in _GENERIC_TITLE_LINES or _INVOICE_NUMBER_LINE_RE.match(raw):
                continue
            if _is_label_value_line(raw):
                continue
            if not _looks_like_a_name(raw):
                continue
            name = raw
            continue
        if any(kw in low for kw in _LETTERHEAD_STOP_KEYWORDS) or "@" in raw:
            break
        address_lines.append(raw.rstrip(","))

    if not _looks_like_a_name(name):
        # The sequential scan above assumes the text stream comes out in
        # roughly the document's visual top-to-bottom order, which
        # doesn't always hold — fall back to anchoring off the GSTIN
        # instead, and don't bother collecting an address in this case
        # since we no longer have a reliable starting point for it.
        fallback_name = _name_near_gstin(lines, end)
        if fallback_name:
            return {"name": fallback_name, "address": None, "region_end": end}
        name = None
        address_lines = []

    return {
        "name": name,
        "address": ", ".join(address_lines) if address_lines else None,
        "region_end": end,
    }


def extract_vendor_invoice_fields(pdf_bytes: bytes, filename: str = "upload.pdf") -> dict:
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
    identity = _extract_vendor_identity(lines)
    letterhead_lines = lines[:identity["region_end"]]
    letterhead_text = "\n".join(letterhead_lines)

    fields = {}

    fields["vendor_name"] = identity["name"]
    fields["vendor_address"] = identity["address"]

    vendor_gstins = list(dict.fromkeys(GSTIN_RE.findall(letterhead_text)))
    if len(vendor_gstins) >= 1:
        fields["vendor_gstin"] = vendor_gstins[0].upper()
    else:
        fields["vendor_gstin"] = None
        if len(list(dict.fromkeys(GSTIN_RE.findall(text)))) > 1:
            warnings.append("Multiple GSTINs found on the page; couldn't confidently tell which is the vendor's, so it was left blank.")

    pan_candidates = [m for m in PAN_RE.findall(letterhead_text)]
    fields["vendor_pan"] = pan_candidates[0].upper() if len(set(pan_candidates)) == 1 else None

    # Excludes lines labeled in a way that clearly means "this is our own
    # email as their customer" (e.g. Zoho's "UserMail : ..." field, which
    # sits in the same header region as the vendor's own letterhead,
    # above any "Bill To" heading — the region boundary alone can't
    # distinguish the two).
    email_source_lines = [
        ln for ln in letterhead_lines
        if not any(kw in ln.lower() for kw in _CUSTOMER_EMAIL_LABEL_KEYWORDS)
    ]
    vendor_emails = list(dict.fromkeys(EMAIL_RE.findall("\n".join(email_source_lines))))
    if len(vendor_emails) == 1:
        fields["vendor_email"] = vendor_emails[0]
    else:
        fields["vendor_email"] = None
        if len(vendor_emails) > 1:
            warnings.append("Multiple emails found near the vendor's letterhead; please confirm the correct one.")

    vendor_phones = list(dict.fromkeys(PHONE_RE.findall(letterhead_text)))
    if len(vendor_phones) == 1:
        fields["vendor_phone"] = re.sub(r"[\s\-]", "", vendor_phones[0])
    else:
        fields["vendor_phone"] = None
        if len(vendor_phones) > 1:
            warnings.append("Multiple phone numbers found near the vendor's letterhead; please confirm the correct one.")

    fields["invoice_number"] = _find_label_value(lines, INVOICE_NUMBER_LABELS, allow_same_line_no_colon=True)
    if not fields["invoice_number"]:
        for ln in lines:
            m = _INVOICE_NUMBER_LINE_RE.match(ln.strip())
            if m:
                fields["invoice_number"] = ln.strip().lstrip("#").strip()
                break

    fields["invoice_date"] = _parse_date(_find_label_value(lines, INVOICE_DATE_LABELS, allow_same_line_no_colon=True))
    fields["payment_due_date"] = _parse_date(_find_label_value(lines, DUE_DATE_LABELS, allow_same_line_no_colon=True))
    fields["payment_terms"] = _find_label_value(lines, PAYMENT_TERMS_LABELS, allow_same_line_no_colon=True)
    fields["place_of_supply"] = _find_label_value(lines, PLACE_OF_SUPPLY_LABELS, allow_same_line_no_colon=used_ocr)

    fields["subtotal"] = _parse_amount(_find_label_value(lines, SUBTOTAL_LABELS, value_check=_looks_like_money, allow_same_line_no_colon=True))
    fields["tax_amount"] = _parse_amount(_find_label_value(lines, TAX_LABELS, value_check=_looks_like_money, allow_same_line_no_colon=True))

    strong_totals = _find_all_label_values(lines, TOTAL_STRONG_LABELS, value_check=_looks_like_money, allow_same_line_no_colon=True)
    total_raw = strong_totals[-1] if strong_totals else _find_label_value(
        lines, TOTAL_WEAK_LABELS, value_check=_looks_like_money, allow_same_line_no_colon=True
    )
    if not total_raw:
        total_raw = _find_label_value(lines, BALANCE_DUE_LABELS, value_check=_looks_like_money, allow_same_line_no_colon=True)
    fields["total"] = _parse_amount(total_raw)
    fields["balance_due"] = fields["total"]
    fields["currency"] = _detect_currency(text, total_raw)

    if not fields["invoice_number"]:
        warnings.append("Could not find an invoice number on this page; please enter it manually.")
    if not fields["vendor_name"]:
        warnings.append("Could not confidently identify the vendor's name; please enter it manually.")

    items = []
    if not used_ocr:
        from app.services.pdf_table_utils import extract_line_items
        items = extract_line_items(pdf_bytes)
    if not items:
        warnings.append("Could not read a line-items table from this file; please add items manually.")

    return {"fields": fields, "items": items, "warnings": warnings, "raw_text_available": True, "used_ocr": used_ocr}
