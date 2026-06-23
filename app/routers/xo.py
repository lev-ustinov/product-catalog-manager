"""
Роутер для управления Хозяйственными Операциями ().

Покрывает:
- CRUD классификатора классов ХО (xo_class) с иерархией
- Редактирование состава параметров и ролей каждого класса ХО
- CRUD экземпляров ХО с управлением статусом (draft/posted/cancelled)
- Установку значений параметров экземпляров с проверкой ограничений
- Назначение ролей участникам экземпляров ХО
- Управление строками (табличной частью) экземпляров ХО
- Поиск ХО по классу и значениям параметров
- Полное представление всех характеристик конкретной ХО
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from decimal import Decimal

from database import get_db
from models import XOParamDef
from auth import get_optional_username
from audit_log import log_action
from crud import (
    get_xo_class, get_all_xo_classes, create_xo_class, update_xo_class,
    delete_xo_class, move_xo_class,
    get_xo_class_template, assign_param_to_xo_class, remove_param_from_xo_class,
    get_xo_class_roles, create_xo_role_def, delete_xo_role_def,
    get_xo_instance, get_xo_instances, create_xo_instance, update_xo_instance,
    get_xo_params, set_xo_param_value, delete_xo_param_value,
    get_xo_roles, assign_xo_role, remove_xo_role,
    get_xo_lines, add_xo_line, delete_xo_line,
    get_xo_full, search_xo_by_param,
    post_xo_instance, cancel_xo_instance, delete_xo_instance,
)
from schemas import (
    XOClassCreate, XOClassUpdate, XOClassResponse, XOClassTreeNode,
    XOParamDefCreate, XOParamDefUpdate, XOParamDefResponse,
    XORoleDefCreate, XORoleDefUpdate, XORoleDefResponse,
    XOInstanceCreate, XOInstanceUpdate, XOInstanceResponse,
    XOParamValueSet, XOParamValueResponse,
    XORoleAssignCreate, XORoleAssignResponse,
    XOLineCreate, XOLineResponse,
    XOFullFieldResponse, XOSearchResult,
)

router = APIRouter(prefix="/api/xo", tags=["xo"])


# =============================================
# КЛАССИФИКАТОР ХО
# =============================================

@router.get("/classes/tree", response_model=List[XOClassTreeNode],
            summary="Дерево классификатора ХО")
def read_xo_class_tree(db: Session = Depends(get_db)):
    """Возвращает полную иерархию классов ХО с глубиной и количеством экземпляров."""
    rows = get_all_xo_classes(db)
    return [
        XOClassTreeNode(
            id=r.id, name=r.name, description=r.description,
            parent_id=r.parent_id, sort_order=r.sort_order,
            depth=r.depth, instance_count=r.instance_count,
        ) for r in rows
    ]


@router.get("/classes/{xo_class_id}", response_model=XOClassResponse,
            summary="Получить класс ХО по ID")
def read_xo_class(xo_class_id: int, db: Session = Depends(get_db)):
    cls = get_xo_class(db, xo_class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Класс ХО не найден")
    return XOClassResponse(id=cls.id, name=cls.name, description=cls.description,
                           parent_id=cls.parent_id, sort_order=cls.sort_order)


@router.post("/classes", response_model=XOClassResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Создать новый класс ХО")
def create_new_xo_class(data: XOClassCreate, db: Session = Depends(get_db)):
    """
    Создаёт класс в классификаторе ХО.
    - Если `parent_id` задан — создаётся подкласс указанного класса
    - Если `parent_id` не задан — корневой класс
    """
    try:
        cls = create_xo_class(db, data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return XOClassResponse(id=cls.id, name=cls.name, description=cls.description,
                           parent_id=cls.parent_id, sort_order=cls.sort_order)


@router.patch("/classes/{xo_class_id}", response_model=XOClassResponse,
              summary="Обновить класс ХО")
def update_existing_xo_class(xo_class_id: int, data: XOClassUpdate,
                              db: Session = Depends(get_db)):
    if not get_xo_class(db, xo_class_id):
        raise HTTPException(status_code=404, detail="Класс ХО не найден")
    try:
        cls = update_xo_class(db, xo_class_id, data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return XOClassResponse(id=cls.id, name=cls.name, description=cls.description,
                           parent_id=cls.parent_id, sort_order=cls.sort_order)


@router.delete("/classes/{xo_class_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Удалить класс ХО")
def delete_existing_xo_class(xo_class_id: int, db: Session = Depends(get_db)):
    """Удаление невозможно если класс имеет экземпляры или дочерние классы."""
    try:
        delete_xo_class(db, xo_class_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/classes/{xo_class_id}/move", response_model=XOClassResponse,
            summary="Переместить класс ХО в другой родитель")
def move_existing_xo_class(xo_class_id: int,
                            new_parent_id: Optional[int] = None,
                            db: Session = Depends(get_db)):
    try:
        cls = move_xo_class(db, xo_class_id, new_parent_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return XOClassResponse(id=cls.id, name=cls.name, description=cls.description,
                           parent_id=cls.parent_id, sort_order=cls.sort_order)


# =============================================
# ПАРАМЕТРЫ КЛАССОВ ХО (шаблон)
# =============================================

@router.get("/classes/{xo_class_id}/params", response_model=List[XOParamDefResponse],
            summary="Шаблон параметров класса ХО (с наследованием от предков)")
def read_xo_class_template(xo_class_id: int, db: Session = Depends(get_db)):
    """
    Возвращает полный набор параметров для класса ХО:
    - собственные (назначенные напрямую)
    - унаследованные от родительских классов (где `is_inherited=True`)

    Поле `is_inherited_xo` показывает, унаследован ли параметр.
    """
    if not get_xo_class(db, xo_class_id):
        raise HTTPException(status_code=404, detail="Класс ХО не найден")
    rows = get_xo_class_template(db, xo_class_id)
    return [
        XOParamDefResponse(
            param_def_id=r.param_def_id, param_name=r.param_name,
            param_type=r.param_type, unit=r.unit,
            min_value=r.min_value, max_value=r.max_value,
            enum_class_id=r.enum_class_id, enum_class_name=r.enum_class_name,
            is_required=r.is_required, is_inherited_xo=r.is_inherited_xo,
            source_class_id=r.source_class_id, source_class_name=r.source_class_name,
            sort_order=r.sort_order,
        ) for r in rows
    ]


@router.post("/classes/{xo_class_id}/params", status_code=status.HTTP_201_CREATED,
             summary="Назначить параметр классу ХО")
def assign_param_xo(xo_class_id: int, data: XOParamDefCreate,
                    db: Session = Depends(get_db)):
    """
    Назначает параметр (из `param_definition`) классу ХО.
    - `is_inherited=true` — параметр передаётся подклассам
    """
    try:
        assign_param_to_xo_class(db, xo_class_id, data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "xo_class_id": xo_class_id, "param_def_id": data.param_def_id}


@router.delete("/classes/{xo_class_id}/params/{param_def_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               summary="Снять параметр с класса ХО")
def remove_param_xo(xo_class_id: int, param_def_id: int, db: Session = Depends(get_db)):
    try:
        remove_param_from_xo_class(db, xo_class_id, param_def_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================
# РОЛИ КЛАССОВ ХО
# =============================================

@router.get("/classes/{xo_class_id}/roles", response_model=List[XORoleDefResponse],
            summary="Список ролей класса ХО")
def read_xo_class_roles(xo_class_id: int, db: Session = Depends(get_db)):
    if not get_xo_class(db, xo_class_id):
        raise HTTPException(status_code=404, detail="Класс ХО не найден")
    rows = get_xo_class_roles(db, xo_class_id)
    return [
        XORoleDefResponse(id=r.id, name=r.name, description=r.description,
                          is_required=r.is_required, subject_type=r.subject_type)
        for r in rows
    ]


@router.post("/classes/{xo_class_id}/roles", response_model=XORoleDefResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Добавить роль к классу ХО")
def create_xo_role(xo_class_id: int, data: XORoleDefCreate, db: Session = Depends(get_db)):
    if not get_xo_class(db, xo_class_id):
        raise HTTPException(status_code=404, detail="Класс ХО не найден")
    try:
        role = create_xo_role_def(db, xo_class_id, data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return XORoleDefResponse(id=role.id, name=role.name, description=role.description,
                             is_required=role.is_required, subject_type=role.subject_type)


@router.delete("/roles/{role_def_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Удалить роль класса ХО")
def delete_xo_role(role_def_id: int, db: Session = Depends(get_db)):
    """Удаление невозможно если роль уже назначена в экземплярах ХО."""
    try:
        delete_xo_role_def(db, role_def_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================
# ЭКЗЕМПЛЯРЫ ХО
# =============================================

@router.get("/instances", response_model=List[XOInstanceResponse],
            summary="Список экземпляров ХО")
def read_xo_instances(
    xo_class_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Возвращает список экземпляров ХО с фильтрацией по классу и статусу.
    Статусы: `draft`, `posted`, `cancelled`.
    """
    instances = get_xo_instances(db, xo_class_id, status, limit, offset)
    return [
        XOInstanceResponse(
            id=xi.id, xo_class_id=xi.xo_class_id,
            xo_class_name=xi.xo_class.name if xi.xo_class else None,
            number=xi.number, op_date=xi.op_date, status=xi.status,
            notes=xi.notes, created_at=xi.created_at, created_by=xi.created_by,
        ) for xi in instances
    ]


@router.get("/instances/{xo_id}", response_model=XOInstanceResponse,
            summary="Получить экземпляр ХО по ID")
def read_xo_instance(xo_id: int, db: Session = Depends(get_db)):
    xi = get_xo_instance(db, xo_id)
    if not xi:
        raise HTTPException(status_code=404, detail="Экземпляр ХО не найден")
    return XOInstanceResponse(
        id=xi.id, xo_class_id=xi.xo_class_id,
        xo_class_name=xi.xo_class.name if xi.xo_class else None,
        number=xi.number, op_date=xi.op_date, status=xi.status,
        notes=xi.notes, created_at=xi.created_at, created_by=xi.created_by,
    )


@router.post("/instances", response_model=XOInstanceResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Создать экземпляр ХО")
def create_new_xo_instance(
    data: XOInstanceCreate,
    actor: str = Depends(get_optional_username),
    db: Session = Depends(get_db),
):
    """
    Создаёт новый экземпляр ХО в статусе `draft`.
    Для редактирования параметров, ролей и строк используйте отдельные эндпоинты.
    """
    try:
        xi = create_xo_instance(db, data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    cls_name = xi.xo_class.name if xi.xo_class else "—"
    number_part = f", № {xi.number}" if xi.number else ""
    log_action(db, actor, "create", "xo_instance", xi.id,
               f"Создан экземпляр ХО «{cls_name}»{number_part} от {xi.op_date}")

    return XOInstanceResponse(
        id=xi.id, xo_class_id=xi.xo_class_id,
        xo_class_name=xi.xo_class.name if xi.xo_class else None,
        number=xi.number, op_date=xi.op_date, status=xi.status,
        notes=xi.notes, created_at=xi.created_at, created_by=xi.created_by,
    )


@router.patch("/instances/{xo_id}", response_model=XOInstanceResponse,
              summary="Обновить экземпляр ХО (только в статусе draft)")
def update_existing_xo_instance(
    xo_id: int,
    data: XOInstanceUpdate,
    actor: str = Depends(get_optional_username),
    db: Session = Depends(get_db),
):
    if not get_xo_instance(db, xo_id):
        raise HTTPException(status_code=404, detail="Экземпляр ХО не найден")
    try:
        xi = update_xo_instance(db, xo_id, data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    changes = []
    if data.number is not None:
        changes.append(f"номер → «{data.number}»")
    if data.op_date is not None:
        changes.append(f"дата операции → {data.op_date}")
    if data.notes is not None:
        changes.append("примечания изменены")
    details = f"ХО id={xo_id}: " + ("; ".join(changes) if changes else "без изменений")
    log_action(db, actor, "update", "xo_instance", xo_id, details)

    return XOInstanceResponse(
        id=xi.id, xo_class_id=xi.xo_class_id,
        xo_class_name=xi.xo_class.name if xi.xo_class else None,
        number=xi.number, op_date=xi.op_date, status=xi.status,
        notes=xi.notes, created_at=xi.created_at, created_by=xi.created_by,
    )


@router.post("/instances/{xo_id}/post", response_model=XOInstanceResponse,
             summary="Провести ХО (draft → posted)")
def post_xo(
    xo_id: int,
    actor: str = Depends(get_optional_username),
    db: Session = Depends(get_db),
):
    """
    Переводит ХО в статус `posted`.
    Перед проведением проверяет заполнение всех обязательных ролей.
    """
    if not get_xo_instance(db, xo_id):
        raise HTTPException(status_code=404, detail="Экземпляр ХО не найден")
    try:
        xi = post_xo_instance(db, xo_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    cls_name = xi.xo_class.name if xi.xo_class else "—"
    number_part = f", № {xi.number}" if xi.number else ""
    log_action(db, actor, "post", "xo_instance", xo_id,
               f"Проведена ХО «{cls_name}»{number_part} от {xi.op_date}")

    return XOInstanceResponse(
        id=xi.id, xo_class_id=xi.xo_class_id,
        xo_class_name=xi.xo_class.name if xi.xo_class else None,
        number=xi.number, op_date=xi.op_date, status=xi.status,
        notes=xi.notes, created_at=xi.created_at, created_by=xi.created_by,
    )


@router.post("/instances/{xo_id}/cancel", response_model=XOInstanceResponse,
             summary="Отменить ХО (→ cancelled)")
def cancel_xo(
    xo_id: int,
    reason: Optional[str] = None,
    actor: str = Depends(get_optional_username),
    db: Session = Depends(get_db),
):
    if not get_xo_instance(db, xo_id):
        raise HTTPException(status_code=404, detail="Экземпляр ХО не найден")
    try:
        xi = cancel_xo_instance(db, xo_id, reason)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    cls_name = xi.xo_class.name if xi.xo_class else "—"
    number_part = f", № {xi.number}" if xi.number else ""
    reason_part = f". Причина: {reason}" if reason else ""
    log_action(db, actor, "cancel", "xo_instance", xo_id,
               f"Отменена ХО «{cls_name}»{number_part}{reason_part}")

    return XOInstanceResponse(
        id=xi.id, xo_class_id=xi.xo_class_id,
        xo_class_name=xi.xo_class.name if xi.xo_class else None,
        number=xi.number, op_date=xi.op_date, status=xi.status,
        notes=xi.notes, created_at=xi.created_at, created_by=xi.created_by,
    )


# =============================================
# ЗНАЧЕНИЯ ПАРАМЕТРОВ ЭКЗЕМПЛЯРОВ ХО
# =============================================

@router.get("/instances/{xo_id}/params", response_model=List[XOParamValueResponse],
            summary="Значения параметров экземпляра ХО")
def read_xo_instance_params(xo_id: int, db: Session = Depends(get_db)):
    if not get_xo_instance(db, xo_id):
        raise HTTPException(status_code=404, detail="Экземпляр ХО не найден")
    rows = get_xo_params(db, xo_id)
    return [
        XOParamValueResponse(
            param_def_id=r.param_def_id, param_name=r.param_name,
            param_type=r.param_type, unit=r.unit,
            numeric_value=r.numeric_value, text_value=r.text_value,
            enum_value_id=r.enum_value_id, enum_value_text=r.enum_value_text,
        ) for r in rows
    ]


@router.put("/instances/{xo_id}/params", summary="Установить значение параметра ХО")
def set_xo_instance_param(xo_id: int, data: XOParamValueSet,
                           db: Session = Depends(get_db)):
    """
    Устанавливает значение параметра. Проверяет:
    - ограничения min/max для числовых параметров
    - принадлежность enum-значения нужному перечислению
    - статус ХО (только draft)
    """
    if not get_xo_instance(db, xo_id):
        raise HTTPException(status_code=404, detail="Экземпляр ХО не найден")
    try:
        set_xo_param_value(db, xo_id, data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "xo_id": xo_id, "param_def_id": data.param_def_id}


@router.delete("/instances/{xo_id}/params/{param_def_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               summary="Удалить значение параметра ХО")
def delete_xo_instance_param(xo_id: int, param_def_id: int,
                               db: Session = Depends(get_db)):
    try:
        delete_xo_param_value(db, xo_id, param_def_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================
# РОЛИ ЭКЗЕМПЛЯРОВ ХО
# =============================================

@router.get("/instances/{xo_id}/roles", response_model=List[XORoleAssignResponse],
            summary="Назначения ролей в экземпляре ХО")
def read_xo_instance_roles(xo_id: int, db: Session = Depends(get_db)):
    """Возвращает все роли класса ХО с указанием кто назначен (или None если не назначено)."""
    if not get_xo_instance(db, xo_id):
        raise HTTPException(status_code=404, detail="Экземпляр ХО не найден")
    rows = get_xo_roles(db, xo_id)
    return [
        XORoleAssignResponse(
            role_def_id=r.role_def_id, role_name=r.role_name,
            is_required=r.is_required, subject_name=r.subject_name,
            subject_type=r.subject_type, subject_id=r.subject_id,
        ) for r in rows
    ]


@router.put("/instances/{xo_id}/roles", summary="Назначить субъекта на роль в ХО")
def assign_role_xo(xo_id: int, data: XORoleAssignCreate, db: Session = Depends(get_db)):
    if not get_xo_instance(db, xo_id):
        raise HTTPException(status_code=404, detail="Экземпляр ХО не найден")
    try:
        assign_xo_role(db, xo_id, data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "xo_id": xo_id, "role_def_id": data.role_def_id}


@router.delete("/instances/{xo_id}/roles/{role_def_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               summary="Снять назначение роли в ХО")
def remove_role_xo(xo_id: int, role_def_id: int, db: Session = Depends(get_db)):
    try:
        remove_xo_role(db, xo_id, role_def_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================
# СТРОКИ (ТАБЛИЧНАЯ ЧАСТЬ) ХО
# =============================================

@router.get("/instances/{xo_id}/lines", response_model=List[XOLineResponse],
            summary="Строки табличной части экземпляра ХО")
def read_xo_instance_lines(xo_id: int, db: Session = Depends(get_db)):
    if not get_xo_instance(db, xo_id):
        raise HTTPException(status_code=404, detail="Экземпляр ХО не найден")
    rows = get_xo_lines(db, xo_id)
    return [
        XOLineResponse(
            line_id=r.line_id, line_order=r.line_order,
            product_id=r.product_id, product_name=r.product_name,
            quantity=r.quantity, price=r.price, amount=r.amount,
            unit_name=r.unit_name,
        ) for r in rows
    ]


@router.post("/instances/{xo_id}/lines", status_code=status.HTTP_201_CREATED,
             summary="Добавить строку в табличную часть ХО")
def add_line_to_xo(xo_id: int, data: XOLineCreate, db: Session = Depends(get_db)):
    """quantity должно быть > 0. ХО должна быть в статусе draft."""
    if not get_xo_instance(db, xo_id):
        raise HTTPException(status_code=404, detail="Экземпляр ХО не найден")
    try:
        line_id = add_xo_line(db, xo_id, data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "line_id": line_id}


@router.delete("/lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Удалить строку из ХО")
def delete_line_from_xo(line_id: int, db: Session = Depends(get_db)):
    try:
        delete_xo_line(db, line_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================
# ПОЛНОЕ ПРЕДСТАВЛЕНИЕ И ПОИСК
# =============================================

@router.get("/instances/{xo_id}/full", response_model=List[XOFullFieldResponse],
            summary="Полное представление всех характеристик ХО")
def read_xo_full(xo_id: int, db: Session = Depends(get_db)):
    """
    Возвращает все характеристики ХО в плоском виде:
    - `header` — реквизиты (номер, дата, статус, класс)
    - `role` — назначения ролей
    - `param` — значения параметров
    - `line` — строки табличной части
    """
    if not get_xo_instance(db, xo_id):
        raise HTTPException(status_code=404, detail="Экземпляр ХО не найден")
    rows = get_xo_full(db, xo_id)
    return [
        XOFullFieldResponse(
            field_type=r.field_type,
            field_name=r.field_name,
            field_value=r.field_value,
        ) for r in rows
    ]


@router.get("/search", response_model=List[XOSearchResult],
            summary="Поиск ХО заданного класса по значению параметра")
def search_xo(
    xo_class_id: int,
    param_def_id: int,
    num_min: Optional[Decimal] = None,
    num_max: Optional[Decimal] = None,
    enum_value_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Ищет экземпляры ХО указанного класса (и всех подклассов) по значению параметра.

    Примеры:
    - Числовой диапазон: `?xo_class_id=1&param_def_id=5&num_min=1000&num_max=50000`
    - Перечисление: `?xo_class_id=1&param_def_id=8&enum_value_id=3`
    - С фильтром по статусу: добавить `&status=posted`
    """
    rows = search_xo_by_param(db, xo_class_id, param_def_id,
                               num_min, num_max, enum_value_id, status)
    return [
        XOSearchResult(
            xo_id=r.xo_id, xo_number=r.xo_number, xo_class=r.xo_class,
            op_date=r.op_date, status=r.status,
            param_name=r.param_name, param_value=r.param_value,
        ) for r in rows
    ]

@router.patch("/classes/{xo_class_id}/params/{param_def_id}",
              summary="Обновить настройки параметра класса ХО")
def update_xo_param(xo_class_id: int, param_def_id: int,
                    data: XOParamDefUpdate, db: Session = Depends(get_db)):
    """Обновляет is_inherited и sort_order для параметра класса ХО."""
    xp = db.query(XOParamDef).filter(
        XOParamDef.xo_class_id == xo_class_id,
        XOParamDef.param_def_id == param_def_id
    ).first()
    if not xp:
        raise HTTPException(status_code=404, detail="Параметр не назначен классу")
    if data.is_inherited is not None:
        xp.is_inherited = data.is_inherited
    if data.sort_order is not None:
        xp.sort_order = data.sort_order
    db.commit()
    return {"status": "ok"}
    
@router.delete("/instances/{xo_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Удалить экземпляр ХО (только draft)")
def delete_xo(
    xo_id: int,
    actor: str = Depends(get_optional_username),
    db: Session = Depends(get_db),
):
    xi = get_xo_instance(db, xo_id)
    if not xi:
        raise HTTPException(status_code=404, detail="Экземпляр ХО не найден")

    cls_name = xi.xo_class.name if xi.xo_class else "—"
    number_part = f", № {xi.number}" if xi.number else ""

    try:
        delete_xo_instance(db, xo_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    log_action(db, actor, "delete", "xo_instance", xo_id,
               f"Удалён экземпляр ХО «{cls_name}»{number_part}")