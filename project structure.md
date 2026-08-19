# Credit Data Watch — Project Structure

Full directory tree (excludes `node_modules/`, `venv/`, `__pycache__/`, `.git/`, `dist/`, `build/`).

```
Credit-data-watch/
├── .gitignore
├── README.md
├── docs/                          # architecture & progress write-ups (not code)
├── client/                        # React + Vite frontend
│   ├── .eslintrc.cjs
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── public/                    # static assets
│   ├── docs/                      # api-contract.md, requirements.md
│   └── src/
│       ├── App.jsx
│       ├── main.jsx
│       ├── index.css
│       ├── routes/
│       │   └── index.jsx          # central route table
│       ├── pages/                 # one file per screen
│       │   ├── Home.jsx, Dashboard.jsx, Wallet.jsx, ...
│       │   ├── account/
│       │   ├── admin/
│       │   ├── auth/
│       │   ├── roles/
│       │   ├── services/
│       │   └── solutions/
│       ├── components/            # reusable + feature-grouped UI
│       │   ├── NotificationBell.jsx, RoleRoute.jsx, ...
│       │   ├── account/
│       │   ├── common/
│       │   ├── dashboard/
│       │   ├── home/
│       │   ├── layout/
│       │   ├── membership/
│       │   ├── po/                # purchase-order feature components
│       │   └── ui/
│       ├── services/
│       │   ├── api/                       # apiClient.js — the only fetch layer
│       │   ├── authService.js
│       │   └── subscriptionService.js
│       ├── state/
│       │   ├── authContext.jsx
│       │   └── demoSession.js
│       ├── hooks/
│       │   └── useConfetti.js
│       └── utils/
│           ├── validation.js, date.js, phone.js, accessControl.js, activityLogger.js, monthlySeries.js
│
├── server/                        # FastAPI backend
│   ├── .env / .envexample
│   ├── .flake8
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── main.py                    # uvicorn entry point
│   ├── app/
│   │   ├── main.py                # FastAPI app + router registration
│   │   ├── config.py               # settings
│   │   ├── database.py             # async SQLAlchemy engine/session
│   │   ├── dependencies.py          # get_current_user, etc.
│   │   ├── exceptions.py             # AppException + subclasses
│   │   ├── redis_client.py
│   │   ├── middleware/
│   │   │   ├── error_handler.py
│   │   │   ├── rate_limit.py
│   │   │   └── request_id.py
│   │   ├── models/                    # SQLAlchemy ORM models
│   │   │   ├── __init__.py            # (bulk of models live here)
│   │   │   ├── credibility_index.py
│   │   │   └── notification.py
│   │   ├── schemas/                   # Pydantic request/response schemas
│   │   │   ├── auth.py, wallet.py, subscription.py, sales_invoice.py, ...
│   │   ├── routes/                    # one file per resource, thin
│   │   │   ├── auth.py, wallet.py, payments.py, subscriptions.py
│   │   │   ├── admin.py, core.py       # large, catch-all — avoid growing further
│   │   │   ├── business_check.py, business_profile.py
│   │   │   ├── credibility.py, credibility_index.py, inv_credibility.py
│   │   │   ├── invoices.py, sales_invoices.py
│   │   │   ├── invitations.py, appointments.py, workflow.py
│   │   │   ├── activity.py, chat.py, contact.py, drive.py, legal.py, ratings.py, user_settings.py
│   │   ├── services/                  # business logic, one class per domain
│   │   │   ├── auth_service.py, wallet_service.py, payment_service.py
│   │   │   ├── subscription_service.py, credibility_service.py
│   │   │   ├── notification_service.py, email_service.py, sms_service.py, otp_service.py
│   │   │   ├── drive_service.py, import_service.py, pdf_service.py, sales_invoice_pdf.py
│   │   │   ├── access_control_service.py, ai_cbi_service.py, business_profile_service.py
│   │   │   ├── legal_notice_service.py, rating_service.py, user_service.py, user_settings_service.py
│   │   │   └── workflow_service.py
│   │   ├── utils/                     # small stateless helpers
│   │   │   ├── response.py            # ResponseFormatter
│   │   │   ├── gstin.py, phone.py, password.py, jwt_helper.py, time.py, audit.py, role_settings.py, uploads.py
│   │   └── scripts/                   # one-off / maintenance scripts (in-app)
│   ├── migrations/                    # Alembic
│   │   ├── env.py
│   │   └── versions/                  # ~30+ migration files
│   ├── scripts/                       # standalone ops scripts (outside app/)
│   │   ├── delete_test_users*.py, list_users.py, list_tables.py, migrate_sqlite_to_postgres.py, ...
│   ├── seed_cms.py, seed_plans.py, run_production.py, setup.py
│   └── uploads/                       # user-uploaded files at runtime
│       ├── drive_fallback/, evidence/, payment_proofs/, payment_receipts/
│       ├── purchase_orders/, reports/, sales_invoice_evidence/, sales_invoices/, temp/
│
├── pytest.ini, pyrightconfig.json, sonar-project.properties
└── *.md                            # top-level status/summary docs (CHANGES-SUMMARY, PROJECT_SUMMARY, etc.)
```

## Quick orientation

| Area | Where |
|---|---|
| Add a new API endpoint | `server/app/routes/<resource>.py` (call a `Service`, return via `ResponseFormatter`) |
| Add business logic | `server/app/services/<domain>_service.py` |
| Add/change a DB table | `server/app/models/`, then generate an Alembic migration in `server/migrations/versions/` |
| Add a new frontend page | `client/src/pages/`, wire it up in `client/src/routes/index.jsx` |
| Add a reusable UI piece | `client/src/components/` (feature subfolder if it's specific to one area, e.g. `po/`, `admin/`) |
| Add a new API call from frontend | `client/src/services/api/apiClient.js` (low-level) + a domain service file if one exists |
| Shared validation logic | `client/src/utils/validation.js` (frontend) / `server/app/utils/` (backend) |

*Excludes generated/vendor directories (`node_modules`, Python `venv`, `__pycache__`) and runtime upload files' individual filenames beyond the folder they live in.*