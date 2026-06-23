from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from crud import (
    get_category, create_category, update_category, delete_category,
    move_category, reorder_categories, get_descendants, get_parents,
    get_terminal_products, check_cycles
)
from schemas import (
    Category, CategoryCreate, CategoryUpdate,
    DescendantInfo, ParentInfo, TerminalProduct, CycleCheckResult
)
from database import get_db
from auth import get_optional_username
from audit_log import log_action

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get(
    "/{category_id}",
    response_model=Category,
    summary="Получить категорию по ID",
    description="Возвращает данные одной категории каталога по её идентификатору.",
)
def read_category(category_id: int, db: Session = Depends(get_db)):
    cat = get_category(db, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return cat


@router.post(
    "/",
    response_model=Category,
    status_code=status.HTTP_201_CREATED,
    summary="Создать категорию",
    description=(
        "Создаёт новую категорию каталога. Если `Category_id` указан — "
        "новая категория становится подкатегорией указанной родительской категории, "
        "иначе создаётся корневая категория."
    ),
)
def create_new_category(
    category: CategoryCreate,
    actor: str = Depends(get_optional_username),
    db: Session = Depends(get_db),
):
    try:
        new_cat = create_category(db, category)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    if new_cat.Category_id:
        details = f"Создана категория «{new_cat.name}» (id={new_cat.id}), родитель id={new_cat.Category_id}"
    else:
        details = f"Создана корневая категория «{new_cat.name}» (id={new_cat.id})"

    log_action(db, actor, "create", "category", new_cat.id, details)
    return new_cat


@router.put(
    "/{category_id}",
    response_model=Category,
    summary="Обновить категорию",
    description="Частично обновляет поля категории: название, родителя, единицу упаковки, порядок сортировки.",
)
def update_existing_category(
    category_id: int,
    updates: CategoryUpdate,
    actor: str = Depends(get_optional_username),
    db: Session = Depends(get_db),
):
    old = get_category(db, category_id)
    if not old:
        raise HTTPException(status_code=404, detail="Category not found")
    old_name = old.name

    updated = update_category(db, category_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Category not found")

    changes: List[str] = []
    if updates.name is not None and updates.name != old_name:
        changes.append(f"название «{old_name}» → «{updates.name}»")
    if updates.Category_id is not None:
        changes.append(f"родитель → id={updates.Category_id}")
    if updates.packaging_unit_name is not None:
        changes.append(f"единица упаковки → «{updates.packaging_unit_name}»")
    if updates.sort_order is not None:
        changes.append(f"порядок сортировки → {updates.sort_order}")

    details = f"Категория «{updated.name}» (id={category_id}): " + (
        "; ".join(changes) if changes else "без изменений"
    )
    log_action(db, actor, "update", "category", category_id, details)
    return updated


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить категорию",
    description="Удаляет категорию. Удаление невозможно, если категория содержит подкатегории или товары.",
)
def delete_existing_category(
    category_id: int,
    actor: str = Depends(get_optional_username),
    db: Session = Depends(get_db),
):
    existing = get_category(db, category_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Category not found")
    name = existing.name

    try:
        delete_category(db, category_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    log_action(db, actor, "delete", "category", category_id, f"Удалена категория «{name}» (id={category_id})")


@router.put(
    "/{category_id}/move",
    response_model=Category,
    summary="Переместить категорию",
    description="Переносит категорию к новому родителю (или в корень, если `new_parent_id` не указан).",
)
def move_existing_category(
    category_id: int,
    new_parent_id: Optional[int] = None,
    actor: str = Depends(get_optional_username),
    db: Session = Depends(get_db),
):
    existing = get_category(db, category_id)
    name = existing.name if existing else f"id={category_id}"

    try:
        result = move_category(db, category_id, new_parent_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    destination = f"id={new_parent_id}" if new_parent_id else "корень"
    log_action(db, actor, "update", "category", category_id,
               f"Категория «{name}» перемещена → родитель {destination}")
    return result


@router.put(
    "/{parent_id}/reorder",
    summary="Изменить порядок категорий",
    description="Переупорядочивает категории внутри одного родителя согласно переданному списку идентификаторов.",
)
def reorder_existing_categories(
    parent_id: Optional[int],
    ordered_ids: List[int],
    actor: str = Depends(get_optional_username),
    db: Session = Depends(get_db),
):
    try:
        reorder_categories(db, parent_id, ordered_ids)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    log_action(db, actor, "update", "category", parent_id,
               f"Изменён порядок {len(ordered_ids)} категорий (родитель={'корень' if parent_id is None else parent_id})")
    return {"status": "ok"}


@router.get(
    "/{category_id}/descendants",
    response_model=List[DescendantInfo],
    summary="Все потомки категории",
    description="Возвращает плоский список всех подкатегорий и товаров, вложенных в указанную категорию (рекурсивно).",
)
def read_descendants(category_id: int, db: Session = Depends(get_db)):
    return get_descendants(db, category_id)


@router.get(
    "/{category_id}/parents",
    response_model=List[ParentInfo],
    summary="Путь до корня",
    description="Возвращает цепочку родительских категорий от корня до указанной категории (включительно).",
)
def read_parents(category_id: int, db: Session = Depends(get_db)):
    return get_parents(db, category_id)


@router.get(
    "/{category_id}/terminal-products",
    response_model=List[TerminalProduct],
    summary="Товары категории",
    description="Возвращает товары, находящиеся непосредственно в указанной категории (без подкатегорий).",
)
def read_terminal_products(category_id: int, db: Session = Depends(get_db)):
    return get_terminal_products(db, category_id)


@router.get(
    "/diagnostic/cycles",
    response_model=CycleCheckResult,
    summary="Диагностика циклов в дереве категорий",
    description="Проверяет дерево категорий на наличие циклических ссылок (некорректных данных).",
)
def read_cycle_check(db: Session = Depends(get_db)):
    return check_cycles(db)


@router.get(
    "/tree/full",
    response_model=dict,
    summary="Полное дерево категорий и товаров",
    description="Возвращает всё дерево категорий с вложенными товарами. Если указан `root_id`, дерево строится от этой категории.",
)
def read_full_tree(root_id: Optional[int] = None, db: Session = Depends(get_db)):
    from crud import get_full_tree
    return get_full_tree(db, root_id)


@router.get(
    "/{category_id}/tree",
    response_model=dict,
    summary="Поддерево категории",
    description="Возвращает поддерево каталога, начиная с указанной категории.",
)
def read_category_tree(category_id: int, db: Session = Depends(get_db)):
    from crud import get_full_tree
    tree = get_full_tree(db, category_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Category not found")
    return tree
