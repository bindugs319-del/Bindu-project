# Zoho Invoice → CreditDataWatch sync

Once set up, an invoice created or edited in Zoho Invoice appears in
CreditDataWatch automatically (as a Draft sales invoice) — no manual
export/import.

## How it works (polling, not a webhook)

Zoho Invoice's **free plan doesn't include Automation/Webhooks**
(confirmed on Zoho's own plan comparison — Automation, including
webhooks, is a paid-plan-only feature). So instead of Zoho pushing to
us the instant something changes, CreditDataWatch's backend checks
Zoho every 15 minutes (configurable) for new or changed invoices and
pulls them in. This means there's a short delay (up to 15 minutes by
default) rather than instant sync — but it costs nothing and needs no
Zoho plan upgrade.

If you later upgrade to a paid Zoho plan, a webhook (instant sync) is
already built and ready — see "Optional: switch to instant sync"
below.

New files:
- `app/services/zoho_service.py` — talks to the Zoho API (auth + fetching invoices)
- `app/services/zoho_sync_service.py` — turns one Zoho invoice into a sales_invoices row
- `app/services/zoho_poll_service.py` — the periodic check (what's actually running)
- `app/routes/integrations_zoho.py` — the webhook endpoint (only used if you upgrade Zoho later)

## 1. Create a Zoho API Console app

1. Go to your data center's console — `https://api-console.zoho.in` for
   India accounts, `https://api-console.zoho.com` for `.com` accounts.
2. Click **Add Client** (or **Get Started**) → **Self Client**. This is
   the right type for a single Zoho organization talking to your own
   server — no redirect/login flow needed.
3. Note the **Client ID** and **Client Secret** shown (Client Secret
   tab) — you'll need both.

## 2. Generate a refresh token (one-time)

1. Still on your Self Client, open the **Generate Code** tab.
2. Scope: enter exactly
   `ZohoInvoice.invoices.READ,ZohoInvoice.settings.READ`
3. Duration: 10 minutes is enough. Fill in a Description (any text).
   Click **Create**.
4. Copy the **grant code** shown — it's one-time-use, valid only for
   the duration you picked. Act on the next step immediately.
5. Exchange it for a refresh token. In a terminal (PowerShell needs
   `curl.exe`, not `curl` — plain `curl` in PowerShell is actually a
   different command that doesn't support this the same way):

   ```
   curl.exe -X POST "https://accounts.zoho.in/oauth/v2/token" -d "code=PASTE_GRANT_CODE_HERE" -d "client_id=PASTE_CLIENT_ID_HERE" -d "client_secret=PASTE_CLIENT_SECRET_HERE" -d "redirect_uri=https://bindu-project-1.onrender.com" -d "grant_type=authorization_code"
   ```

   (Use `accounts.zoho.com` instead of `accounts.zoho.in` if you're on
   the `.com` data center. `redirect_uri` is just a placeholder value
   for a Self Client — any syntactically valid URL works.)

6. The response is JSON containing `"refresh_token": "1000...."`. Save
   that — it doesn't expire (unless revoked), so this step only
   happens once, ever.

## 3. Find your Zoho Organization ID

In Zoho Invoice, click the gear icon → **Settings** → **Organization
Profile**. The Organization ID is shown right at the top next to the
title.

## 4. Set environment variables on Render

On the `Bindu-project` service in Render → Environment, add:

| Key | Value |
|---|---|
| `ZOHO_CLIENT_ID` | from step 1 |
| `ZOHO_CLIENT_SECRET` | from step 1 |
| `ZOHO_REFRESH_TOKEN` | from step 2 |
| `ZOHO_ORGANIZATION_ID` | from step 3 |
| `ZOHO_ACCOUNTS_BASE_URL` | `https://accounts.zoho.in` (or `.com` for that data center) |
| `ZOHO_API_BASE_URL` | `https://www.zohoapis.in/invoice/v3` (or `.com`) |
| `ZOHO_TARGET_USER_EMAIL` | the CreditDataWatch account email that these invoices should be filed under |
| `ZOHO_WEBHOOK_SECRET` | only needed if you set up the optional webhook later — safe to fill in now anyway (any random string) |
| `ZOHO_POLL_INTERVAL_SECONDS` | optional — how often to check Zoho, in seconds. Defaults to 900 (15 min) if not set. |

Click **Save, rebuild, and deploy**. Once live, check the Logs tab for
a line like `Starting Zoho invoice poll runner (900s interval)` to
confirm it started.

## 5. Test it

1. In Zoho Invoice, create a test invoice for a customer.
2. Wait up to 15 minutes (or however long `ZOHO_POLL_INTERVAL_SECONDS`
   is set to).
3. Check CreditDataWatch's Sales Invoices list — the invoice should
   appear as a Draft.
4. Or check Render's Logs sooner, for a line like `Zoho poll: checked
   1 invoice(s), synced 1, 0 error(s)`.

The very first poll after setup also backfills your most recent 100
existing Zoho invoices (if any), not just new ones from that point on.

## Known unconfirmed field: customer GSTIN

Zoho's exact key for a customer's GSTIN on the invoice object varies
by account/edition and wasn't confirmed while writing this. The code
tries a few likely key names (`gst_no`, `tax_reg_no`, `gst_treatment`)
and leaves it blank if none match.

To find the right one: create a test invoice for a customer that has
a GSTIN on file in Zoho, wait for a poll cycle, then temporarily add
`logger.info(zoho_invoice)` near the top of `sync_one_invoice` in
`app/services/zoho_sync_service.py`, redeploy, wait for the next poll,
and read the full JSON in Render's logs. Add the real key name to the
`_first_present(...)` call for `counterparty_gstin` there.

## Optional: switch to instant sync (requires a paid Zoho plan)

If you later upgrade your Zoho Invoice plan to one that includes
Automation:

1. In Zoho Invoice, go to **Settings → Automation → Webhooks**.
2. Create a webhook: Module = Invoices, Trigger = On Create (and On
   Update), URL =
   `https://<your-backend>/api/v1/integrations/zoho/webhook?secret=YOUR_ZOHO_WEBHOOK_SECRET`,
   Body = custom JSON: `{"invoice_id": "${invoice.invoice_id}"}`.
3. That's it — no code changes needed. The webhook and the poller both
   call the same sync logic, so behavior is identical; you'd just get
   near-instant updates instead of waiting for the next poll. You can
   leave the poller running alongside it (harmless — it just won't
   find anything new most of the time) or increase
   `ZOHO_POLL_INTERVAL_SECONDS` to something long as a backup check.

## Notes

- Only one CreditDataWatch account (`ZOHO_TARGET_USER_EMAIL`) receives
  synced invoices. If you need invoices split across multiple
  accounts by customer or by Zoho organization, this needs extending.
- An invoice already marked "Paid" in CreditDataWatch is left alone
  if Zoho later sends another update for it, to avoid Zoho
  overwriting a reconciled record.
- Line items aren't synced (same limitation as the existing scanned-PDF
  import) — only totals, dates, and customer info.
- The poller only looks at the most recent 100 invoices per check. If
  you create more than 100 invoices within one poll interval, older
  ones in that batch could be missed until you increase `per_page` in
  `zoho_service.list_invoices` — very unlikely at normal volumes.
