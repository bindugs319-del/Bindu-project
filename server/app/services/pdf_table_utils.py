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
from typing import Optional

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from app.services.po_pdf_scan_service import _norm_key


def table_extraction_available() -> bool:
    return pdfplumber is not None


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
