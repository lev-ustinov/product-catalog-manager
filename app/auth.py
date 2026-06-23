"""
Authentication module — JWT-based.

POST /auth/login  → returns access_token
All protected endpoints require  Authorization: Bearer <token>
Roles: admin | user
"""

import os
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import get_db

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

security = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


# ── Password helpers (bcrypt directly — no passlib) ───────────────────────────

def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the password."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ── DB-aware authentication ───────────────────────────────────────────────────

def _authenticate_user(db: Session, username: str, password: str) -> Optional[str]:
    """
    Returns role ('admin'|'user') on success, None on failure.
    Checks app_user table first; falls back to env credentials if the
    table doesn't exist yet (pre-migration) or the user isn't found there.
    """
    from models import User

    try:
        db_user = db.query(User).filter(
            User.username == username,
            User.is_active == True,
        ).first()

        if db_user is not None:
            # User exists in DB — only accept if password matches; no env fallback
            return db_user.role if verify_password(password, db_user.password_hash) else None

    except Exception:
        # Table doesn't exist yet — fall through to env fallback below
        try:
            db.rollback()
        except Exception:
            pass

    # Env-based fallback: works even before migrations are applied
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return "admin"

    return None


# ── FastAPI dependencies ──────────────────────────────────────────────────────

def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Decode JWT and return role. Raises 401 on any failure."""
    payload = _decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    role = payload.get("role")
    if role not in ("admin", "user"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return role


def get_current_username(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Extract username from JWT for audit logging."""
    payload = _decode_token(credentials.credentials)
    if not payload:
        return "anonymous"
    return payload.get("sub", "anonymous")


def get_optional_username(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
) -> str:
    """
    Best-effort username extraction for audit logging on endpoints that
    do NOT require authentication. Never raises:
      - no Authorization header  -> "anonymous"
      - invalid / expired token   -> "anonymous"
      - valid token                -> the 'sub' claim (username)
    """
    if credentials is None:
        return "anonymous"
    payload = _decode_token(credentials.credentials)
    if not payload:
        return "anonymous"
    return payload.get("sub", "anonymous")


def require_admin(role: str = Depends(verify_token)) -> str:
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin rights required",
        )
    return role


def optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
) -> Optional[str]:
    """Returns role or None for unauthenticated requests."""
    if credentials is None:
        return None
    payload = _decode_token(credentials.credentials)
    return payload.get("role") if payload else None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Получить JWT access-token",
    description=(
        "Принимает username и password, возвращает JWT access-token. "
        "Используйте заголовок Authorization: Bearer <token> для всех защищённых запросов."
    ),
)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    role = _authenticate_user(db, data.username, data.password)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    token = create_access_token({"sub": data.username, "role": role})
    return TokenResponse(access_token=token, token_type="bearer", role=role)


@router.get(
    "/me",
    summary="Текущий пользователь",
    description="Возвращает информацию о текущем авторизованном пользователе.",
)
def me(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = _decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"username": payload.get("sub"), "role": payload.get("role")}
