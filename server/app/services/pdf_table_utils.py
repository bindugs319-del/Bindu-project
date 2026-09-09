"""
Table-aware fallback for fields that sit inside a multi-column header/value
table — e.g. a single row reading "Invoice Date | Payment Due Date | PO# |
PO Date | PAN | MSME No" with the actual values in the row below.

Why this needs its own module: plain sequential text extraction (used
everywhere else in po_pdf_scan_service.py / invoice_pdf_scan_service.py)
reads a page as a flat top-to-bottom stream of lines, so it has no idea
which value belongs under which header once there's more than one column
— and a cell whose text wraps onto a second line makes a naive
"line N lines later" guess actively wrong. pdfplumber reconstructs the
actual table grid (using the PDF's drawn cell borders), so a header and
its value are still correctly paired even if the cell text wraps.

This is intentionally used only as a FALLBACK after the normal line-based
matching fails, and only for real (non-OCR) PDFs — pdfplumber needs
vector-drawn table lines, which a scanned/photographed page doesn't have.
"""
import io
import re
from typing import Optional

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from app.services.po_pdf_scan_service import _norm_key, _parse_amount


def table_extraction_available() -> bool:
    return pdfplumber is not None


# Substrings (post-_norm_key, which only lowercases/collapses whitespace —
# it does NOT strip spaces around "&" or "/", so labels here keep the
# spacing real header cells actually normalize to, e.g. "Item & Description"
# -> "item & description", not "itemdescription") checked as "does this
# header cell CONTAIN one of these", not exact-match. Real templates wrap
# a lot of extra text into a header cell (row-number columns merged in,
# "Sl. No. Item Description", etc.), so exact matching was silently
# missing common real invoices.
ITEM_DESC_LABELS = ("description", "particulars", "item")
ITEM_HSN_LABELS = ("hsn", "sac")
ITEM_QTY_LABELS = ("qty", "quantity")
ITEM_RATE_LABELS = ("rate", "price")
ITEM_AMOUNT_LABELS = ("amount", "total", "value")
# Row description text that means "this isn't a real item row, it's a
# summary line" — also substring-checked for the same reason.
_ITEM_SKIP_DESC = ("total", "amount in words", "items in total")
# Markers checked against the WHOLE row (every column, not just the
# description column) that mean the items table has ended entirely —
# extraction stops as soon as one is seen, rather than merely skipping
# that one row, since everything after it is summary/payment/legal
# boilerplate. This matters most when a borderless-table strategy has
# lumped the whole page into a single "table": without an explicit stop,
# extraction would otherwise keep treating footer text (payment
# instructions, bank details, T&Cs) as further item rows.
_ITEM_TABLE_END_KEYWORDS = (
    "subtotal", "sub total", "grand total", "amount due", "balance due",
    "amount in words", "total in words", "items in total",
    "tax to be paid", "reverse charge", "wire funds", "beneficiary",
    "swift code", "authorized signature", "authorised signature",
    "bank name and address", "please remit payment", "for wire transfer",
    "wire transfer routing", "ach routing", "electronic payment details",
    "thank you for your purchase", "thank you for your business",
    "terms of payment", "all charges are in",
)
_PAGE_OF_RE = re.compile(r"\bpage\s+\d+\s+of\s+\d+\b", re.IGNORECASE)


def _find_col(norm_header, labels):
    for i, h in enumerate(norm_header):
        if any(lbl in h for lbl in labels):
            return i
    return None


def _merge_header_rows(row_a, row_b):
    """Concatenates two rows cell-by-cell. Needed because a text-alignment
    (borderless) table strategy splits a header cell that visually wraps
    onto two lines — e.g. "Unit price" / "(excl. tax)" — into two separate
    table rows at the same column position, rather than one cell
    containing both lines."""
    width = max(len(row_a), len(row_b))
    merged = []
    for i in range(width):
        a = row_a[i] if i < len(row_a) and row_a[i] else ""
        b = row_b[i] if i < len(row_b) and row_b[i] else ""
        merged.append((a + " " + b).strip())
    return merged


def _find_header_row(table):
    """Scans every row of the table (not just row 0) for one that looks
    like an items-table header, also trying it merged with the row right
    after it (see _merge_header_rows) in case the real header wraps
    across two visual lines. This matters most for borderless/text-based
    table detection, which can lump an entire page — everything above
    the real header included — into a single "table", so the header is
    rarely still at index 0.

    Returns (first_item_row_index, desc_idx, qty_idx, rate_idx,
    amount_idx, hsn_idx), or None if no row looks like a header.
    """
    for i, row in enumerate(table):
        # A single-column (or otherwise too-narrow) row can't be a real
        # header — a real items table always separates description from
        # its numeric columns. Skipping this outright also protects
        # against a whole-page-as-one-giant-cell false table (a known
        # pdfplumber artifact on some invoice templates): that blob cell
        # contains every label word mashed together, which would
        # otherwise satisfy the checks below with every index pointing
        # at the same single column.
        if len(row) < 2:
            continue
        candidates = [(row, i + 1)]
        if i + 1 < len(table):
            candidates.append((_merge_header_rows(row, table[i + 1]), i + 2))
        for header_row, next_idx in candidates:
            norm_header = [_norm_key((c or "").replace("\n", " ")) for c in header_row]
            desc_idx = _find_col(norm_header, ITEM_DESC_LABELS)
            qty_idx = _find_col(norm_header, ITEM_QTY_LABELS)
            rate_idx = _find_col(norm_header, ITEM_RATE_LABELS)
            amount_idx = _find_col(norm_header, ITEM_AMOUNT_LABELS)
            hsn_idx = _find_col(norm_header, ITEM_HSN_LABELS)
            if desc_idx is None or (qty_idx is None and amount_idx is None):
                continue
            # A real header never has two different roles (description
            # vs. a numeric/HSN column) landing on the very same column
            # index — that only happens when the "header" is actually
            # one blob of merged text with no real column structure.
            other_idxs = {qty_idx, rate_idx, amount_idx, hsn_idx} - {None}
            if desc_idx in other_idxs:
                continue
            return next_idx, desc_idx, qty_idx, rate_idx, amount_idx, hsn_idx
    return None


def _items_from_tables(tables) -> list:
    """Shared row->item mapping, used by extract_line_items for each
    table-detection strategy it tries. Returns [] if none of the given
    tables looks like an items table."""
    for table in tables:
        if len(table) < 2:
            continue
        header_info = _find_header_row(table)
        if header_info is None:
            continue
        start_idx, desc_idx, qty_idx, rate_idx, amount_idx, hsn_idx = header_info

        items = []
        for row in table[start_idx:]:
            row_text_norm = _norm_key(" ".join((c or "") for c in row).replace("\n", " "))
            if any(kw in row_text_norm for kw in _ITEM_TABLE_END_KEYWORDS) or _PAGE_OF_RE.search(row_text_norm):
                break
            if desc_idx >= len(row):
                continue
            desc = (row[desc_idx] or "").replace("\n", " ").strip()
            if not desc:
                continue
            desc_norm = _norm_key(desc)
            if any(skip in desc_norm for skip in _ITEM_SKIP_DESC):
                continue

            def cell(idx, row=row):
                if idx is None or idx >= len(row) or not row[idx]:
                    return None
                return row[idx].replace("\n", "").strip()

            item = {"desc": desc}
            hsn_val = cell(hsn_idx)
            if hsn_val:
                item["hsn"] = hsn_val
            qty_val = _parse_amount(cell(qty_idx))
            if qty_val is not None:
                item["qty"] = qty_val
            rate_val = _parse_amount(cell(rate_idx))
            if rate_val is not None:
                item["rate"] = rate_val
            amount_val = _parse_amount(cell(amount_idx))
            if amount_val is not None:
                item["amount"] = amount_val

            # A row with a description but no qty/rate/amount/HSN of its
            # own is almost always the wrapped second (or third...) line
            # of the PREVIOUS row's description, not a genuinely separate
            # item — e.g. a subscription's "Sep 3, 2026–Sep 3, 2027" date
            # range printed under its own line. Fold it into the previous
            # item instead of creating a spurious item with no numbers.
            has_numeric_data = any(k in item for k in ("hsn", "qty", "rate", "amount"))
            if not has_numeric_data and items:
                items[-1]["desc"] = (items[-1]["desc"] + " " + desc).strip()
            else:
                items.append(item)

        if items:
            return items
    return []


def extract_line_items(pdf_bytes: bytes, max_pages: int = 3) -> list:
    """
    Best-effort extraction of an invoice/PO's line-items table. Tries
    pdfplumber's default (vector-line-based) table detection first, then
    falls back to its text-alignment-based detection for the many real
    templates that only visually align item columns without drawing
    actual vertical rules between them. Still needs a text layer (not a
    scanned/photographed page) either way. Returns [] if pdfplumber isn't
    available, or no page has anything that looks like an items table.
    """
    if not table_extraction_available():
        return []

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages[:max_pages]:
                for settings in (None, {"vertical_strategy": "text", "horizontal_strategy": "text"}):
                    try:
                        tables = page.extract_tables(settings) if settings else page.extract_tables()
                    except Exception:
                        continue
                    items = _items_from_tables(tables)
                    if items:
                        return items
    except Exception:
        return []
    return []


def find_table_header_value(pdf_bytes: bytes, labels: list, max_pages: int = 2) -> Optional[str]:
    """
    Looks through every table pdfplumber can detect on the first
    `max_pages` pages. If a header cell (first row of a table) matches one
    of `labels` (case-insensitively, ignoring how the cell's text wraps),
    returns the value in the SAME COLUMN from the row directly below it.
    Returns None if pdfplumber isn't installed, nothing matches, or the
    PDF can't be parsed as a table (e.g. no drawn cell borders).
    """
    if not table_extraction_available():
        return None
    norm_labels = {_norm_key(l) for l in labels}
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages[:max_pages]:
                try:
                    tables = page.extract_tables()
                except Exception:
                    continue
                for table in tables:
                    if len(table) < 2:
                        continue
                    header_row = table[0]
                    for col_idx, cell in enumerate(header_row):
                        if not cell:
                            continue
                        cell_norm = _norm_key(cell.replace("\n", " "))
                        if cell_norm not in norm_labels:
                            continue
                        # look for the value in this same column, in the
                        # first data row below the header that actually
                        # has something in that column
                        for row in table[1:]:
                            if col_idx < len(row) and row[col_idx]:
                                # cell text wraps mid-token in narrow
                                # columns (e.g. "402-30000088\n4"), so
                                # newlines are removed with no inserted
                                # space to reconstruct the original value
                                return row[col_idx].replace("\n", "").strip()
    except Exception:
        return None
    return None
