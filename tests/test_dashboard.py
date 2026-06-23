"""
Dashboard summary endpoint (/api/dashboard/stats).

This endpoint uses plain SQLAlchemy `func.count()` over ORM models, so
it runs correctly on SQLite and is covered here as a unit test.

/api/analytics uses Postgres-only SQL (DATE_TRUNC, ::numeric casts) and
is covered separately as an integration test (see test_analytics.py).
"""

from models import Category, Product, ParamDefinition, XOClass, XOInstance
import datetime


def test_dashboard_stats_shape_and_zero_state(client, admin_headers):
    r = client.get("/api/dashboard/stats", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"categories", "products", "params", "xo_instances"}
    # Fresh in-memory DB — nothing seeded yet
    assert body == {"categories": 0, "products": 0, "params": 0, "xo_instances": 0}


def test_dashboard_stats_requires_auth(client):
    r = client.get("/api/dashboard/stats")
    assert r.status_code == 403


def test_dashboard_stats_counts_rows(client, admin_headers, db_session):
    cat = Category(name="Тест", sort_order=0)
    db_session.add(cat)
    db_session.flush()

    db_session.add(Product(name="Товар 1", Category_id=cat.id, price=10, sort_order=0))
    db_session.add(Product(name="Товар 2", Category_id=cat.id, price=20, sort_order=1))
    db_session.add(ParamDefinition(name="Цвет", param_type="enum"))

    xo_class = XOClass(name="Тестовая операция", sort_order=0)
    db_session.add(xo_class)
    db_session.flush()
    db_session.add(XOInstance(xo_class_id=xo_class.id, op_date=datetime.date.today(), status="draft"))

    db_session.commit()

    r = client.get("/api/dashboard/stats", headers=admin_headers)
    body = r.json()
    assert body["categories"] == 1
    assert body["products"] == 2
    assert body["params"] == 1
    assert body["xo_instances"] == 1


def test_dashboard_stats_available_to_regular_user(client, user_headers):
    """Dashboard is informational and available to any authenticated user."""
    r = client.get("/api/dashboard/stats", headers=user_headers)
    assert r.status_code == 200
