"""
Scans an uploaded Purchase Order PDF and extracts the same fields the CSV/Excel
importer uses (po_number, vendor, gstin, vendor_email, vendor_phone, amount,
due_date, payment_window_days).

Design notes (matches what was agreed with the user before building this):
- Works on text-based PDFs only (Word/Tally/Zoho exports, fillable templates).
  Scanned/photographed PDFs have no text layer and will come back empty; the
  route surfaces that as a clear error rather than silently returning nothing.
- The buyer's own letterhead info (address/email/phone/GSTIN at the top of
  the page) is noise. To avoid picking it up, we look for a "vendor block":
  the text between a heading like "Vendor Details" / "Supplier" / "Bill From"
  and the next heading, and prefer matches found inside that block.
- Multiple money figures (subtotal/tax/total) are common; "Grand Total" /
  "Total" / "Net Amount" / "Amount Payable" beats a bare "Amount" label.
- Ambiguous fields (two equally-plausible candidates, no way to tell them
  apart) are left blank with a warning instead of guessing.
"""
import io
import re
from datetime import datetime
from typing import Optional

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - fallback for older pinned deps
    from PyPDF2 import PdfReader  # type: ignore


# ---- label alias sets (mirrors CSVImportModal.jsx's MAPPINGS.DEFAULT) ----

PO_NUMBER_LABELS = ["po number", "po #", "po no", "purchase order#", "purchase order number", "voucher no", "reference"]
VENDOR_LABELS = ["vendor name", "vendor", "supplier name", "supplier", "party name", "seller", "billed by"]
GSTIN_LABELS = ["vendor gstin", "supplier gstin", "seller gstin", "gstin", "gstin/uin", "gst no"]
EMAIL_LABELS = ["vendor email", "supplier email", "seller email", "email"]
PHONE_LABELS = ["vendor mobile", "vendor phone", "supplier mobile", "supplier phone", "mobile", "phone", "contact"]
AMOUNT_STRONG_LABELS = ["grand total", "total amount", "net amount", "amount payable", "amount due"]
AMOUNT_WEAK_LABELS = ["total", "amount"]
DUE_DATE_LABELS = ["due date", "payment due", "due on"]
PO_DATE_LABELS = ["po date", "date", "invoice date", "bill date", "voucher date"]
PAYMENT_WINDOW_LABELS = ["payment window", "credit period", "payment days"]

VENDOR_SECTION_HEADINGS = ["vendor details", "vendor information", "supplier details", "bill from", "vendor:", "supplier:"]
SECTION_HEADING_HINTS = ["items", "item details", "payment terms", "terms & conditions", "terms and conditions", "bank details", "authorized signatory"]

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+?91[\s\-]?)?[6-9]\d{9}\b")
GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}\d[Z]{1}[A-Z\d]{1}\b")
MONEY_RE = re.compile(r"₹?\s*[\d,]+(?:\.\d{1,2})?")
DATE_RE = re.compile(r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}-\d{2}-\d{2})\b")

DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"]


def _normalize_lines(text: str) -> list:
    return [ln.strip() for ln in text.split("\n") if ln.strip()]


def _norm_key(s: str) -> str:
    """Strips a trailing colon/dash, drops any parenthetical, collapses
    whitespace, and removes spaces around '#' so 'Invoice#', 'Invoice #'
    and 'invoice number' style variants all normalize consistently.
    Internal hyphens are treated as spaces too — 'Sub-Total' and 'sub
    total' must normalize to the same key, since PDF templates render
    the same field either way and a mismatch here silently makes the
    field invisible to every _find_label_value() lookup."""
    s = re.sub(r"\([^)]*\)", "", s)  # drop parentheticals, e.g. "(18% GST)"
    s = s.strip().rstrip(":-").strip().lower()
    s = re.sub(r"\s*#\s*", "#", s)
    s = s.replace("-", " ")
    s = re.sub(r"\s+", " ", s)
    return s


_TRAILING_LABEL_RE = re.compile(r"\s+[A-Z][A-Za-z0-9./#-]*(?:\s[A-Za-z][A-Za-z0-9./#-]*){0,2}\s*:")


def _line_key_value(line: str):
    """Splits a line into (key, value) at the first colon, or the first
    ' - ' dash-with-spaces (so we don't split GSTINs/phone numbers that
    contain bare hyphens). Returns (key, None) if there's no separator —
    the caller then checks the NEXT line for the value instead.

    If the line actually holds TWO label:value pairs run together (e.g.
    "Invoice#: PS/INV/643   LUT ARN: AA29...", common when a PDF places
    two short fields on one visual row), the value is truncated right
    before the next label starts, so it doesn't swallow the second
    field's text too."""
    if ":" in line:
        key, _, val = line.partition(":")
        val = val.strip() or None
        if val:
            m = _TRAILING_LABEL_RE.search(val)
            if m:
                val = val[:m.start()].strip() or None
        return key.strip(), val
    m = re.match(r"^(.*?)\s+-\s+(.+)$", line)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return line.strip(), None


def _looks_like_money(s: Optional[str]) -> bool:
    """True only for things that plausibly ARE a money value — requires a
    currency symbol, a thousands comma, a decimal amount, or a 3+ digit
    number, so a bare small integer (e.g. a table row number '1') doesn't
    get accepted as an amount just because it's numeric. Searches within
    the string rather than anchoring to the start, since some PDF fonts
    render the ₹ symbol as a stray glyph (e.g. '■') right before the digits."""
    if not s:
        return False
    m = MONEY_RE.search(s)
    if not m:
        return False
    val = m.group(0)
    digits = re.sub(r"\D", "", val)
    if not digits:
        return False
    return ("₹" in s) or ("," in val) or ("." in val) or (len(digits) >= 3)


def _find_label_value(lines: list, labels: list, search_range=None, value_check=None, allow_same_line_no_colon=False) -> Optional[str]:
    """
    Looks for a line whose KEY (the text before ':' or ' - ') exactly
    matches one of `labels` (ignoring parentheticals/spacing), and returns
    the value — either on the same line, or on the next line if the label
    line has no value of its own (common in table-laid-out PDF exports).

    `value_check`, if given, is a function(value) -> bool used to reject an
    otherwise-matching candidate that doesn't look like the right kind of
    data (e.g. a table column header like "Amount" grabbing the next row's
    serial number "1" as if it were a total — value_check=_looks_like_money
    rejects that because "1" doesn't look like a real amount).

    `allow_same_line_no_colon`: OCR'd text frequently drops the colon
    between a label and its value entirely (table cells run together,
    e.g. "Sub Total 68,930.00" instead of "Sub Total: 68,930.00"). When
    True, and no colon/next-line match is found, also tries "line starts
    with the label, rest of the line is the value" — only used as a last
    resort, and still gated by value_check to avoid loose false positives.
    """
    norm_labels = [_norm_key(l) for l in labels]
    rng = search_range if search_range is not None else range(len(lines))
    for i in rng:
        key, val = _line_key_value(lines[i])
        if _norm_key(key) not in norm_labels:
            continue
        if val:
            if value_check and not value_check(val):
                continue
            return val
        if i + 1 < len(lines):
            candidate = lines[i + 1].strip()
            if value_check and not value_check(candidate):
                continue
            return candidate
    if allow_same_line_no_colon:
        for i in rng:
            line_norm = _norm_key(lines[i])
            for label in labels:
                nl = _norm_key(label)
                if line_norm.startswith(nl):
                    rest = lines[i][len(label):].strip() if lines[i].lower().startswith(label) else lines[i][len(nl):].strip()
                    if rest and (not value_check or value_check(rest)):
                        return rest
    return None


def _find_all_label_values(lines: list, labels: list, search_range=None, value_check=None) -> list:
    """Same as _find_label_value but returns every match found (for ambiguity checks)."""
    norm_labels = [_norm_key(l) for l in labels]
    rng = search_range if search_range is not None else range(len(lines))
    found = []
    for i in rng:
        key, val = _line_key_value(lines[i])
        if _norm_key(key) not in norm_labels:
            continue
        if val:
            if value_check and not value_check(val):
                continue
            found.append(val)
        elif i + 1 < len(lines):
            candidate = lines[i + 1].strip()
            if value_check and not value_check(candidate):
                continue
            found.append(candidate)
    return found


def _vendor_block_range(lines: list):
    """Returns the (start, end) line-index range belonging to the vendor section, if found."""
    start = None
    for i, ln in enumerate(lines):
        if any(h in ln.lower() for h in VENDOR_SECTION_HEADINGS):
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


def _parse_date(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    m = DATE_RE.search(raw)
    candidate = m.group(1) if m else raw.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(candidate, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_amount(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    m = MONEY_RE.search(raw)
    if not m:
        return None
    cleaned = m.group(0).replace("₹", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _read_document_text(pdf_bytes: bytes, filename: str) -> dict:
    """
    Shared by both extract_po_fields() and extract_invoice_fields() — reads
    a PDF's text layer directly when there is one, falling back to OCR
    (scanned PDFs / photographed uploads) otherwise, and covers the two
    "nothing readable" cases identically for both document types.

    Returns {"text": str, "used_ocr": bool, "early_result": dict | None}.
    When "early_result" is not None, the caller should return it
    immediately as-is — it's the full extract_*_fields() response for a
    document that couldn't be read at all.
    """
    from app.services.ocr_utils import IMAGE_EXTENSIONS, get_document_text

    pdf_text = ""
    is_image = filename.lower().endswith(IMAGE_EXTENSIONS)

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
            "text": "", "used_ocr": False,
            "early_result": {
                "fields": {},
                "warnings": [
                    "This looks like a scanned/photographed document with no embedded text, and OCR isn't "
                    "available on this server right now (missing tesseract/poppler). Ask your admin to enable "
                    "OCR support, or upload a text-based PDF instead."
                ],
                "raw_text_available": False,
                "used_ocr": False,
            },
        }

    if len(text.strip()) < 10:
        return {
            "text": "", "used_ocr": used_ocr,
            "early_result": {
                "fields": {},
                "warnings": ["Couldn't find or recognize any text in this file."],
                "raw_text_available": False,
                "used_ocr": used_ocr,
            },
        }

    return {"text": text, "used_ocr": used_ocr, "early_result": None}


def extract_po_fields(pdf_bytes: bytes, filename: str = "upload.pdf") -> dict:
    """
    Returns:
        {
          "fields": { po_number, vendor, gstin, vendor_email, vendor_phone,
                      amount, due_date, payment_window_days },
          "warnings": [ "human readable notes about ambiguity / missing fields" ],
          "raw_text_available": bool,
          "used_ocr": bool
        }
    """
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
    vendor_range = _vendor_block_range(lines)

    fields = {}

    # PO number — page-wide, only one usually appears
    po_number = _find_label_value(lines, PO_NUMBER_LABELS, allow_same_line_no_colon=used_ocr)
    fields["po_number"] = po_number

    # Vendor name — prefer inside vendor block if we found one
    vendor = _find_label_value(lines, VENDOR_LABELS, vendor_range, allow_same_line_no_colon=used_ocr) if vendor_range else None
    if not vendor:
        vendor = _find_label_value(lines, VENDOR_LABELS, allow_same_line_no_colon=used_ocr)
    fields["vendor"] = vendor

    # GSTIN — vendor-block first, else page-wide with ambiguity check
    if vendor_range:
        gstin = _find_label_value(lines, GSTIN_LABELS, vendor_range, allow_same_line_no_colon=used_ocr)
    else:
        gstin = None
    if not gstin:
        all_gstins = list(dict.fromkeys(GSTIN_RE.findall(text)))
        if len(all_gstins) == 1:
            gstin = all_gstins[0]
        elif len(all_gstins) > 1:
            warnings.append(f"Found {len(all_gstins)} possible GSTINs on the page; couldn't tell which is the vendor's, so it was left blank.")
    fields["gstin"] = gstin.upper() if gstin else None

    # Vendor email — vendor-block only; if none found there, don't fall back
    # page-wide (that's how the buyer's own letterhead/support email leaks in)
    email = _find_label_value(lines, EMAIL_LABELS, vendor_range) if vendor_range else None
    if not email:
        candidates = EMAIL_RE.findall(text)
        if vendor_range:
            in_block = [c for c in candidates if any(c in lines[i] for i in vendor_range)]
            if len(in_block) == 1:
                email = in_block[0]
            elif len(in_block) > 1:
                warnings.append("Multiple emails found in the vendor section; please confirm the correct one.")
        elif len(set(candidates)) == 1:
            email = candidates[0]
        elif len(set(candidates)) > 1:
            warnings.append("Multiple emails found on the page and no clear vendor section; vendor email left blank — please fill it in.")
    fields["vendor_email"] = email

    # Vendor phone — same approach as email
    phone = _find_label_value(lines, PHONE_LABELS, vendor_range) if vendor_range else None
    if phone:
        m = PHONE_RE.search(phone)
        phone = m.group(0) if m else phone
    if not phone:
        candidates = PHONE_RE.findall(text)
        if vendor_range:
            in_block = [c for c in candidates if any(c in lines[i] for i in vendor_range)]
            if len(in_block) == 1:
                phone = in_block[0]
            elif len(in_block) > 1:
                warnings.append("Multiple phone numbers found in the vendor section; please confirm the correct one.")
        elif len(set(candidates)) == 1:
            phone = candidates[0]
        elif len(set(candidates)) > 1:
            warnings.append("Multiple phone numbers found on the page and no clear vendor section; vendor mobile left blank — please fill it in.")
    fields["vendor_phone"] = re.sub(r"[\s\-]", "", phone) if phone else None

    # Amount — strong labels ("Grand Total" etc.) beat weak ones; if several
    # strong matches exist, use the last one (grand total is printed last).
    # value_check=_looks_like_money stops a bare table column header like
    # "Amount" from grabbing an unrelated number (e.g. a row's serial "1").
    # allow_same_line_no_colon helps with OCR'd tables that drop the colon
    # entirely (e.g. "Total 68,930.00" with no ":" between them).
    strong_matches = _find_all_label_values(lines, AMOUNT_STRONG_LABELS, value_check=_looks_like_money)
    amount_raw = strong_matches[-1] if strong_matches else _find_label_value(
        lines, AMOUNT_WEAK_LABELS, value_check=_looks_like_money, allow_same_line_no_colon=used_ocr
    )
    fields["amount"] = _parse_amount(amount_raw)
    if fields["amount"] is None:
        warnings.append("Could not confidently find a total amount; please enter it manually.")

    # Due date — explicit "Due Date" label, even if it's mid-sentence
    due_raw = _find_label_value(lines, DUE_DATE_LABELS)
    if not due_raw:
        # try to catch "Due Date: 29-09-2026)" style inline mentions across the whole text
        m = re.search(r"due date\s*[:\-]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
        if m:
            due_raw = m.group(1)
    fields["due_date"] = _parse_date(due_raw)
    if not fields["due_date"] and not used_ocr:
        from app.services.pdf_table_utils import find_table_header_value
        table_val = find_table_header_value(pdf_bytes, DUE_DATE_LABELS)
        fields["due_date"] = _parse_date(table_val)
    if not fields["due_date"]:
        warnings.append("Could not find a due date; please enter one manually.")

    # Payment window (days) — only trust an explicit standalone number next
    # to a matching label; won't try to parse "within 45 days" out of prose
    window_raw = _find_label_value(lines, PAYMENT_WINDOW_LABELS)
    window_days = None
    if window_raw:
        m = re.search(r"\d+", window_raw)
        if m:
            window_days = int(m.group(0))
    fields["payment_window_days"] = window_days or 50
    if not window_days:
        warnings.append("No explicit payment window found; defaulted to 50 days.")

    if not fields.get("po_number"):
        warnings.append("Could not find a PO Number on this page; please enter it manually.")
    if not fields.get("vendor"):
        warnings.append("Could not find a Vendor Name; please enter it manually.")

    return {"fields": fields, "warnings": warnings, "raw_text_available": True, "used_ocr": used_ocr}
