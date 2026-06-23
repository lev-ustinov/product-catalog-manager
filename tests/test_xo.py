"""
XO (business-operation) instance lifecycle (integration).

Uses a freshly-created XO class with no required roles, so `post_xo`
succeeds without needing role assignments — keeping the test
self-contained and independent of the seeded operational classes
(Отгрузка / Поступление / ...), which DO have required roles.

Run with:
    docker-compose up -d db
    export TEST_DATABASE_URL=postgresql://appuser:securepassword@localhost:5432/product_catalog
    pytest -m integration
"""

import pytest

from conftest import requires_postgres


pytestmark = [pytest.mark.integration, requires_postgres]


@pytest.fixture()
def qa_xo_class(pg_client, pg_admin_headers):
    """
    A throwaway top-level XO class with no required roles.

    Not deleted on teardown: several tests post/cancel instances under
    it, and xo_instance.xo_class_id is ON DELETE RESTRICT, so the class
    can't be removed while those (intentionally immutable) rows exist.
    A handful of "QA Тестовая операция" classes accumulating in a
    long-lived dev database is harmless; CI uses a throwaway container.
    """
    r = pg_client.post(
        "/api/xo/classes",
        json={"name": "QA Тестовая операция", "description": "Создан тестом", "sort_order": 999},
        headers=pg_admin_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_xo_create_writes_audit(pg_client, pg_admin_headers, qa_xo_class):
    r = pg_client.post(
        "/api/xo/instances",
        json={"xo_class_id": qa_xo_class, "number": "QA-001", "op_date": "2026-06-01"},
        headers=pg_admin_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "draft"
    xo_id = body["id"]

    r = pg_client.get("/api/audit/?entity_type=xo_instance&action=create", headers=pg_admin_headers)
    entry = next(e for e in r.json() if e["entity_id"] == xo_id)
    assert "QA-001" in entry["details"]

    # cleanup: draft instances can be deleted directly
    pg_client.delete(f"/api/xo/instances/{xo_id}", headers=pg_admin_headers)


def test_xo_update_writes_audit(pg_client, pg_admin_headers, qa_xo_class):
    r = pg_client.post(
        "/api/xo/instances",
        json={"xo_class_id": qa_xo_class, "number": "QA-002", "op_date": "2026-06-02"},
        headers=pg_admin_headers,
    )
    xo_id = r.json()["id"]

    r = pg_client.patch(
        f"/api/xo/instances/{xo_id}",
        json={"notes": "Обновлено тестом"},
        headers=pg_admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["notes"] == "Обновлено тестом"

    r = pg_client.get("/api/audit/?entity_type=xo_instance&action=update", headers=pg_admin_headers)
    entry = next(e for e in r.json() if e["entity_id"] == xo_id)
    assert "примечания" in entry["details"]

    pg_client.delete(f"/api/xo/instances/{xo_id}", headers=pg_admin_headers)


def test_xo_post_without_required_roles_succeeds(pg_client, pg_admin_headers, qa_xo_class):
    """The QA class has zero role_defs, so posting needs no role assignments."""
    r = pg_client.post(
        "/api/xo/instances",
        json={"xo_class_id": qa_xo_class, "number": "QA-003", "op_date": "2026-06-03"},
        headers=pg_admin_headers,
    )
    xo_id = r.json()["id"]

    r = pg_client.post(f"/api/xo/instances/{xo_id}/post", headers=pg_admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "posted"

    r = pg_client.get("/api/audit/?entity_type=xo_instance&action=post", headers=pg_admin_headers)
    entry = next(e for e in r.json() if e["entity_id"] == xo_id)
    assert "QA-003" in entry["details"]

    # Posted instances cannot be deleted (only draft) — cancel instead so
    # the qa_xo_class fixture teardown can remove the class cleanly.
    pg_client.post(f"/api/xo/instances/{xo_id}/cancel", headers=pg_admin_headers)


def test_xo_cancel_with_reason_writes_audit(pg_client, pg_admin_headers, qa_xo_class):
    r = pg_client.post(
        "/api/xo/instances",
        json={"xo_class_id": qa_xo_class, "number": "QA-004", "op_date": "2026-06-04"},
        headers=pg_admin_headers,
    )
    xo_id = r.json()["id"]

    r = pg_client.post(
        f"/api/xo/instances/{xo_id}/cancel",
        params={"reason": "Тестовая отмена"},
        headers=pg_admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"

    r = pg_client.get("/api/audit/?entity_type=xo_instance&action=cancel", headers=pg_admin_headers)
    entry = next(e for e in r.json() if e["entity_id"] == xo_id)
    assert "Тестовая отмена" in entry["details"]


def test_xo_post_requires_draft_status(pg_client, pg_admin_headers, qa_xo_class):
    r = pg_client.post(
        "/api/xo/instances",
        json={"xo_class_id": qa_xo_class, "number": "QA-005", "op_date": "2026-06-05"},
        headers=pg_admin_headers,
    )
    xo_id = r.json()["id"]
    pg_client.post(f"/api/xo/instances/{xo_id}/post", headers=pg_admin_headers)

    # Posting an already-posted instance must fail
    r = pg_client.post(f"/api/xo/instances/{xo_id}/post", headers=pg_admin_headers)
    assert r.status_code == 400

    pg_client.post(f"/api/xo/instances/{xo_id}/cancel", headers=pg_admin_headers)


def test_xo_delete_only_allows_draft(pg_client, pg_admin_headers, qa_xo_class):
    r = pg_client.post(
        "/api/xo/instances",
        json={"xo_class_id": qa_xo_class, "number": "QA-006", "op_date": "2026-06-06"},
        headers=pg_admin_headers,
    )
    xo_id = r.json()["id"]
    pg_client.post(f"/api/xo/instances/{xo_id}/post", headers=pg_admin_headers)

    # Cannot delete a posted instance
    r = pg_client.delete(f"/api/xo/instances/{xo_id}", headers=pg_admin_headers)
    assert r.status_code == 400

    pg_client.post(f"/api/xo/instances/{xo_id}/cancel", headers=pg_admin_headers)


def test_xo_full_lifecycle_audit_trail(pg_client, pg_admin_headers, qa_xo_class):
    """End-to-end: create -> update -> post -> cancel, all logged."""
    r = pg_client.post(
        "/api/xo/instances",
        json={"xo_class_id": qa_xo_class, "number": "QA-007", "op_date": "2026-06-07"},
        headers=pg_admin_headers,
    )
    xo_id = r.json()["id"]

    pg_client.patch(f"/api/xo/instances/{xo_id}", json={"notes": "draft note"}, headers=pg_admin_headers)
    pg_client.post(f"/api/xo/instances/{xo_id}/post", headers=pg_admin_headers)
    pg_client.post(f"/api/xo/instances/{xo_id}/cancel", headers=pg_admin_headers)

    r = pg_client.get("/api/audit/?entity_type=xo_instance", headers=pg_admin_headers)
    actions_for_xo = {e["action"] for e in r.json() if e["entity_id"] == xo_id}
    assert actions_for_xo == {"create", "update", "post", "cancel"}
