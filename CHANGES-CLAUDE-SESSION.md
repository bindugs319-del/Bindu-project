# Changes made in this session

This zip has **all** fixes from this conversation already applied to the source
files below. `server/venv` and `client/node_modules` were intentionally
excluded (too large, environment-specific) — use your existing ones, just
copy these source files over your project.

## Root problem
`Invoices.jsx` created records in the `sales_invoices` table (`SalesInvoice`
model — the rich GST tax-invoice form), but the Operations/Master Admin
approval workflow only existed on a separate, unused `invoices` table
(`Invoice` model). Nothing in the app ever created records there, so
submitted invoices had no working approval path. Fix: added the same
approval workflow to `SalesInvoice` instead (additive, nothing existing
was removed).

## Backend files changed
- **`server/app/models/__init__.py`**
  - Added `workflow_status`, `operations_reviewed_by/at/notes`,
    `master_approved_by/at/notes` to `SalesInvoice`.
  - Added `counterparty_email`, `counterparty_phone` to `SalesInvoice`.
- **`server/app/schemas/sales_invoice.py`**
  - Exposed the new workflow + contact fields on
    `SalesInvoiceCreate` / `Update` / `Response`.
  - Added `SalesInvoiceWorkflowAction` schema.
- **`server/app/routes/sales_invoices.py`**
  - Added `POST /{id}/submit`, `GET /workflow/pending-operations`,
    `POST /{id}/operations-verify`, `POST /{id}/operations-reject`,
    `GET /workflow/pending-master`, `POST /{id}/master-approve`,
    `POST /{id}/master-reject` — mirrors the old `Invoice` workflow
    exactly, including audit logs and notifications.
  - Added `POST /{id}/archive` (toggle archive, mirrors PO's archive
    endpoint) and `include_archived` query param on `GET /sales-invoices`.
  - **Important fix**: every workflow endpoint calls
    `await db.refresh(invoice)` right before building the response.
    Without this, `NotificationService.send()`'s internal `db.commit()`
    expires the SQLAlchemy object, and building the Pydantic response
    afterwards throws `MissingGreenlet` (async lazy-load in a sync
    context) — this caused the 500 errors even though the underlying
    DB update had already succeeded.

## New migrations (run `alembic upgrade head` after copying these in)
- **`b7c8d9e0f1a2_sales_invoice_workflow.py`** — adds the 7 workflow
  columns above.
- **`c9d0e1f2a3b4_sales_invoice_counterparty_phone.py`** — adds
  `counterparty_phone` (`counterparty_email` already existed as an
  unused column in the DB from an earlier migration).

## Frontend files changed
- **`client/src/services/api/apiClient.js`**
  - `salesInvoices` client gained: `submit`, `pendingOperations`,
    `operationsVerify`, `operationsReject`, `pendingMaster`,
    `masterApprove`, `masterReject`, `archive`, and `include_archived`
    support on `list`.
- **`client/src/pages/roles/RoleDashboard.jsx`**
  - Operations/Master Admin queues now call `salesInvoices` endpoints
    instead of the unused `invoices` ones, and render `total` /
    `payment_due_date` (the real `SalesInvoice` field names) instead of
    `amount` / `due_date`.
- **`client/src/pages/Invoices.jsx`** — brought to feature parity with
  the Purchase Orders page:
  - "Invoice Overview" stats card (Total / Paid / Pending), mirroring
    the PO page's Business Credibility Index card.
  - Status filter tabs (All/Draft/Sent/Paid/Overdue).
  - "Show Archived" toggle + Archive/Unarchive action button.
  - "Download CSV" export button.
  - New **Document**, **Email**, **Mobile** columns in the table.
  - New **Customer Email** / **Customer Mobile** fields in the
    create/edit form, and shown in the invoice detail view.
- **`client/src/pages/Dashboard.jsx`**
  - Added a "Recent Sales Invoices" widget for Company Admin / Master
    Admin, mirroring the existing "Recent Purchase Orders" widget.

## Still outstanding
- Your Alembic migration history has two branch heads that predate this
  session (`f7a8b9c0d1e2` and `f5g6h7i8j9k0`) — consider
  `alembic merge heads` at some point.
- `psycopg2-binary` needs to be in your venv for Alembic to run (not in
  `requirements.txt` originally — add it if you rebuild the venv).
