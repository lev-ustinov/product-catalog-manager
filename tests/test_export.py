"""
CSV export endpoints (integration).

Verifies the UTF-8 BOM fix (Excel + Cyrillic) and correct headers/content.
Requires a real PostgreSQL database with init.sql applied.
"""

import csv
import io

import pytest

from conftest import requires_postgres


pytestmark = [pytest.mark.integration, requires_postgres]

BOM = "\ufeff"


def test_export_products_all_has_bom_and_cyrillic_headers(pg_client, pg_admin_headers):
    r = pg_client.get("/api/export/products", headers=pg_admin_headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]

    text = r.content.decode("utf-8")
    assert text.startswith(BOM), "CSV must start with a UTF-8 BOM for Excel/Cyrillic compatibility"

    reader = csv.reader(io.StringIO(text.lstrip(BOM)))
    header = next(reader)
    assert header == ["ID", "Название", "Категория", "Цена", "Бренд",
                       "Описание", "Ед. упаковки", "Порядок сортировки"]

    rows = list(reader)
    assert len(rows) >= 9  # init.sql seeds 9 products


def test_export_products_filtered_by_category(pg_client, pg_admin_headers):
    # Category 4 = 'Огурцы' (subtree of 'Семена' -> 'Овощи' -> 'Огурцы')
    r = pg_client.get("/api/export/products", params={"category_id": 4}, headers=pg_admin_headers)
    assert r.status_code == 200

    text = r.content.decode("utf-8").lstrip(BOM)
    reader = csv.reader(io.StringIO(text))
    next(reader)  # header
    rows = list(reader)
    assert len(rows) >= 1
    assert all(row[2] == "Огурцы" for row in rows)


def test_export_xo_instances_has_bom_and_headers(pg_client, pg_admin_headers):
    r = pg_client.get("/api/export/xo-instances", headers=pg_admin_headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")

    text = r.content.decode("utf-8")
    assert text.startswith(BOM)

    reader = csv.reader(io.StringIO(text.lstrip(BOM)))
    header = next(reader)
    assert header == ["ID", "Номер", "Класс ХО", "Дата операции",
                       "Статус", "Примечания", "Создал", "Создан"]

    rows = list(reader)
    assert len(rows) >= 1  # init.sql seeds at least one xo_instance


def test_export_requires_auth(pg_client):
    r = pg_client.get("/api/export/products")
    assert r.status_code == 403
