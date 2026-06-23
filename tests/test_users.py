"""
User management: CRUD via /api/users/, role-based access control,
validation, and the audit trail those operations produce.
"""


def test_create_user(client, admin_headers):
    r = client.post(
        "/api/users/",
        json={"username": "newuser", "password": "pass1234", "role": "user"},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["username"] == "newuser"
    assert body["role"] == "user"
    assert body["is_active"] is True
    assert "password" not in body
    assert "password_hash" not in body


def test_create_user_duplicate_username(client, admin_headers):
    payload = {"username": "dup", "password": "pass1234", "role": "user"}
    r1 = client.post("/api/users/", json=payload, headers=admin_headers)
    assert r1.status_code == 201

    r2 = client.post("/api/users/", json=payload, headers=admin_headers)
    assert r2.status_code == 400
    assert "taken" in r2.json()["detail"].lower()


def test_create_user_validation_errors(client, admin_headers):
    # empty username
    r = client.post(
        "/api/users/",
        json={"username": "  ", "password": "pass1234", "role": "user"},
        headers=admin_headers,
    )
    assert r.status_code == 400

    # password too short
    r = client.post(
        "/api/users/",
        json={"username": "shortpw", "password": "123", "role": "user"},
        headers=admin_headers,
    )
    assert r.status_code == 400

    # invalid role
    r = client.post(
        "/api/users/",
        json={"username": "badrole", "password": "pass1234", "role": "superuser"},
        headers=admin_headers,
    )
    assert r.status_code == 400


def test_non_admin_cannot_manage_users(client, user_headers):
    r = client.get("/api/users/", headers=user_headers)
    assert r.status_code == 403

    r = client.post(
        "/api/users/",
        json={"username": "sneaky", "password": "pass1234", "role": "admin"},
        headers=user_headers,
    )
    assert r.status_code == 403


def test_list_users_includes_created(client, admin_headers):
    client.post(
        "/api/users/",
        json={"username": "alice", "password": "pass1234", "role": "user"},
        headers=admin_headers,
    )
    r = client.get("/api/users/", headers=admin_headers)
    assert r.status_code == 200
    usernames = [u["username"] for u in r.json()]
    assert "alice" in usernames


def test_update_user_role(client, admin_headers):
    r = client.post(
        "/api/users/",
        json={"username": "bob", "password": "pass1234", "role": "user"},
        headers=admin_headers,
    )
    user_id = r.json()["id"]

    r = client.patch(f"/api/users/{user_id}", json={"role": "admin"}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_update_user_password_takes_effect(client, admin_headers):
    r = client.post(
        "/api/users/",
        json={"username": "carol", "password": "oldpass1", "role": "user"},
        headers=admin_headers,
    )
    user_id = r.json()["id"]

    # Old password works
    r = client.post("/auth/login", json={"username": "carol", "password": "oldpass1"})
    assert r.status_code == 200

    # Change password
    r = client.patch(f"/api/users/{user_id}", json={"password": "newpass1"}, headers=admin_headers)
    assert r.status_code == 200

    # Old password no longer works
    r = client.post("/auth/login", json={"username": "carol", "password": "oldpass1"})
    assert r.status_code == 401

    # New password works
    r = client.post("/auth/login", json={"username": "carol", "password": "newpass1"})
    assert r.status_code == 200


def test_deactivate_user_blocks_login(client, admin_headers):
    r = client.post(
        "/api/users/",
        json={"username": "dave", "password": "pass1234", "role": "user"},
        headers=admin_headers,
    )
    user_id = r.json()["id"]

    # Works while active
    r = client.post("/auth/login", json={"username": "dave", "password": "pass1234"})
    assert r.status_code == 200

    # Deactivate
    r = client.patch(f"/api/users/{user_id}", json={"is_active": False}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    # Login now fails
    r = client.post("/auth/login", json={"username": "dave", "password": "pass1234"})
    assert r.status_code == 401


def test_delete_user(client, admin_headers):
    r = client.post(
        "/api/users/",
        json={"username": "erin", "password": "pass1234", "role": "user"},
        headers=admin_headers,
    )
    user_id = r.json()["id"]

    r = client.delete(f"/api/users/{user_id}", headers=admin_headers)
    assert r.status_code == 204

    r = client.get("/api/users/", headers=admin_headers)
    assert "erin" not in [u["username"] for u in r.json()]


def test_update_nonexistent_user(client, admin_headers):
    r = client.patch("/api/users/99999", json={"role": "admin"}, headers=admin_headers)
    assert r.status_code == 404


def test_delete_nonexistent_user(client, admin_headers):
    r = client.delete("/api/users/99999", headers=admin_headers)
    assert r.status_code == 404


# ── Audit trail produced by user management ───────────────────────────────────

def test_create_user_writes_audit_entry(client, admin_headers):
    r = client.post(
        "/api/users/",
        json={"username": "audited", "password": "pass1234", "role": "user"},
        headers=admin_headers,
    )
    user_id = r.json()["id"]

    r = client.get("/api/audit/?entity_type=user&action=create", headers=admin_headers)
    assert r.status_code == 200
    entries = r.json()
    matching = [e for e in entries if e["entity_id"] == user_id]
    assert len(matching) == 1
    assert matching[0]["user_login"] == "admin"
    assert "audited" in matching[0]["details"]


def test_delete_user_writes_audit_entry(client, admin_headers):
    r = client.post(
        "/api/users/",
        json={"username": "todelete", "password": "pass1234", "role": "user"},
        headers=admin_headers,
    )
    user_id = r.json()["id"]

    client.delete(f"/api/users/{user_id}", headers=admin_headers)

    r = client.get("/api/audit/?entity_type=user&action=delete", headers=admin_headers)
    matching = [e for e in r.json() if e["entity_id"] == user_id]
    assert len(matching) == 1
    assert "todelete" in matching[0]["details"]
