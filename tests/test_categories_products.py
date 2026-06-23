"""
Category & product CRUD (integration).

These endpoints call PL/pgSQL functions defined in init.sql
(add_category, update_category, delete_category, add_product, ...),
so they require a real PostgreSQL database with the schema applied.

Run with:
    docker-compose up -d db
    export TEST_DATABASE_URL=postgresql://appuser:securepassword@localhost:5432/product_catalog
    pytest -m integration
"""

import pytest

from conftest import requires_postgres


pytestmark = [pytest.mark.integration, requires_postgres]


# ── Categories ──────────────────────────────────────────────────────────────

def test_create_update_delete_category(pg_client, pg_admin_headers):
    # Create a fresh root category
    r = pg_client.post(
        "/api/categories/",
        json={"name": "QA Тестовая категория", "sort_order": 999},
        headers=pg_admin_headers,
    )
    assert r.status_code == 201, r.text
    cat = r.json()
    cat_id = cat["id"]
    assert cat["name"] == "QA Тестовая категория"
    assert cat["Category_id"] is None

    # Update its name
    r = pg_client.put(
        f"/api/categories/{cat_id}",
        json={"name": "QA Категория (переименована)"},
        headers=pg_admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "QA Категория (переименована)"

    # Audit: create + update entries exist for this category
    r = pg_client.get(f"/api/audit/?entity_type=category", headers=pg_admin_headers)
    entries = [e for e in r.json() if e["entity_id"] == cat_id]
    actions = {e["action"] for e in entries}
    assert "create" in actions
    assert "update" in actions
    update_entry = next(e for e in entries if e["action"] == "update")
    assert "переименована" in update_entry["details"]

    # Delete (leaf category with no children/products → allowed)
    r = pg_client.delete(f"/api/categories/{cat_id}", headers=pg_admin_headers)
    assert r.status_code == 204

    r = pg_client.get(f"/api/audit/?entity_type=category&action=delete", headers=pg_admin_headers)
    assert any(e["entity_id"] == cat_id for e in r.json())


def test_delete_category_with_children_fails(pg_client, pg_admin_headers):
    # category id=1 ('Товар') has subcategories in the seeded data
    r = pg_client.delete("/api/categories/1", headers=pg_admin_headers)
    assert r.status_code == 400


def test_category_move_prevents_cycle(pg_client, pg_admin_headers):
    # Create parent -> child, then try to move parent under its own child
    r = pg_client.post("/api/categories/", json={"name": "QA Родитель"}, headers=pg_admin_headers)
    parent_id = r.json()["id"]

    r = pg_client.post(
        "/api/categories/",
        json={"name": "QA Ребёнок", "Category_id": parent_id},
        headers=pg_admin_headers,
    )
    child_id = r.json()["id"]

    # Moving the parent under its own child must fail (would create a cycle)
    r = pg_client.put(
        f"/api/categories/{parent_id}/move",
        params={"new_parent_id": child_id},
        headers=pg_admin_headers,
    )
    assert r.status_code == 400

    # cleanup
    pg_client.delete(f"/api/categories/{child_id}", headers=pg_admin_headers)
    pg_client.delete(f"/api/categories/{parent_id}", headers=pg_admin_headers)


# ── Products ────────────────────────────────────────────────────────────────

def test_create_update_delete_product_with_price_audit(pg_client, pg_admin_headers):
    # Create a throwaway category to host the product
    r = pg_client.post("/api/categories/", json={"name": "QA Товары категория"}, headers=pg_admin_headers)
    cat_id = r.json()["id"]

    # Create product
    r = pg_client.post(
        "/api/products/",
        json={"name": "QA Тестовый товар", "price": "100.00", "Category_id": cat_id, "brand": "QABrand"},
        headers=pg_admin_headers,
    )
    assert r.status_code == 201, r.text
    prod = r.json()
    prod_id = prod["id"]
    assert prod["price"] == "100.00" or float(prod["price"]) == 100.0

    # Update price
    r = pg_client.put(
        f"/api/products/{prod_id}",
        json={"price": "149.99"},
        headers=pg_admin_headers,
    )
    assert r.status_code == 200
    assert float(r.json()["price"]) == 149.99

    # Audit entry must mention the price change explicitly
    r = pg_client.get("/api/audit/?entity_type=product&action=update", headers=pg_admin_headers)
    entry = next(e for e in r.json() if e["entity_id"] == prod_id)
    assert "100.00" in entry["details"] and "149.99" in entry["details"]

    # Delete product, then category
    r = pg_client.delete(f"/api/products/{prod_id}", headers=pg_admin_headers)
    assert r.status_code == 204

    r = pg_client.get("/api/audit/?entity_type=product&action=delete", headers=pg_admin_headers)
    assert any(e["entity_id"] == prod_id for e in r.json())

    pg_client.delete(f"/api/categories/{cat_id}", headers=pg_admin_headers)


def test_create_product_requires_existing_category(pg_client, pg_admin_headers):
    r = pg_client.post(
        "/api/products/",
        json={"name": "Сирота", "price": "10.00", "Category_id": 99999},
        headers=pg_admin_headers,
    )
    assert r.status_code in (400, 404, 422)
