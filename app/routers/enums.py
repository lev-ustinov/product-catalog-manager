from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from database import get_db
from crud import (
    get_all_enum_classes, get_enum_class_by_id, create_enum_class,
    update_enum_class, delete_enum_class, get_enum_values,
    get_enum_value_by_id, add_enum_value, update_enum_value,
    delete_enum_value, reorder_enum_values, enum_class_exists
)
from schemas import (
    EnumClassCreate, EnumClassUpdate, EnumClassResponse,
    EnumValueCreate, EnumValueUpdate, EnumValueResponse,
    EnumValueDetailResponse, ReorderEnumValuesRequest
)

router = APIRouter(prefix="/api/enums", tags=["enumerations"])


# ==================== ENUM CLASSES ====================

@router.get("/classes", response_model=List[dict])
def get_all_classes(db: Session = Depends(get_db)):
    """Получить список всех перечислений"""
    result = get_all_enum_classes(db)
    return [{"id": r.id, "name": r.name, "description": r.description, "values_count": r.values_count} for r in result]


@router.get("/classes/{enum_class_id}", response_model=dict)
def get_class_by_id(enum_class_id: int, db: Session = Depends(get_db)):
    """Получить перечисление по ID с его значениями"""
    enum_class = get_enum_class_by_id(db, enum_class_id)
    if not enum_class:
        raise HTTPException(status_code=404, detail="Enum class not found")
    
    values = get_enum_values(db, enum_class_id)
    return {
        "id": enum_class.id,
        "name": enum_class.name,
        "description": enum_class.description,
        "created_at": enum_class.created_at,
        "values": [{"id": v.id, "value": v.value, "sort_order": v.sort_order, "is_active": v.is_active} for v in values]
    }


@router.post("/classes", response_model=EnumClassResponse, status_code=status.HTTP_201_CREATED)
def create_new_enum_class(enum_class: EnumClassCreate, db: Session = Depends(get_db)):
    """Создать новое перечисление"""
    if enum_class_exists(db, enum_class.name):
        raise HTTPException(status_code=400, detail=f"Enum class with name '{enum_class.name}' already exists")
    
    result = create_enum_class(db, enum_class.name, enum_class.description)
    return result


@router.patch("/classes/{enum_class_id}", response_model=EnumClassResponse)
def update_existing_enum_class(enum_class_id: int, updates: EnumClassUpdate, db: Session = Depends(get_db)):
    """Обновить перечисление"""
    if updates.name and enum_class_exists(db, updates.name, enum_class_id):
        raise HTTPException(status_code=400, detail=f"Enum class with name '{updates.name}' already exists")
    
    result = update_enum_class(db, enum_class_id, updates.name, updates.description)
    if not result:
        raise HTTPException(status_code=404, detail="Enum class not found")
    return result


@router.delete("/classes/{enum_class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_enum_class(enum_class_id: int, db: Session = Depends(get_db)):
    """Удалить перечисление"""
    enum_class = get_enum_class_by_id(db, enum_class_id)
    if not enum_class:
        raise HTTPException(status_code=404, detail="Enum class not found")
    delete_enum_class(db, enum_class_id)


# ==================== ENUM VALUES ====================

@router.get("/classes/{enum_class_id}/values", response_model=List[EnumValueResponse])
def get_class_values(enum_class_id: int, db: Session = Depends(get_db)):
    """Получить все значения перечисления"""
    enum_class = get_enum_class_by_id(db, enum_class_id)
    if not enum_class:
        raise HTTPException(status_code=404, detail="Enum class not found")
    
    values = get_enum_values(db, enum_class_id)
    
    # values возвращает кортежи (id, value, sort_order, is_active)
    return [{"id": v[0], "value": v[1], "sort_order": v[2], "is_active": v[3], "enum_class_id": enum_class_id} for v in values]

@router.get("/values/{value_id}", response_model=EnumValueDetailResponse)
def get_value_by_id(value_id: int, db: Session = Depends(get_db)):
    """Получить значение перечисления по ID"""
    result = get_enum_value_by_id(db, value_id)
    if not result:
        raise HTTPException(status_code=404, detail="Enum value not found")
    return {"id": result.id, "value": result.value, "class_name": result.class_name, "class_description": result.class_description}


@router.post("/classes/{enum_class_id}/values", response_model=EnumValueResponse, status_code=status.HTTP_201_CREATED)
def create_enum_value(enum_class_id: int, enum_value: EnumValueCreate, db: Session = Depends(get_db)):
    """Добавить значение в перечисление"""
    enum_class = get_enum_class_by_id(db, enum_class_id)
    if not enum_class:
        raise HTTPException(status_code=404, detail="Enum class not found")
    
    result = add_enum_value(db, enum_class_id, enum_value.value, enum_value.sort_order)
    # result – это кортеж (id, value, sort_order, is_active)
    return {
        "id": result.id,
        "value": result.value,
        "sort_order": result.sort_order,
        "is_active": result.is_active,
        "enum_class_id": enum_class_id,
    }


@router.patch("/values/{value_id}", response_model=EnumValueResponse)
def update_existing_enum_value(value_id: int, updates: EnumValueUpdate, db: Session = Depends(get_db)):
    """Обновить значение перечисления"""
    # сначала получаем старый объект, чтобы знать enum_class_id
    old = get_enum_value_by_id(db, value_id)
    if not old:
        raise HTTPException(status_code=404, detail="Enum value not found")
    result = update_enum_value(db, value_id, updates.value, updates.sort_order, updates.is_active)
    if not result:
        raise HTTPException(status_code=404, detail="Enum value not found")
    # result – (id, value, sort_order, is_active)
    return {
        "id": result[0],
        "value": result[1],
        "sort_order": result[2],
        "is_active": result[3],
        "enum_class_id": old.enum_class_id,   # берём из старой записи
    }

@router.delete("/values/{value_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_enum_value(value_id: int, db: Session = Depends(get_db)):
    """Удалить значение перечисления (мягкое удаление)"""
    existing = get_enum_value_by_id(db, value_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Enum value not found")
    delete_enum_value(db, value_id)


@router.put("/classes/{enum_class_id}/reorder")
def reorder_values(enum_class_id: int, request: ReorderEnumValuesRequest, db: Session = Depends(get_db)):
    """Изменить порядок значений перечисления"""
    enum_class = get_enum_class_by_id(db, enum_class_id)
    if not enum_class:
        raise HTTPException(status_code=404, detail="Enum class not found")
    
    reorder_enum_values(db, enum_class_id, request.value_ids)
    return {"status": "ok", "message": "Order updated successfully"}