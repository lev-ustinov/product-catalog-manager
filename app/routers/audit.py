"""
Audit log endpoints — admin only.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from auth import require_admin
from models import AuditLog
from schemas import AuditLogResponse

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get(
    "/",
    response_model=List[AuditLogResponse],
    summary="Журнал изменений",
    description=(
        "Возвращает записи журнала аудита с пагинацией. "
        "Доступно только администратору. "
        "Можно фильтровать по типу сущности и действию."
    ),
)
def list_audit_logs(
    entity_type: Optional[str] = Query(None, description="Тип сущности: product, category, xo_instance, user"),
    action: Optional[str] = Query(None, description="Действие: create, update, delete, post, cancel"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _role: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if action:
        q = q.filter(AuditLog.action == action)
    return q.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset).all()
