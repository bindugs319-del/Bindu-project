"""
OCR fallback for scanned/photographed Purchase Orders and Invoices — used
when a PDF has no real text layer, or when the upload is a photo (JPG/PNG)
rather than a PDF at all.

Important limitation, by design: OCR text is noisy. Labels can be
misread (e.g. "GSTIN" -> "STN"), and stray marks near numbers (like a
currency symbol the font/camera renders oddly) can get read as digits.
The label-matching logic in po_pdf_scan_service.py stays strict about
what counts as a valid GSTIN/email/money value specifically so that
OCR noise produces a MISSING field (safe — the preview screen just shows
it blank for the user to fill in) rather than a WRONG field silently
saved. This module only extracts text; it doesn't lower those standards.

Requires the system binaries `tesseract-ocr` and `poppler-utils` to be
installed (this is the case in this dev environment, but is NOT installed
by default on a plain Render Python web service — see the deployment
note this was flagged with).
"""
import io
from typing import Optional

try:
    import pytesseract
    from PIL import Image
except ImportError:
    pytesseract = None
    Image = None

try:
    from pdf2image import convert_from_bytes
except ImportError:
    convert_from_bytes = None

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp")


def ocr_available() -> bool:
    return pytesseract is not None and Image is not None


def ocr_image_bytes(image_bytes: bytes) -> str:
    """OCRs a single image (JPG/PNG/etc). Returns '' on failure."""
    if not ocr_available():
        return ""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(img) or ""
    except Exception:
        return ""


def ocr_pdf_bytes(pdf_bytes: bytes, max_pages: int = 3) -> str:
    """
    Renders the first `max_pages` pages of a (scanned/no-text-layer) PDF to
    images and OCRs each one. Requires poppler-utils (pdftoppm) on the
    system PATH via pdf2image. Returns '' on failure (e.g. poppler missing).
    """
    if not ocr_available() or convert_from_bytes is None:
        return ""
    try:
        images = convert_from_bytes(pdf_bytes, first_page=1, last_page=max_pages)
    except Exception:
        return ""
    text_parts = []
    for img in images:
        try:
            text_parts.append(pytesseract.image_to_string(img) or "")
        except Exception:
            continue
    return "\n".join(text_parts)


def get_document_text(file_bytes: bytes, filename: str, existing_text: Optional[str] = None) -> dict:
    """
    Central entry point used by both scan services. Returns:
        {"text": str, "source": "pdf_text" | "ocr_pdf" | "ocr_image" | "none",
         "ocr_unavailable": bool}

    - If `existing_text` (already-extracted PDF text) is long enough, uses it
      as-is — no OCR needed, fastest and most accurate path.
    - If the filename is an image, OCRs it directly.
    - Otherwise (a PDF with too little/no text layer), OCRs the rendered
      pages.
    """
    is_image = filename.lower().endswith(IMAGE_EXTENSIONS)

    if not is_image and existing_text and len(existing_text.strip()) >= 20:
        return {"text": existing_text, "source": "pdf_text", "ocr_unavailable": False}

    if not ocr_available():
        return {"text": existing_text or "", "source": "none", "ocr_unavailable": True}

    if is_image:
        text = ocr_image_bytes(file_bytes)
        return {"text": text, "source": "ocr_image", "ocr_unavailable": False}

    text = ocr_pdf_bytes(file_bytes)
    if not text.strip() and convert_from_bytes is None:
        return {"text": existing_text or "", "source": "none", "ocr_unavailable": True}
    return {"text": text, "source": "ocr_pdf", "ocr_unavailable": False}
