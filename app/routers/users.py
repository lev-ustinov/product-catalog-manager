"""
User management endpoints (admin only).
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError
from typing import List

from database import get_db
from auth import require_admin, get_current_username, hash_password
from models import User
from schemas import UserCreate, UserUpdate, UserResponse
from audit_log import log_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get(
    "/",
    response_model=List[UserResponse],
    summary="Список пользователей",
    description="Возвращает всех пользователей системы. Только для администратора.",
)
def list_users(
    _role: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        return db.query(User).order_by(User.id).all()
    except OperationalError as exc:
        logger.error("list_users DB error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database error — make sure migrations are applied (alembic upgrade head).",
        )


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать пользователя",
    description="Создаёт нового пользователя системы. Только для администратора.",
)
def create_user(
    data: UserCreate,
    _role: str = Depends(require_admin),
    actor: str = Depends(get_current_username),
    db: Session = Depends(get_db),
):
    # Validate input
    if not data.username or not data.username.strip():
        raise HTTPException(status_code=400, detail="Username must not be empty.")
    if not data.password or len(data.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters.")
    if data.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'.")

    # Duplicate check
    try:
        existing = db.query(User).filter(
            User.username == data.username.strip()
        ).first()
    except OperationalError as exc:
        logger.error("create_user duplicate-check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database error — run 'alembic upgrade head' to create the app_user table.",
        )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{data.username}' is already taken.",
        )

    user = User(
        username=data.username.strip(),
        password_hash=hash_password(data.password),
        role=data.role,
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{data.username}' is already taken.",
        )
    except OperationalError as exc:
        db.rollback()
        logger.error("create_user insert failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database error while creating user. Check server logs.",
        )
    except Exception as exc:
        db.rollback()
        logger.exception("create_user unexpected error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {exc}",
        )

    # Audit is a separate, best-effort step — failures here must not
    # affect the already-committed user creation above.
    log_action(db, actor, "create", "user", user.id,
               f"Создан пользователь «{user.username}» (роль={user.role})")

    return user


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Обновить пользователя",
    description="Обновляет пароль, роль или статус активности. Только для администратора.",
)
def update_user(
    user_id: int,
    data: UserUpdate,
    _role: str = Depends(require_admin),
    actor: str = Depends(get_current_username),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if data.role is not None and data.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'.")

    changes: List[str] = []

    if data.password is not None:
        if len(data.password) < 4:
            raise HTTPException(status_code=400, detail="Password must be at least 4 characters.")
        user.password_hash = hash_password(data.password)
        changes.append("пароль изменён")

    if data.role is not None:
        user.role = data.role
        changes.append(f"роль → {data.role}")

    if data.is_active is not None:
        user.is_active = data.is_active
        changes.append(f"активен → {data.is_active}")

    try:
        db.commit()
        db.refresh(user)
    except Exception as exc:
        db.rollback()
        logger.exception("update_user failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Update failed: {exc}")

    log_action(db, actor, "update", "user", user.id,
               f"Пользователь «{user.username}»: " + ("; ".join(changes) if changes else "без изменений"))

    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить пользователя",
    description="Удаляет пользователя из системы. Только для администратора.",
)
def delete_user(
    user_id: int,
    _role: str = Depends(require_admin),
    actor: str = Depends(get_current_username),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    username = user.username

    try:
        db.delete(user)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("delete_user failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Delete failed: {exc}")

    log_action(db, actor, "delete", "user", user_id, f"Удалён пользователь «{username}»")
