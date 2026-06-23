"""
Роутер для управления системой настраиваемых параметров ().

Покрывает:
- CRUD определений параметров (param_definition)
- Назначение/снятие параметров с категорий (category_param)
- Установку/удаление значений параметров изделий
- Поиск изделий по параметрам (одиночный и многофильтровый)
- Агрегаты числовых параметров
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from decimal import Decimal
from sqlalchemy import text

from database import get_db
from crud import (
    get_all_param_definitions, get_param_definition,
    create_param_definition, update_param_definition, delete_param_definition,
    assign_param_to_category, remove_param_from_category,
    get_category_params, get_direct_category_params, update_category_param,
    get_product_params, set_product_param_numeric, set_product_param_enum,
    delete_product_param, get_param_aggregates,
    search_products_by_param, search_products_multi_filter,
)
from schemas import (
    ParamDefinitionCreate, ParamDefinitionUpdate, ParamDefinitionResponse,
    CategoryParamCreate, CategoryParamUpdate, CategoryParamResponse, InheritedParamResponse,
    ProductParamNumericSet, ProductParamEnumSet, ProductParamResponse,
    ParamAggregateResponse, ProductSearchFilter, ProductSearchRequest, ProductSearchResult,
)

router = APIRouter(prefix="/api/params", tags=["parameters"])


# =============================================
# ОПРЕДЕЛЕНИЯ ПАРАМЕТРОВ (param_definition)
# =============================================

@router.get("/definitions", response_model=List[ParamDefinitionResponse],
            summary="Список всех определений параметров")
def list_param_definitions(db: Session = Depends(get_db)):
    """Возвращает справочник всех определений параметров."""
    rows = get_all_param_definitions(db)
    return [
        ParamDefinitionResponse(
            id=r.id, name=r.name, description=r.description,
            param_type=r.param_type, unit=r.unit,
            min_value=r.min_value, max_value=r.max_value,
            enum_class_id=r.enum_class_id, enum_class_name=r.enum_class_name,
            is_required=r.is_required,
        ) for r in rows
    ]


@router.get("/definitions/{param_id}", response_model=ParamDefinitionResponse,
            summary="Получить определение параметра по ID")
def get_param_def(param_id: int, db: Session = Depends(get_db)):
    pd = get_param_definition(db, param_id)
    if not pd:
        raise HTTPException(status_code=404, detail="Параметр не найден")
    return ParamDefinitionResponse(
        id=pd.id, name=pd.name, description=pd.description,
        param_type=pd.param_type, unit=pd.unit,
        min_value=pd.min_value, max_value=pd.max_value,
        enum_class_id=pd.enum_class_id,
        enum_class_name=pd.enum_class.name if pd.enum_class else None,
        is_required=pd.is_required,
    )


@router.post("/definitions", response_model=ParamDefinitionResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Создать новое определение параметра")
def create_param_def(param: ParamDefinitionCreate, db: Session = Depends(get_db)):
    """
    Создаёт новый параметр (шаблон).

    - **param_type**: `numeric` — числовой, `enum` — перечисление
    - Для `numeric` можно задать `unit`, `min_value`, `max_value`
    - Для `enum` обязателен `enum_class_id`
    """
    try:
        pd = create_param_definition(db, param)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ParamDefinitionResponse(
        id=pd.id, name=pd.name, description=pd.description,
        param_type=pd.param_type, unit=pd.unit,
        min_value=pd.min_value, max_value=pd.max_value,
        enum_class_id=pd.enum_class_id,
        enum_class_name=pd.enum_class.name if pd.enum_class else None,
        is_required=pd.is_required,
    )


@router.patch("/definitions/{param_id}", response_model=ParamDefinitionResponse,
              summary="Обновить определение параметра")
def update_param_def(param_id: int, updates: ParamDefinitionUpdate, db: Session = Depends(get_db)):
    try:
        pd = update_param_definition(db, param_id, updates)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not pd:
        raise HTTPException(status_code=404, detail="Параметр не найден")
    return ParamDefinitionResponse(
        id=pd.id, name=pd.name, description=pd.description,
        param_type=pd.param_type, unit=pd.unit,
        min_value=pd.min_value, max_value=pd.max_value,
        enum_class_id=pd.enum_class_id,
        enum_class_name=pd.enum_class.name if pd.enum_class else None,
        is_required=pd.is_required,
    )


@router.delete("/definitions/{param_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Удалить определение параметра")
def delete_param_def(param_id: int, db: Session = Depends(get_db)):
    """Удаляет параметр и все его значения у изделий (каскадно)."""
    if not get_param_definition(db, param_id):
        raise HTTPException(status_code=404, detail="Параметр не найден")
    try:
        delete_param_definition(db, param_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================
# ПАРАМЕТРЫ КАТЕГОРИЙ (СХЕМА)
# =============================================

@router.get("/categories/{category_id}",
            response_model=List[InheritedParamResponse],
            summary="Параметры категории (с унаследованными от предков)")
def read_category_params(category_id: int, db: Session = Depends(get_db)):
    """
    Возвращает полный набор параметров для категории:
    - собственные (назначенные напрямую)
    - унаследованные от предков (где `is_inherited=True`)

    Поле `is_inherited` в ответе указывает, унаследован ли параметр.
    """
    rows = get_category_params(db, category_id)
    return [
        InheritedParamResponse(
            param_id=r.param_id, param_name=r.param_name,
            description=r.description, param_type=r.param_type,
            unit=r.unit, min_value=r.min_value, max_value=r.max_value,
            enum_class_id=r.enum_class_id, enum_class_name=r.enum_class_name,
            is_required=r.is_required,
            is_inherited=r.is_inherited,
            source_category_id=r.source_category_id,
            source_category_name=r.source_category_name,
            sort_order=r.sort_order,
        ) for r in rows
    ]


@router.get("/categories/{category_id}/direct",
            summary="Непосредственно назначенные параметры категории")
def read_direct_category_params(category_id: int, db: Session = Depends(get_db)):
    """Только собственные параметры категории (без наследования)."""
    rows = get_direct_category_params(db, category_id)
    return [
        {
            "param_id": r.param_id, "param_name": r.param_name,
            "param_type": r.param_type, "unit": r.unit,
            "min_value": r.min_value, "max_value": r.max_value,
            "enum_class_id": r.enum_class_id, "is_required": r.is_required,
            "is_inherited": r.is_inherited, "sort_order": r.sort_order,
        } for r in rows
    ]


@router.post("/categories/{category_id}",
             status_code=status.HTTP_201_CREATED,
             summary="Назначить параметр категории")
def assign_param(category_id: int, cp: CategoryParamCreate, db: Session = Depends(get_db)):
    """
    Назначает параметр категории.

    - **is_inherited**: если `true`, параметр наследуется подкатегориями
    """
    try:
        assign_param_to_category(db, category_id, cp)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "category_id": category_id, "param_id": cp.param_id}


@router.patch("/categories/{category_id}/{param_id}",
              summary="Обновить настройки параметра для категории")
def update_cat_param(category_id: int, param_id: int,
                     updates: CategoryParamUpdate, db: Session = Depends(get_db)):
    result = update_category_param(db, category_id, param_id,
                                   updates.is_inherited, updates.sort_order)
    if not result:
        raise HTTPException(status_code=404, detail="Связь параметр-категория не найдена")
    return {"status": "ok"}


@router.delete("/categories/{category_id}/{param_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               summary="Снять параметр с категории")
def remove_param(category_id: int, param_id: int, db: Session = Depends(get_db)):
    try:
        remove_param_from_category(db, category_id, param_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================
# ЗНАЧЕНИЯ ПАРАМЕТРОВ ИЗДЕЛИЙ
# =============================================

@router.get("/products/{product_id}",
            response_model=List[ProductParamResponse],
            summary="Параметры и значения конкретного изделия")
def read_product_params(product_id: int, db: Session = Depends(get_db)):
    """
    Возвращает все параметры, применимые к изделию (на основе его категории + наследование),
    вместе с установленными значениями.
    """
    rows = get_product_params(db, product_id)
    return [
        ProductParamResponse(
            param_id=r.param_id, param_name=r.param_name,
            param_type=r.param_type, unit=r.unit,
            min_value=r.min_value, max_value=r.max_value,
            numeric_value=r.numeric_value,
            enum_value_id=r.enum_value_id, enum_value_text=r.enum_value_text,
            is_required=r.is_required,
        ) for r in rows
    ]


@router.put("/products/{product_id}/numeric",
            summary="Установить числовое значение параметра изделия")
def set_numeric_param(product_id: int, data: ProductParamNumericSet,
                      db: Session = Depends(get_db)):
    """
    Устанавливает (или обновляет) числовое значение параметра.
    Значение проверяется на соответствие ограничениям min/max.
    """
    try:
        set_product_param_numeric(db, product_id, data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "product_id": product_id, "param_id": data.param_id}


@router.put("/products/{product_id}/enum",
            summary="Установить enum-значение параметра изделия")
def set_enum_param(product_id: int, data: ProductParamEnumSet, db: Session = Depends(get_db)):
    """
    Устанавливает (или обновляет) значение параметра-перечисления.
    Проверяет принадлежность значения нужному классу.
    """
    try:
        set_product_param_enum(db, product_id, data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "product_id": product_id, "param_id": data.param_id}


@router.delete("/products/{product_id}/{param_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               summary="Удалить значение параметра изделия")
def del_product_param(product_id: int, param_id: int, db: Session = Depends(get_db)):
    try:
        delete_product_param(db, product_id, param_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================
# ПОИСК И АГРЕГАТЫ
# =============================================

@router.get("/search",
            response_model=List[ProductSearchResult],
            summary="Поиск изделий по значению одного параметра")
def search_by_single_param(
    category_id: int,
    param_id: int,
    num_min: Optional[Decimal] = None,
    num_max: Optional[Decimal] = None,
    enum_value_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Ищет изделия в категории и всех её подкатегориях по значению параметра.

    Примеры:
    - Числовой: `?category_id=1&param_id=5&num_min=50&num_max=200`
    - Перечисление: `?category_id=1&param_id=13&enum_value_id=4`
    """
    rows = search_products_by_param(db, category_id, param_id, num_min, num_max, enum_value_id)
    return [
        ProductSearchResult(
            product_id=r.product_id, product_name=r.product_name,
            category_id=r.category_id, category_name=r.category_name,
            price=r.price, brand=r.brand,
        ) for r in rows
    ]


@router.post("/search/multi",
             response_model=List[ProductSearchResult],
             summary="Поиск изделий по нескольким параметрам (пересечение)")
def search_by_multi_params(request: ProductSearchRequest, db: Session = Depends(get_db)):
    """
    Поиск изделий с применением нескольких фильтров одновременно.
    Возвращает изделия, удовлетворяющие **всем** фильтрам (пересечение).

    Пример тела запроса:
    ```json
    {
        "category_id": 1,
        "filters": [
            {"param_id": 9, "num_min": 500, "num_max": 1000},
            {"param_id": 14, "enum_value_id": 1}
        ]
    }
    ```
    """
    filters = [
        {
            "param_id": f.param_id,
            "num_min": f.num_min,
            "num_max": f.num_max,
            "enum_value_id": f.enum_value_id,
        }
        for f in request.filters
    ]
    rows = search_products_multi_filter(db, request.category_id, filters)
    return [
        ProductSearchResult(
            product_id=r.product_id, product_name=r.product_name,
            category_id=r.category_id, category_name=r.category_name,
            price=r.price, brand=r.brand,
        ) for r in rows
    ]


@router.get("/aggregates",
            response_model=ParamAggregateResponse,
            summary="Агрегаты числового параметра по категории")
def read_param_aggregates(category_id: int, param_id: int, db: Session = Depends(get_db)):
    """
    Возвращает статистику числового параметра по всем изделиям
    в категории и её подкатегориях: count, min, max, avg, sum.
    """
    row = get_param_aggregates(db, category_id, param_id)
    if not row:
        raise HTTPException(status_code=404, detail="Параметр не найден или не является числовым")
    return ParamAggregateResponse(
        param_id=row.param_id, param_name=row.param_name, unit=row.unit,
        count=row.cnt,
        min_val=row.min_val, max_val=row.max_val,
        avg_val=row.avg_val, sum_val=row.sum_val,
    )


@router.get("/search/text", response_model=List[ProductSearchResult],
            summary="Поиск изделий по тексту (название, бренд, описание)")
def search_by_text(
    category_id: int,
    query: str,
    db: Session = Depends(get_db),
):
    """
    Ищет изделия в категории (и её подкатегориях), у которых название, бренд или описание содержат заданный текст.
    """
    if not query or len(query.strip()) == 0:
        return []
    
    # Рекурсивный CTE для получения всех подкатегорий
    cte_sql = """
    WITH RECURSIVE cat_tree AS (
        SELECT id FROM category WHERE id = :cat_id
        UNION ALL
        SELECT c.id FROM category c JOIN cat_tree ct ON c."Category_id" = ct.id
    )
    SELECT p.id AS product_id, p.name AS product_name,
           p."Category_id" AS category_id, c.name AS category_name,
           p.price, p.brand
    FROM product p
    JOIN category c ON c.id = p."Category_id"
    WHERE p."Category_id" IN (SELECT id FROM cat_tree)
      AND (p.name ILIKE :q OR p.brand ILIKE :q OR p.description ILIKE :q)
    ORDER BY p.name
    """
    result = db.execute(
        text(cte_sql),
        {"cat_id": category_id, "q": f"%{query}%"}
    )
    rows = result.fetchall()
    return [
        ProductSearchResult(
            product_id=r.product_id, product_name=r.product_name,
            category_id=r.category_id, category_name=r.category_name,
            price=r.price, brand=r.brand,
        ) for r in rows
    ]
    
    
@router.get("/categories/{category_id}/available-params",
            summary="Список параметров, не назначенных категории")
def get_available_params(category_id: int, db: Session = Depends(get_db)):
    """Возвращает все параметры, которые ещё не назначены данной категории (и не унаследованы)."""
    # Получаем ID параметров, уже назначенных категории (прямо или через наследование)
    assigned = db.execute(
        text("SELECT param_id FROM get_category_params(:id)"),
        {"id": category_id}
    ).fetchall()
    assigned_ids = [row[0] for row in assigned]
    # Все параметры
    all_params = get_all_param_definitions(db)
    # Фильтруем
    available = [p for p in all_params if p.id not in assigned_ids]
    return [
        {
            "id": p.id, "name": p.name, "param_type": p.param_type,
            "unit": p.unit, "enum_class_id": p.enum_class_id,
            "enum_class_name": p.enum_class_name, "is_required": p.is_required
        } for p in available
    ]
    
