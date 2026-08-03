# RentFlow — Simple Rent Management System

A lightweight, modern rent management web app for landlords and property owners.

Built with **Python (FastAPI) + HTML + CSS + Vanilla JavaScript + Supabase (PostgreSQL)**.

**No Node.js. No npm. No frontend framework.** Only Python and pip.

## Features

Authentication with Supabase (login, signup, logout, password change). Dashboard with total,
occupied and vacant properties, expected monthly rent, pending rent, a six-month collection
trend chart and an outstanding-rent list. Full CRUD for properties and tenants, monthly rent
records with "mark paid", payment history and one-click generation of pending records for all
active tenants. Downloadable PDF rent-collection reports (till today, last 6 months, last 12
months or last 2 years) with billing summary and full transaction history. Global search across
tenants and properties, plus dark/light/system themes, glassmorphism cards, CSS-only animations,
loading spinners, empty states and a mobile-friendly responsive layout.

## Requirements

Python 3.10 or newer on Windows, a free Supabase account, and any modern browser.
Check your Python version with `python --version`.

## Installation

```bat
cd rent-management-system
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Then open `.env` and paste your Supabase credentials.

## Supabase Setup

1. Create a project at https://supabase.com (free tier is enough).
2. Go to **Project Settings → API** and copy the **Project URL** and the **anon public** key
   into `.env` as `SUPABASE_URL` and `SUPABASE_ANON_KEY`. Never use the `service_role` key here.
3. Open **SQL Editor → New query**, paste the whole contents of `database/schema.sql` and click
   **Run**. This creates the tables, indexes, triggers and Row Level Security policies.
4. For local development go to **Authentication → Providers → Email** and turn **Confirm email**
   off, so you can sign in immediately after creating an account.
5. Optional: after you have created your first account, run `database/seed.sql` in the SQL Editor
   to load demo properties, tenants and payments.

## Environment Variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `SUPABASE_URL` | Yes | — | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | — | The anon public API key |
| `APP_NAME` | No | `RentFlow` | Name shown in the UI |
| `HOST` | No | `127.0.0.1` | Bind address |
| `PORT` | No | `8000` | Port number |
| `DEBUG` | No | `true` | Auto-reload, verbose errors, and enables `/api/docs` |
| `COOKIE_SECURE` | No | `false` | Set `true` only when serving over HTTPS |
| `ALLOW_SIGNUP` | No | `true` | Show the "Create account" tab |

## How to Run

```bat
.venv\Scripts\activate
python run.py
```

Open http://127.0.0.1:8000 in your browser, create an account on the login screen, then sign in.
Press `Ctrl + C` in the terminal to stop the server. The interactive API docs are at
http://127.0.0.1:8000/api/docs while `DEBUG=true`.

## Folder Structure

```
rent-management-system/
├── app/                 Backend (FastAPI)
│   ├── main.py          App factory, routing, global error handlers
│   ├── config.py        Environment configuration
│   ├── supabase_client.py  Per-request Supabase client factory
│   ├── dependencies.py  Cookie session handling and auth guards
│   ├── schemas.py       Pydantic request validation models
│   ├── crud.py          Reusable data-access helpers
│   ├── errors.py        Custom exceptions and error message cleanup
│   ├── templating.py    Shared Jinja2 environment
│   ├── reports.py       PDF rent-collection report generator (ReportLab)
│   └── routers/         pages, auth, dashboard, properties, tenants,
│                        payments, search, settings
├── database/            schema.sql (tables + RLS) and seed.sql (demo data)
├── templates/           Jinja2 HTML pages and partials
├── static/              css/ and js/ assets plus the favicon
├── requirements.txt     Python dependencies
├── run.py               Start the server
└── .env                 Your local secrets (never commit this)
```

## Database Design

`profiles` holds one row per user and is created automatically by a trigger on signup.
`properties` and `tenants` both belong to a user through `owner_id`, and a tenant links to a
property through `property_id`. `payments` stores one row per tenant per rent month, enforced by
a unique constraint on `(tenant_id, period_month)`, and links back to both the tenant and the
property. Every table has Row Level Security enabled with policies matching `auth.uid()`, so a
user can only ever read or write their own data even if the API key is exposed.

## Rent Collection Reports

The **Rent & Payments** page has a "Generate report" button that downloads a professional PDF
summary of rent collection, generated server-side with ReportLab. Choose a period — till today,
last 6 months, last 12 months, or last 2 years — and the report includes:

- A summary of total billed, total collected, pending balance and collection rate
- A full transaction table (tenant, property, month, due, paid, balance, status, paid-on date)

`reportlab` is listed in `requirements.txt` and installs automatically with
`pip install -r requirements.txt`. No extra setup is required.

## Troubleshooting

**"Supabase is not configured"** — `.env` is missing or empty. Copy `.env.example` to `.env`,
fill in both Supabase values and restart `python run.py`.

**"Database tables are missing"** — run `database/schema.sql` in the Supabase SQL Editor.

**"Invalid email or password"** — the account does not exist yet, or email confirmation is still
required. Create the account first, or disable **Confirm email** in Supabase.

**Login succeeds but every page bounces back to /login** — your browser is blocking cookies for
`127.0.0.1`, or `COOKIE_SECURE=true` while running over plain HTTP. Set `COOKIE_SECURE=false`.

**`'python' is not recognized`** — Python is not on your PATH. Reinstall Python and tick
*Add Python to PATH*, or use `py -3` instead of `python`.

**`ERROR: [Errno 10048] address already in use`** — another program is using port 8000. Change
`PORT` in `.env` to `8080` and restart.

**Code changes don't seem to take effect / a route "Method Not Allowed" even after editing the
file** — a leftover Python process from a previous run may still be holding port 8000, so your
browser or `curl` requests are hitting the old code instead of the new one. Check what's on the
port and kill it, then restart cleanly:

```bat
netstat -ano | findstr :8000
taskkill /F /IM python.exe
python run.py
```

**Empty dashboard after adding data** — data is scoped per user. Make sure you are signed in with
the same account that created the records, and hard-refresh with `Ctrl + F5`.

**Deleting a property is refused** — a property with an active tenant cannot be deleted. Reassign
or deactivate the tenant first.

**`/api/docs` or `/api/openapi.json` returns "Not Found"** — these are only enabled when
`DEBUG=true` in `.env`. Set it, save, and restart `python run.py`.

## Notes

Only the Supabase **anon** key is used, and all access is protected by Row Level Security, so no
privileged key ever reaches the browser. Session tokens are stored in HttpOnly cookies rather
than `localStorage`. For production use, serve behind HTTPS and set `COOKIE_SECURE=true` and
`DEBUG=false`.

## License

MIT — free to use and modify."# rent" 
