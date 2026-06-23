"""
/api/analytics (integration).

This endpoint uses Postgres-only SQL (DATE_TRUNC, ::numeric, TO_CHAR),
so it cannot run against the SQLite unit-test database and requires a
real PostgreSQL instance with init.sql applied.
"""

import pytest

from conftest import requires_postgres


pytestmark = [pytest.mark.integration, requires_postgres]


def test_analytics_shape(pg_client, pg_admin_headers):
    r = pg_client.get("/api/analytics", headers=pg_admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert set(body.keys()) == {
        "category_distribution", "category_avg_price", "param_usage", "xo_monthly",
    }
    assert isinstance(body["category_distribution"], list)
    assert isinstance(body["category_avg_price"], list)
    assert isinstance(body["param_usage"], list)
    assert isinstance(body["xo_monthly"], list)


def test_analytics_category_distribution_has_seeded_categories(pg_client, pg_admin_headers):
    r = pg_client.get("/api/analytics", headers=pg_admin_headers)
    dist = r.json()["category_distribution"]

    assert len(dist) > 0
    for row in dist:
        assert "category_name" in row
        assert "product_count" in row
        assert row["product_count"] > 0


def test_analytics_avg_price_is_numeric(pg_client, pg_admin_headers):
    r = pg_client.get("/api/analytics", headers=pg_admin_headers)
    avg_price = r.json()["category_avg_price"]

    assert len(avg_price) > 0
    for row in avg_price:
        assert isinstance(row["avg_price"], (int, float))
        assert row["avg_price"] > 0


def test_analytics_requires_auth(pg_client):
    r = pg_client.get("/api/analytics")
    assert r.status_code == 403


def test_analytics_available_to_regular_user(pg_client, pg_client_user_headers):
    r = pg_client.get("/api/analytics", headers=pg_client_user_headers)
    assert r.status_code == 200
