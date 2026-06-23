"""
CSV export endpoints.
"""

import csv
import io
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional

from database import get_db
from auth import verify_token

router = APIRouter(prefix="/api/export", tags=["export"])


def _csv_response(rows: list, headers: list, filename: str) -> StreamingResponse:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    content = output.getvalue()
    content_with_bom = '\ufeff' + content
    return StreamingResponse(
        iter([content_with_bom.encode('utf-8')]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/products",
    summary="Экспорт товаров в CSV",
    description=(
        "Возвращает CSV-файл со списком товаров. "
        "Если передан `category_id` — только товары этой категории и её подкатегорий. "
        "Без фильтра — все товары."
    ),
)
def export_products(
    category_id: Optional[int] = None,
    _role: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    if category_id:
        sql = text("""
            WITH RECURSIVE cat_tree AS (
                SELECT id FROM category WHERE id = :cat_id
                UNION ALL
                SELECT c.id FROM category c JOIN cat_tree ct ON c."Category_id" = ct.id
            )
            SELECT p.id, p.name, c.name AS category,
                   p.price, p.brand, p.description,
                   p.packaging_unit_value, p.sort_order
            FROM product p
            JOIN category c ON c.id = p."Category_id"
            WHERE p."Category_id" IN (SELECT id FROM cat_tree)
            ORDER BY c.name, p.name
        """)
        rows = db.execute(sql, {"cat_id": category_id}).fetchall()
        filename = f"products_cat{category_id}.csv"
    else:
        sql = text("""
            SELECT p.id, p.name, c.name AS category,
                   p.price, p.brand, p.description,
                   p.packaging_unit_value, p.sort_order
            FROM product p
            JOIN category c ON c.id = p."Category_id"
            ORDER BY c.name, p.name
        """)
        rows = db.execute(sql).fetchall()
        filename = "products_all.csv"

    headers = ["ID", "Название", "Категория", "Цена", "Бренд",
               "Описание", "Ед. упаковки", "Порядок сортировки"]
    data = [
        [r.id, r.name, r.category, r.price, r.brand or "",
         r.description or "", r.packaging_unit_value or "", r.sort_order]
        for r in rows
    ]
    return _csv_response(data, headers, filename)


@router.get(
    "/xo-instances",
    summary="Экспорт экземпляров ХО в CSV",
    description="Возвращает CSV-файл со списком всех экземпляров хозяйственных операций.",
)
def export_xo_instances(
    _role: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    rows = db.execute(text("""
        SELECT xi.id, xi.number, xc.name AS xo_class,
               xi.op_date, xi.status, xi.notes, xi.created_by, xi.created_at
        FROM xo_instance xi
        JOIN xo_class xc ON xc.id = xi.xo_class_id
        ORDER BY xi.op_date DESC, xi.id DESC
    """)).fetchall()

    headers = ["ID", "Номер", "Класс ХО", "Дата операции",
               "Статус", "Примечания", "Создал", "Создан"]
    data = [
        [r.id, r.number or "", r.xo_class, r.op_date,
         r.status, r.notes or "", r.created_by or "", r.created_at]
        for r in rows
    ]
    return _csv_response(data, headers, "xo_instances.csv")
