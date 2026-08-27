# CreditDataWatch backend — FastAPI + Postgres + OCR (tesseract/poppler)
#
# Real entrypoint is app.main:app (see server/app/main.py). The top-level
# server/main.py is a stale duplicate that can't even run standalone (it
# uses a relative import — `from .database import ...` — which only
# resolves when the file is loaded as the `app.main` package member, not
# as a bare script). Do not point CMD at it.

FROM python:3.11-slim AS base

# --- System dependencies -----------------------------------------------
# tesseract-ocr + poppler-utils: required for OCR (pytesseract / pdf2image)
#   on scanned/photographed PO and invoice uploads.
# libpq-dev + gcc: needed to build psycopg2-binary / asyncpg on some
#   base images (kept even though most wheels are prebuilt, for safety).
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Python dependencies -------------------------------------------------
# Dependencies are version-pinned in requirements.txt (verified to resolve
# and install cleanly together — see the file for how those pins were
# derived). --only-binary :all: additionally refuses to fall back to
# building any package from a source distribution, which would otherwise
# let that package's setup.py execute arbitrary code during install —
# confirmed every pinned dependency here actually has a prebuilt wheel
# for this image, so this doesn't risk breaking the build.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --only-binary :all: -r requirements.txt

# --- Application code ------------------------------------------------------
# COPY . . pulls in the whole build context recursively — .dockerignore
# (in this same directory) is what keeps secrets/dev artifacts (.env,
# credentials/, venv/, *.dump, uploads/*) out of the resulting image.
# Update .dockerignore, not this line, if a new kind of sensitive file
# needs excluding.
COPY . .

# Uploads directory (evidence files, PO/invoice documents) — created here so
# it exists even before the app's own os.makedirs() call runs, and so it's
# writable by the non-root user below.
RUN mkdir -p /app/uploads

# Run as a non-root user (good practice; Render also expects this on some plans)
RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

# Render sets $PORT at runtime; default to 8000 for local `docker run`.
ENV PORT=8000
EXPOSE 8000

# Real entrypoint: app.main:app (NOT main:app — see note at top of file).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
