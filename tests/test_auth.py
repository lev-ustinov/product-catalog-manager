"""
Authentication: password hashing, JWT issuance/validation, /auth/login,
/auth/me, and the env-fallback admin account.
"""

import auth


def test_password_hash_roundtrip():
    hashed = auth.hash_password("s3cret!")
    assert hashed != "s3cret!"
    assert auth.verify_password("s3cret!", hashed) is True
    assert auth.verify_password("wrong", hashed) is False


def test_create_and_decode_token():
    token = auth.create_access_token({"sub": "admin", "role": "admin"})
    payload = auth._decode_token(token)
    assert payload["sub"] == "admin"
    assert payload["role"] == "admin"
    assert "exp" in payload


def test_decode_invalid_token_returns_none():
    assert auth._decode_token("not-a-valid-jwt") is None


def test_login_success_env_fallback(client):
    """Before any app_user rows exist, admin/admin123 from .env must work."""
    r = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["role"] == "admin"
    assert len(body["access_token"]) > 20


def test_login_wrong_password(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/auth/login", json={"username": "ghost", "password": "whatever"})
    assert r.status_code == 401


def test_auth_me_with_valid_token(client, admin_headers):
    r = client.get("/auth/me", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"


def test_protected_endpoint_without_token(client):
    r = client.get("/api/users/")
    assert r.status_code == 403  # HTTPBearer auto_error


def test_protected_endpoint_with_garbage_token(client):
    r = client.get("/api/users/", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401


def test_db_user_takes_precedence_over_env(client, db_session):
    """
    Once 'admin' exists in app_user with a DIFFERENT password, the env
    fallback for that username must no longer apply.
    """
    from models import User

    db_session.add(User(
        username="admin",
        password_hash=auth.hash_password("dbpassword"),
        role="admin",
        is_active=True,
    ))
    db_session.commit()

    # Old env password no longer works for this username
    r = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 401

    # New DB password works
    r = client.post("/auth/login", json={"username": "admin", "password": "dbpassword"})
    assert r.status_code == 200
    assert r.json()["role"] == "admin"
