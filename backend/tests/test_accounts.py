"""Authentication, role permissions, registration and rep invitations, and account isolation."""
import hashlib
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.auth import get_current_user, hash_password, require_representative
from app.contracts import RepQuestion
from app.main import app

client = TestClient(app)
ADMIN_EMAIL = "admin@example.test"
ADMIN_PASSWORD = "admin-password-123"


def auth_headers(session):
    return {"Authorization": "Bearer " + session["access_token"]}


def admin_session(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", ADMIN_EMAIL)
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN_PASSWORD)
    app.dependency_overrides.pop(get_current_user, None)
    response = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "role": "admin"},
    )
    assert response.status_code == 200
    return response.json()


def test_admin_login_reports_missing_server_configuration(monkeypatch, isolated):
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    response = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "role": "admin"},
    )
    assert response.status_code == 503
    assert "ADMIN_USERNAME" in response.json()["detail"]


def test_admin_login_rejects_invalid_server_username_configuration(monkeypatch, isolated):
    monkeypatch.setenv("ADMIN_USERNAME", "administrator")
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN_PASSWORD)
    response = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "role": "admin"},
    )
    assert response.status_code == 503
    assert "email" in response.json()["detail"]


def invite(headers, email="rep@example.test", full_name="Rep Person"):
    return client.post("/api/auth/invitations", headers=headers, json={"email": email, "full_name": full_name})


def register_rep(email, code, password="account-password-12"):
    return client.post(
        "/api/auth/representatives/register",
        json={"email": email, "code": code, "password": password},
    )


def register_employee(email="employee@example.test", full_name="Employee Person"):
    return client.post(
        "/api/auth/employees/register",
        json={"email": email, "password": "account-password-12", "full_name": full_name},
    )


def rep_account(monkeypatch, email="rep@example.test"):
    admin = auth_headers(admin_session(monkeypatch))
    registered = register_rep(email, invite(admin, email).json()["code"])
    assert registered.status_code == 201
    return registered.json()


def test_employee_registers_without_code(isolated):
    assert client.post(
        "/api/auth/employees/register",
        json={"email": "missing-name@example.test", "password": "account-password-12"},
    ).status_code == 422
    assert client.post(
        "/api/auth/employees/register",
        json={"email": "blank@example.test", "password": "account-password-12", "full_name": "   "},
    ).status_code == 422
    registered = register_employee()
    assert registered.status_code == 201
    assert registered.json()["user"]["role"] == "employee"
    assert registered.json()["user"]["full_name"] == "Employee Person"
    assert isolated.user_by_email("employee@example.test")["password_hash"] != "account-password-12"
    login = client.post("/api/auth/login", json={"email": "EMPLOYEE@example.test", "password": "account-password-12"})
    assert login.status_code == 200 and login.json()["user"]["role"] == "employee"
    assert register_employee().status_code == 409
    assert client.post(
        "/api/auth/employees/register",
        json={"email": "boss@example.test", "password": "account-password-12", "full_name": "Boss", "role": "admin"},
    ).status_code == 422


def test_admin_invites_rep_who_registers_with_code(monkeypatch, isolated):
    admin = auth_headers(admin_session(monkeypatch))
    issued = invite(admin, "new.rep@example.test", "New Rep")
    assert issued.status_code == 201
    code = issued.json()["code"]
    assert len(code) == 5 and code.isdigit()
    saved = isolated.user_by_email("new.rep@example.test")
    assert saved["role"] == "rep" and saved["password_hash"] == "pending"
    assert saved["password_setup_hash"] == hashlib.sha256(code.encode("ascii")).hexdigest()
    assert client.post(
        "/api/auth/login", json={"email": "new.rep@example.test", "password": "account-password-12"},
    ).status_code == 401

    assert register_rep("other@example.test", code).status_code == 401
    registered = register_rep("NEW.REP@example.test", code)
    assert registered.status_code == 201
    assert registered.json()["user"]["role"] == "rep"
    assert registered.json()["user"]["full_name"] == "New Rep"
    login = client.post("/api/auth/login", json={"email": "new.rep@example.test", "password": "account-password-12"})
    assert login.status_code == 200 and login.json()["user"]["role"] == "rep"
    assert register_rep("new.rep@example.test", code, "another-password-12").status_code == 401  # חד-פעמי
    assert invite(admin, "new.rep@example.test").status_code == 409


def test_reinvite_replaces_code(monkeypatch, isolated):
    admin = auth_headers(admin_session(monkeypatch))
    first = invite(admin, "pending.rep@example.test").json()["code"]
    second = invite(admin, "pending.rep@example.test").json()["code"]
    if first != second:
        assert register_rep("pending.rep@example.test", first).status_code == 401
    assert register_rep("pending.rep@example.test", second).status_code == 201


def test_employee_cannot_become_rep_with_invitation(monkeypatch, isolated):
    admin = auth_headers(admin_session(monkeypatch))
    register_employee("worker@example.test")
    assert invite(admin, "worker@example.test").status_code == 409


def test_expired_code_is_rejected(isolated):
    code = "54321"
    assert isolated.create_invitation(
        "expired-user", "expired@example.test", "rep",
        hashlib.sha256(code.encode("ascii")).hexdigest(), "2000-01-01T00:00:00+00:00", "Expired",
    ) == "created"
    assert register_rep("expired@example.test", code).status_code == 401


def test_rep_registration_attempts_are_rate_limited(isolated):
    code = "54321"
    isolated.create_invitation(
        "limited-user", "limited@example.test", "rep",
        hashlib.sha256(code.encode("ascii")).hexdigest(), "2999-01-01T00:00:00+00:00", "Limited",
    )
    for _ in range(10):
        assert register_rep("limited@example.test", "12345").status_code == 401
    assert register_rep("limited@example.test", code).status_code == 429


def test_demo_rep_is_created_at_startup(monkeypatch, isolated):
    """חשבון נציג/ה להדגמה נוצר בכל עלייה — הנתונים ב-Render נמחקים בכל פריסה."""
    monkeypatch.setenv("DEMO_REP_EMAIL", "Demo.Rep@example.test")
    monkeypatch.setenv("DEMO_REP_PASSWORD", "demo-rep-password")
    with TestClient(app):
        pass
    login = client.post("/api/auth/login", json={"email": "demo.rep@example.test", "password": "demo-rep-password"})
    assert login.status_code == 200 and login.json()["user"]["role"] == "rep"


def test_demo_rep_skipped_when_misconfigured(monkeypatch, isolated):
    monkeypatch.setenv("DEMO_REP_EMAIL", "not-an-email")
    monkeypatch.setenv("DEMO_REP_PASSWORD", "demo-rep-password")
    with TestClient(app):  # השרת עולה גם עם הגדרה שגויה
        pass
    monkeypatch.setenv("DEMO_REP_EMAIL", "short@example.test")
    monkeypatch.setenv("DEMO_REP_PASSWORD", "short")
    with TestClient(app):
        pass
    assert isolated.user_by_email("short@example.test") is None


def test_only_admin_can_invite_and_change_rules(monkeypatch, isolated):
    admin_session(monkeypatch)
    employee = register_employee("rules-employee@example.test").json()
    rep = rep_account(monkeypatch, "rules-rep@example.test")
    assert invite({}, "blocked@example.test").status_code == 401
    for session in (employee, rep):
        assert invite(auth_headers(session), "blocked@example.test").status_code == 403
        assert client.post("/api/rules/preview", headers=auth_headers(session), json={"rules": {}}).status_code == 403
    assert isolated.user_by_email("blocked@example.test") is None


def test_employee_conversations_remain_private(isolated):
    app.dependency_overrides.pop(get_current_user, None)
    first = register_employee("first@example.test").json()
    second = register_employee("second@example.test").json()
    first_headers = auth_headers(first)
    second_headers = auth_headers(second)
    created = client.post("/api/conversations/new/demo/E-001", headers=first_headers)
    assert created.status_code == 200
    conversation_id = created.json()["conversation_id"]
    assert client.get(f"/api/conversations/{conversation_id}", headers=first_headers).status_code == 200
    assert client.get(f"/api/conversations/{conversation_id}", headers=second_headers).status_code == 404
    assert client.post(
        "/api/chat",
        headers=second_headers,
        json={"conversation_id": conversation_id, "message": "read another account"},
    ).status_code == 404


def test_representatives_share_open_queue_but_only_see_their_answers(isolated):
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_representative, None)
    now = datetime.now(timezone.utc)
    for question_id in ("question-1", "question-2"):
        isolated.save_question(RepQuestion(
            id=question_id,
            conversation_id=f"conversation-{question_id}",
            employee_display_name="Employee",
            field="participation:CAR-10",
            question_text=f"Question {question_id}",
            context="Test context",
            status="open",
            created_at=now,
        ))
    credentials = []
    for index in (1, 2):
        email = f"rep{index}@example.test"
        password = f"representative-password-{index}"
        assert isolated.create_account(f"rep-{index}", email, hash_password(password), "rep")
        credentials.append(client.post("/api/auth/login", json={"email": email, "password": password}))
    assert all(response.status_code == 200 and response.json()["user"]["role"] == "rep" for response in credentials)
    headers = [auth_headers(response.json()) for response in credentials]
    answered = client.post(
        "/api/rep/questions/question-1/answer",
        headers=headers[0],
        json={"value": 275},
    )
    assert answered.status_code == 200
    first_questions = client.get("/api/rep/questions", headers=headers[0]).json()
    second_questions = client.get("/api/rep/questions", headers=headers[1]).json()
    assert {question["id"] for question in first_questions} == {"question-1", "question-2"}
    assert {question["id"] for question in second_questions} == {"question-2"}
    assert client.get("/api/rep/questions?status=answered", headers=headers[1]).json() == []
