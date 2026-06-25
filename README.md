# Product Classification Management System

A production-ready REST API and single-page frontend for managing a
hierarchical product catalog with configurable parameters, business
operations (XO), analytics, audit trail, and multi-role access control.

---

## Features

| Area | Details |
|------|---------|
| **Catalog** | Multi-level category tree, drag-and-drop reordering, rich product cards |
| **Parameters** | Numeric and enum-type attributes with min/max constraints; category inheritance |
| **Search** | Multi-filter parameter search across full category subtrees |
| **Business Operations** | Hierarchical XO classifier; draft → posted / cancelled lifecycle |
| **Dashboard** | Summary counters (categories, products, params, XO instances) |
| **Analytics** | Product distribution, avg-price, parameter usage, XO monthly trends — rendered with Chart.js |
| **Auth** | JWT login (username + password), RBAC with admin / user roles |
| **Audit** | Immutable change log for every create / update / delete / post / cancel |
| **Users** | Admin panel: create users, change role/password, activate/deactivate |
| **Export** | One-click CSV export with UTF-8 BOM (opens in Excel without encoding issues) |

---

## Architecture

```
Browser (SPA)  ──JWT──►  FastAPI  ──SQLAlchemy──►  PostgreSQL
    │                        │                          │
index.html              main.py + routers          init.sql  (schema, PL/pgSQL, seed)
vanilla JS              auth / catalog / xo        alembic/  (app_user, audit_log)
Chart.js                export / audit / users     seed_demo_data.py  (demo data)
```

![Architecture diagram](docs/architecture.svg)

### Key design decisions

**Two-layer schema management** — `init.sql` owns the business schema
(categories, products, parameters, XO, PL/pgSQL stored functions for
cycle detection, role validation, etc.) and is applied once, automatically,
by the official `postgres` Docker image on first container start. Alembic
owns only the two tables that were added later (`app_user` and
`audit_log`) and is applied via `alembic upgrade head`. This avoids
rewriting PL/pgSQL as Alembic DDL while still getting migration tracking.

**`entrypoint.sh` orchestrates container startup** — inside the `app`
Docker image, `alembic upgrade head` and `seed_demo_data.py` run
automatically before `uvicorn` starts. Both steps are idempotent, so
restarting the container never duplicates data.

**`create_all` safety net** — `main.py` also calls
`Base.metadata.create_all` at startup, so the server starts cleanly
even in environments where Alembic wasn't run (e.g. a quick local test).

**`audit_log.py` — isolated helper** — `log_action()` commits its own
mini-transaction. A failure in the audit write (table missing, network
blip) logs a warning and returns — it never rolls back the caller's
already-committed business operation.

**JWT with env fallback** — `_authenticate_user()` checks `app_user`
first; if the table doesn't exist yet it falls through to
`ADMIN_USERNAME` / `ADMIN_PASSWORD` from `.env`, so a fresh deployment
can be accessed before any migration is run.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.11+ |
| API Framework | FastAPI 0.115 |
| ORM | SQLAlchemy 2.0 |
| Database | PostgreSQL 15 |
| Migrations | Alembic 1.14 |
| Auth | python-jose (JWT · HS256) + bcrypt 4.x (direct, no passlib) |
| Frontend | Vanilla JS SPA — single `index.html`, Chart.js 4.4 |
| Container | Docker + docker-compose |

> The frontend is served as a static file by FastAPI (`GET /ui`) —
> no build step, no Node.js.

---

## Quick Start — Docker (recommended)

```bash
git clone https://github.com/lev-ustinov /product-catalog-manager.git
cd product-catalog-manager
cp .env.example .env
docker-compose up --build
```

That's it — one command. On first run, the `app` container automatically:

1. waits for PostgreSQL to become healthy,
2. runs `alembic upgrade head` (creates `app_user` / `audit_log`),
3. runs `seed_demo_data.py` (creates demo users + sample XO instances + audit history),
4. starts `uvicorn`.

All three steps are skipped on subsequent restarts if the data already exists.

- **SPA:** http://localhost:8000/ui
- **Swagger:** http://localhost:8000/docs
- **Login:** `admin` / `admin123` (full demo set below)

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | admin |
| `manager` | `manager123` | user |
| `analyst` | `analyst123` | user |

> `docker-compose.yml` reads `DB_PASSWORD` from `.env` to set the
> PostgreSQL password (defaults to `securepassword` if unset). This is
> separate from `DATABASE_URL`, which the app container ignores in favor
> of an internal connection string pointing at the `db` service.

---

## Manual Setup (without Docker, for local development)

Use this path if you want to run `uvicorn --reload` directly against
your own Python environment.

### 1 · Clone

```bash
git clone https://github.com/lev-ustinov /product-catalog-manager.git
cd product-catalog-manager
```

### 2 · Configure environment

```bash
cp .env.example .env
# Edit .env — at minimum change SECRET_KEY
```

### 3 · Start PostgreSQL

**Option A — Postgres in Docker, app run locally (hybrid, convenient):**
```bash
docker-compose up -d db
```
This automatically applies `init.sql` on first start — **do not** run it
again manually (re-running it against an already-initialized database
will fail with "relation already exists" errors).

**Option B — Postgres installed locally:**
```sql
CREATE USER appuser WITH PASSWORD 'yourpassword';
CREATE DATABASE product_catalog OWNER appuser;
GRANT ALL PRIVILEGES ON DATABASE product_catalog TO appuser;
GRANT ALL ON SCHEMA public TO appuser;
```
Then apply the schema yourself:
```bash
psql -h localhost -U appuser -d product_catalog -f init.sql
```

### 4 · Apply Alembic migrations

```bash
# from the project root — works from any directory
alembic upgrade head
```

### 5 · Install dependencies and run

```bash
pip install -r requirements.txt
cd app
uvicorn main:app --reload
```

- **SPA:** http://localhost:8000/ui
- **Swagger:** http://localhost:8000/docs
- **Default admin:** `admin` / `admin123` (from `.env`)

### 6 · Seed demo data (optional)

Creates demo user accounts (`manager`, `analyst`), 13 sample XO instances
spread across the last 6 months (so the Analytics chart isn't empty/flat),
and 19 realistic audit-log entries:

```bash
cd app
python seed_demo_data.py
```

Safe to re-run — it checks for existing data first and skips anything
already seeded.

---

## Running Tests

Install test dependencies:

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### Unit tests (SQLite, no Postgres needed)

```bash
pytest -v -m "not integration"
```

Covers: JWT auth, RBAC, user management CRUD, password changes,
account deactivation, audit-log filtering and pagination, dashboard
stats, and validation edge cases. **34 tests**, run in ~10 s.

### Integration tests (requires Postgres + init.sql)

```bash
docker-compose up -d db
alembic upgrade head

export TEST_DATABASE_URL=postgresql://appuser:securepassword@localhost:5432/product_catalog
pytest -v -m integration
```

Covers: category CRUD (cycle detection, FK protection), product CRUD
(price change audit), full XO lifecycle (create → update → post →
cancel), CSV export encoding (UTF-8 BOM), analytics endpoint. **21 tests**.

### Full suite

```bash
pytest -v   # unit + integration (integration skipped if TEST_DATABASE_URL not set)
```

CI runs the full suite automatically on every push via
`.github/workflows/tests.yml`.

---

## Production Deployment (systemd)

```ini
# /etc/systemd/system/product-catalog.service
[Unit]
Description=Product Catalog Manager
After=network.target postgresql.service

[Service]
WorkingDirectory=/opt/product-catalog/app
EnvironmentFile=/opt/product-catalog/.env
ExecStart=/opt/product-catalog/.venv/bin/uvicorn main:app \
          --host 0.0.0.0 --port 8000 --workers 2
Restart=on-failure
User=www-data

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now product-catalog
```

> `ExecStart` only starts `uvicorn` — unlike the Docker image, it does
> **not** run `entrypoint.sh`. Apply `alembic upgrade head` (and
> optionally `seed_demo_data.py`) manually once before the first start.

---

## API Documentation

Interactive Swagger UI: **`/docs`** — ReDoc: **`/redoc`**

| Endpoint | Description |
|----------|-------------|
| `POST /auth/login` | Obtain JWT token |
| `GET /auth/me` | Current user info |
| `GET /api/dashboard/stats` | Dashboard counters |
| `GET /api/analytics` | Aggregated chart data |
| `GET /api/categories/tree/full` | Full category tree |
| `GET /api/products/{product_id}` | Product detail |
| `GET /api/params/search` | Parameter-based product search |
| `GET /api/xo/instances` | XO instance list |
| `GET /api/export/products` | CSV export (products) |
| `GET /api/export/xo-instances` | CSV export (XO instances) |
| `GET /api/audit/` | Audit log — admin only |
| `GET /api/users/` | User list — admin only |

A `GET /health` endpoint also exists for container healthchecks. It's
intentionally excluded from the Swagger schema and from request logs.

---

## Screenshots

![Каталог](docs/screenshots/01_catalog.png)
![Dashboard](docs/screenshots/02_dashboard.png)
![Аналитика](docs/screenshots/03_analytics.png)
![Хоз операции](docs/screenshots/04_xo.png)
![Аудит](docs/screenshots/05_audit.png)
![Swagger](docs/screenshots/06_swagger.png)

---

## License

MIT
