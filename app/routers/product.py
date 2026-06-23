from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from crud import (
    get_product, create_product, update_product, delete_product,
    move_product, reorder_products
)
from schemas import Product, ProductCreate, ProductUpdate
from database import get_db
from auth import get_optional_username
from audit_log import log_action

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get(
    "/{product_id}",
    response_model=Product,
    summary="Получить товар по ID",
    description="Возвращает данные одного товара по его идентификатору.",
)
def read_product(product_id: int, db: Session = Depends(get_db)):
    prod = get_product(db, product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    return prod


@router.post(
    "/",
    response_model=Product,
    status_code=status.HTTP_201_CREATED,
    summary="Создать товар",
    description="Создаёт новый товар в указанной категории (`Category_id` обязателен).",
)
def create_new_product(
    product: ProductCreate,
    actor: str = Depends(get_optional_username),
    db: Session = Depends(get_db),
):
    try:
        new_prod = create_product(db, product)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    log_action(
        db, actor, "create", "product", new_prod.id,
        f"Создан товар «{new_prod.name}» (категория id={new_prod.Category_id}, цена={new_prod.price})",
    )
    return new_prod


@router.put(
    "/{product_id}",
    response_model=Product,
    summary="Обновить товар",
    description=(
        "Частично обновляет поля товара. "
        "Изменение `price` фиксируется в журнале аудита отдельной записью с указанием старого и нового значения."
    ),
)
def update_existing_product(
    product_id: int,
    updates: ProductUpdate,
    actor: str = Depends(get_optional_username),
    db: Session = Depends(get_db),
):
    old = get_product(db, product_id)
    if not old:
        raise HTTPException(status_code=404, detail="Product not found")
    old_name = old.name
    old_price = old.price

    updated = update_product(db, product_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Product not found")

    changes: List[str] = []
    if updates.name is not None and updates.name != old_name:
        changes.append(f"название «{old_name}» → «{updates.name}»")
    if updates.price is not None and updates.price != old_price:
        changes.append(f"цена {old_price} → {updates.price}")
    if updates.Category_id is not None:
        changes.append(f"категория → id={updates.Category_id}")
    if updates.brand is not None:
        changes.append(f"бренд → «{updates.brand or '—'}»")
    if updates.description is not None:
        changes.append("описание изменено")
    if updates.packaging_unit_value is not None:
        changes.append(f"объём упаковки → {updates.packaging_unit_value}")
    if updates.sort_order is not None:
        changes.append(f"порядок сортировки → {updates.sort_order}")

    details = f"Товар «{updated.name}» (id={product_id}): " + (
        "; ".join(changes) if changes else "без изменений"
    )
    log_action(db, actor, "update", "product", product_id, details)

    return updated


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить товар",
    description="Удаляет товар. Удаление невозможно, если товар используется в строках хозяйственных операций.",
)
def delete_existing_product(
    product_id: int,
    actor: str = Depends(get_optional_username),
    db: Session = Depends(get_db),
):
    existing = get_product(db, product_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Product not found")
    name = existing.name
    price = existing.price

    try:
        delete_product(db, product_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    log_action(db, actor, "delete", "product", product_id,
               f"Удалён товар «{name}» (id={product_id}, цена={price})")


@router.put(
    "/{product_id}/move",
    response_model=Product,
    summary="Переместить товар в другую категорию",
    description="Переносит товар в указанную категорию `new_category_id`.",
)
def move_existing_product(
    product_id: int,
    new_category_id: int,
    actor: str = Depends(get_optional_username),
    db: Session = Depends(get_db),
):
    existing = get_product(db, product_id)
    name = existing.name if existing else f"id={product_id}"

    try:
        result = move_product(db, product_id, new_category_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    log_action(db, actor, "update", "product", product_id,
               f"Товар «{name}» перемещён в категорию id={new_category_id}")
    return result


@router.put(
    "/reorder/{category_id}",
    summary="Изменить порядок товаров в категории",
    description="Переупорядочивает товары внутри категории согласно переданному списку идентификаторов.",
)
def reorder_existing_products(
    category_id: int,
    ordered_ids: List[int],
    actor: str = Depends(get_optional_username),
    db: Session = Depends(get_db),
):
    try:
        reorder_products(db, category_id, ordered_ids)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    log_action(db, actor, "update", "product", category_id,
               f"Изменён порядок {len(ordered_ids)} товаров в категории id={category_id}")
    return {"status": "ok"}
