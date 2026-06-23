"""
Audit log endpoint: admin-only access, pagination, and filtering by
entity_type / action.
"""

from datetime import datetime, timedelta, timezone

from models import AuditLog


def _seed_entries(db_session, n=5, **overrides):
    """Insert n synthetic audit rows for filter/pagination tests."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC, matches DateTime columns
    for i in range(n):
        defaults = dict(
            timestamp=now - timedelta(minutes=i),
            user_login="seed",
            action="update",
            entity_type="product",
            entity_id=100 + i,
            details=f"Seed entry #{i}",
        )
        defaults.update(overrides)
        db_session.add(AuditLog(**defaults))
    db_session.commit()


def test_audit_requires_admin(client, user_headers):
    r = client.get("/api/audit/", headers=user_headers)
    assert r.status_code == 403


def test_audit_requires_auth(client):
    r = client.get("/api/audit/")
    assert r.status_code == 403


def test_audit_empty_initially(client, admin_headers):
    r = client.get("/api/audit/", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_audit_pagination(client, admin_headers, db_session):
    _seed_entries(db_session, n=5)

    r = client.get("/api/audit/?limit=2&offset=0", headers=admin_headers)
    assert r.status_code == 200
    page1 = r.json()
    assert len(page1) == 2

    r = client.get("/api/audit/?limit=2&offset=2", headers=admin_headers)
    page2 = r.json()
    assert len(page2) == 2

    # Pages don't overlap and are ordered newest-first
    ids1 = {e["entity_id"] for e in page1}
    ids2 = {e["entity_id"] for e in page2}
    assert ids1.isdisjoint(ids2)
    assert page1[0]["timestamp"] >= page1[1]["timestamp"] >= page2[0]["timestamp"]


def test_audit_filter_by_entity_type(client, admin_headers, db_session):
    _seed_entries(db_session, n=2, entity_type="product")
    _seed_entries(db_session, n=3, entity_type="category", entity_id=200)

    r = client.get("/api/audit/?entity_type=category", headers=admin_headers)
    assert r.status_code == 200
    entries = r.json()
    assert len(entries) == 3
    assert all(e["entity_type"] == "category" for e in entries)


def test_audit_filter_by_action(client, admin_headers, db_session):
    _seed_entries(db_session, n=2, action="update")
    _seed_entries(db_session, n=1, action="delete", entity_id=300)

    r = client.get("/api/audit/?action=delete", headers=admin_headers)
    assert r.status_code == 200
    entries = r.json()
    assert len(entries) == 1
    assert entries[0]["action"] == "delete"
    assert entries[0]["entity_id"] == 300


def test_audit_combined_filters(client, admin_headers, db_session):
    _seed_entries(db_session, n=1, entity_type="xo_instance", action="post", entity_id=401)
    _seed_entries(db_session, n=1, entity_type="xo_instance", action="cancel", entity_id=402)
    _seed_entries(db_session, n=1, entity_type="product", action="post", entity_id=403)

    r = client.get("/api/audit/?entity_type=xo_instance&action=post", headers=admin_headers)
    entries = r.json()
    assert len(entries) == 1
    assert entries[0]["entity_id"] == 401
