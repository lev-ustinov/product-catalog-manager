"""
Shared pytest fixtures.

Two test tiers:

* **Unit tests** (the default) run against an in-memory SQLite database
  created fresh for every test function. They cover everything that is
  pure SQLAlchemy ORM / Python logic: auth, JWT, password hashing,
  user management, audit log, role-based access, and the
  `/api/dashboard/stats` endpoint.

* **Integration tests** (marked with `@pytest.mark.integration`) need a
  real PostgreSQL database with the `init.sql` schema applied, because
  `crud.py` relies on PL/pgSQL functions (add_category, create_xo_instance,
  ...) and `/api/analytics` uses Postgres-only SQL (DATE_TRUNC, ::numeric).

  Set TEST_DATABASE_URL to a Postgres connection string that already has
  init.sql loaded (e.g. the docker-compose `db` service) to run them:

      docker-compose up -d db
      psql ... -f init.sql                 # if not already applied
      export TEST_DATABASE_URL=postgresql://appuser:securepassword@localhost:5432/product_catalog
      pytest -m integration

  Without TEST_DATABASE_URL, integration tests are skipped automatically.
"""

import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

APP_DIR = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP_DIR))

# Environment defaults used by auth.py / database.py at import time.
os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-production")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "480")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import database  # noqa: E402
import models  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Unit-test fixtures (SQLite, in-memory, fresh per test)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def db_engine():
    """Fresh in-memory SQLite database, shared across connections via StaticPool."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    database.engine = engine
    database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(db_engine):
    """FastAPI TestClient wired to the per-test SQLite database."""
    import main  # local import: picks up database.SessionLocal set above
    from fastapi.testclient import TestClient

    with TestClient(main.app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def db_session(db_engine):
    """Direct DB session for arranging test fixtures / assertions."""
    Session = sessionmaker(bind=db_engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def admin_headers(client):
    """Authorization header for the env-fallback admin account."""
    r = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def user_headers(client, admin_headers):
    """
    Creates a non-admin 'user'-role account via the admin API, logs in as
    that user, and returns its Authorization header.
    """
    r = client.post(
        "/api/users/",
        json={"username": "regular_user", "password": "userpass1", "role": "user"},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text

    r = client.post("/auth/login", json={"username": "regular_user", "password": "userpass1"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# Integration-test fixtures (real PostgreSQL with init.sql applied)
# ─────────────────────────────────────────────────────────────────────────────

PG_URL = os.environ.get("TEST_DATABASE_URL")


def _pg_available() -> bool:
    if not PG_URL:
        return False
    try:
        eng = create_engine(PG_URL)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        eng.dispose()
        return True
    except Exception:
        return False


requires_postgres = pytest.mark.skipif(
    not _pg_available(),
    reason="TEST_DATABASE_URL not set or Postgres unreachable — set it to a DB with init.sql applied",
)


@pytest.fixture()
def pg_client():
    """FastAPI TestClient backed by the real Postgres test database."""
    engine = create_engine(PG_URL, pool_pre_ping=True)
    database.engine = engine
    database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    import main
    from fastapi.testclient import TestClient

    with TestClient(main.app, raise_server_exceptions=False) as c:
        yield c

    engine.dispose()


@pytest.fixture()
def pg_admin_headers(pg_client):
    r = pg_client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def pg_client_user_headers(pg_client, pg_admin_headers):
    """A non-admin 'user'-role account in the Postgres test database."""
    import uuid
    username = f"qa_user_{uuid.uuid4().hex[:8]}"
    r = pg_client.post(
        "/api/users/",
        json={"username": username, "password": "userpass1", "role": "user"},
        headers=pg_admin_headers,
    )
    assert r.status_code == 201, r.text

    r = pg_client.post("/auth/login", json={"username": username, "password": "userpass1"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
