# Zoho Invoice → CreditDataWatch sync

Once set up, creating or updating an invoice in Zoho Invoice makes it
appear in CreditDataWatch automatically (as a Draft sales invoice) —
no manual export/import.

## How it works

1. Zoho Invoice calls a webhook on your Render backend whenever an
   invoice is created/updated.
2. The webhook only needs the invoice's ID; the backend then calls the
   Zoho Invoice API itself to fetch the full invoice, and upserts it
   into `sales_invoices` (matching by invoice number), the same way
   the existing "import scanned PDF" feature does.
3. New files: `app/services/zoho_service.py` (talks to the Zoho API)
   and `app/routes/integrations_zoho.py` (the webhook endpoint).

## 1. Create a Zoho API Console app

1. Go to https://api-console.zoho.com (log in with the Zoho account
   that has your invoices).
2. Click **Add Client** → **Self Client**. This is the right type for
   a single Zoho organization talking to your own server — no
   redirect/login flow needed.
3. Note the **Client ID** and **Client Secret** shown — you'll need
   both.

## 2. Generate a refresh token (one-time)

1. Still on the API Console, open your Self Client, go to the
   **Generate Code** tab.
2. Scope: enter
   `ZohoInvoice.invoices.READ,ZohoInvoice.settings.READ`
3. Duration: 10 minutes is enough. Click **Create**.
4. Copy the **grant token** shown — it's a one-time code, valid only
   for a few minutes.
5. Immediately exchange it for a refresh token. From your own computer
   (this only needs to be done once, ever):

   ```
   curl -X POST "https://accounts.zoho.com/oauth/v2/token" \
     -d "code=PASTE_GRANT_TOKEN_HERE" \
     -d "client_id=PASTE_CLIENT_ID_HERE" \
     -d "client_secret=PASTE_CLIENT_SECRET_HERE" \
     -d "redirect_uri=https://bindu-project-1.onrender.com" \
     -d "grant_type=authorization_code"
   ```

   (If you don't have `curl`, Postman or even a Python `requests.post`
   with the same params/URL works just as well.)

6. The response is JSON containing `"refresh_token": "1000...."`. Save
   that value — it does not expire (unless revoked), so this step is
   only done once.

If your Zoho account is not on the `.com` data center (e.g. you signed
up on zoho.in or zoho.eu), replace `accounts.zoho.com` above — and the
`ZOHO_ACCOUNTS_BASE_URL` / `ZOHO_API_BASE_URL` env vars below — with
your data center's domain.

## 3. Find your Zoho Organization ID

In Zoho Invoice, go to **Settings → Organization Profile**. The
Organization ID (a number) is shown there.

## 4. Set environment variables on Render

On the `Bindu-project` service in Render → Environment, add:

| Key | Value |
|---|---|
| `ZOHO_CLIENT_ID` | from step 1 |
| `ZOHO_CLIENT_SECRET` | from step 1 |
| `ZOHO_REFRESH_TOKEN` | from step 2 |
| `ZOHO_ORGANIZATION_ID` | from step 3 |
| `ZOHO_WEBHOOK_SECRET` | any random string you make up, e.g. a long password |
| `ZOHO_TARGET_USER_EMAIL` | the CreditDataWatch account email that these invoices should be filed under |

Leave `ZOHO_ACCOUNTS_BASE_URL` / `ZOHO_API_BASE_URL` unset unless
you're on a non-`.com` Zoho data center (see step 2 note).

## 5. Set up the webhook in Zoho Invoice

1. In Zoho Invoice, go to **Settings → Automation → Webhooks** (or
   **Workflow Rules → Webhooks**, depending on your Zoho edition).
2. Create a new webhook:
   - **Module**: Invoices
   - **Trigger**: On Create, and also add one On Update (so edits sync too)
   - **URL**:
     `https://bindu-project-1-XXXX.onrender.com/api/v1/integrations/zoho/webhook?secret=YOUR_ZOHO_WEBHOOK_SECRET`
     — replace with your actual backend URL (check what it is; it may
     be the same host as `Bindu-project`, not `-1`, since `-1` was
     described as the static frontend) and the secret from step 4.
   - **Body / Payload**: choose the option to send a custom/raw JSON
     body (not the default full payload), and set it to:
     ```
     {"invoice_id": "${invoice.invoice_id}"}
     ```
     This uses Zoho's own field-merge syntax to insert the invoice's
     ID. The exact wording of this option ("Raw", "User Defined
     Format") varies by Zoho edition — if you can't find it, sending
     the default full payload also works, since the backend looks for
     `invoice_id` inside it either way, but the fetched fields are
     more reliable with the custom body above.
3. Save, then create a test invoice in Zoho to confirm it appears in
   CreditDataWatch (check the Sales Invoices list, or the Render logs
   for `Bindu-project` for a line like `Zoho webhook: created new
   invoice ...`).

## Known unconfirmed field: customer GSTIN

Zoho's exact key for a customer's GSTIN on the invoice object varies
by account/edition and wasn't confirmed while writing this. The code
tries a few likely key names (`gst_no`, `tax_reg_no`, `gst_treatment`)
and falls back to leaving it blank if none match.

To find the right one: create a test invoice for a customer that has
a GSTIN on file in Zoho, then check the Render logs after the webhook
fires — or temporarily add `logger.info(zoho_invoice)` near the top of
`zoho_invoice_webhook` in `app/routes/integrations_zoho.py`, redeploy,
trigger the webhook once, and read the full JSON in the logs. Then
add the real key name to the `_first_present(...)` call for
`counterparty_gstin` in that file.

## Notes

- Only one CreditDataWatch account (`ZOHO_TARGET_USER_EMAIL`) receives
  synced invoices. If you need invoices split across multiple
  accounts by customer or by Zoho organization, this needs extending.
- An invoice already marked "Paid" in CreditDataWatch is left alone
  if Zoho sends another update for it, to avoid Zoho overwriting a
  reconciled record.
- Line items aren't synced (same limitation as the existing scanned-PDF
  import) — only totals, dates, and customer info.
