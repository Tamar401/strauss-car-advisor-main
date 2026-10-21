"""Authentication, role permissions, representative activation, and account isolation."""
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
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()


def register_employee(email="employee@example.test", full_name="Employee Person"):
    return client.post(
        "/api/auth/employees/register",
        json={
            "email": email,
            "password": "employee-password-12",
            "full_name": full_name,
        },
    )


def representative_activation(admin_headers, email="rep@example.test"):
    return client.post(
        "/api/auth/representatives",
        headers=admin_headers,
        json={"email": email},
    )


def test_employee_registration_requires_details_and_assigns_employee_role(isolated):
    assert client.post(
        "/api/auth/employees/register",
        json={"email": "missing-name@example.test", "password": "employee-password-12"},
    ).status_code == 422
    assert client.post(
        "/api/auth/employees/register",
        json={
            "email": "blank-name@example.test",
            "password": "employee-password-12",
            "full_name": "   ",
        },
    ).status_code == 422

    registered = register_employee()
    assert registered.status_code == 201
    assert registered.json()["user"]["role"] == "employee"
    assert registered.json()["user"]["full_name"] == "Employee Person"
    saved = isolated.user_by_email("employee@example.test")
    assert saved["role"] == "employee"
    assert saved["password_hash"] != "employee-password-12"

    login = client.post(
        "/api/auth/login",
        json={"email": "EMPLOYEE@example.test", "password": "employee-password-12"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "employee"
    assert client.post(
        "/api/auth/employees/register",
        json={
            "email": "admin-attempt@example.test",
            "password": "employee-password-12",
            "full_name": "Attempted Admin",
            "role": "admin",
        },
    ).status_code == 422
    assert client.post("/api/auth/register", json={}).status_code == 404
    assert client.post("/api/auth/employees", json={}).status_code == 404
    assert isolated.user_by_email("admin-attempt@example.test") is None


def test_admin_issues_single_use_rep_activation_and_rep_logs_in(monkeypatch, isolated):
    admin = admin_session(monkeypatch)
    admin_headers = auth_headers(admin)
    assert representative_activation({}, "unauthorized@example.test").status_code == 401

    issued = representative_activation(admin_headers)
    assert issued.status_code == 201
    invitation = issued.json()
    assert invitation["email"] == "rep@example.test"
    code = invitation["registration_code"]
    assert len(code) >= 40
    stored_hash = isolated._con.execute(
        "SELECT code_hash FROM representative_activation_codes WHERE email = ?",
        ("rep@example.test",),
    ).fetchone()[0]
    assert stored_hash == hashlib.sha256(code.encode("ascii")).hexdigest()

    replacement = representative_activation(admin_headers).json()
    assert replacement["registration_code"] != code
    request = {
        "email": "rep@example.test",
        "password": "representative-password-12",
        "registration_code": code,
    }
    incorrect_email = {**request, "email": "other@example.test"}
    assert client.post("/api/auth/representatives/register", json=incorrect_email).status_code == 401
    assert client.post("/api/auth/representatives/register", json=request).status_code == 401
    request["registration_code"] = replacement["registration_code"]
    registered = client.post("/api/auth/representatives/register", json=request)
    assert registered.status_code == 201
    assert registered.json()["role"] == "rep"
    assert isolated._con.execute(
        "SELECT 1 FROM representative_activation_codes WHERE code_hash = ?",
        (stored_hash,),
    ).fetchone() is None
    assert client.post("/api/auth/representatives/register", json=request).status_code == 401

    login = client.post(
        "/api/auth/login",
        json={"email": request["email"], "password": request["password"]},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "rep"
    assert representative_activation(admin_headers, "rep@example.test").status_code == 409


def test_expired_representative_activation_is_rejected(monkeypatch, isolated):
    admin = admin_session(monkeypatch)
    activation = representative_activation(auth_headers(admin), "expired@example.test").json()
    code_hash = hashlib.sha256(activation["registration_code"].encode("ascii")).hexdigest()
    isolated._con.execute(
        "UPDATE representative_activation_codes SET expires_at = ? WHERE code_hash = ?",
        ("2000-01-01T00:00:00+00:00", code_hash),
    )
    assert client.post(
        "/api/auth/representatives/register",
        json={
            "email": activation["email"],
            "password": "representative-password-12",
            "registration_code": activation["registration_code"],
        },
    ).status_code == 401
    assert isolated.user_by_email("expired@example.test") is None


def test_legacy_employee_setup_codes_remain_rate_limited(isolated):
    email = "legacy-pending@example.test"
    setup_code = "54321"
    assert isolated.create_pending_employee(
        "legacy-pending-user",
        email,
        hashlib.sha256(setup_code.encode("ascii")).hexdigest(),
        full_name="Legacy Employee",
    )
    attempt = {
        "email": email,
        "setup_code": "12345",
        "password": "employee-password-12",
    }
    for _ in range(10):
        assert client.post("/api/auth/set-password", json=attempt).status_code == 401
    attempt["setup_code"] = setup_code
    assert client.post("/api/auth/set-password", json=attempt).status_code == 429


def test_admin_is_only_role_that_can_issue_rep_codes_and_change_rules(monkeypatch, isolated):
    admin = admin_session(monkeypatch)
    employee = register_employee().json()
    rep_invitation = representative_activation(auth_headers(admin), "rules-rep@example.test").json()
    rep_registration = client.post(
        "/api/auth/representatives/register",
        json={
            "email": rep_invitation["email"],
            "password": "representative-password-12",
            "registration_code": rep_invitation["registration_code"],
        },
    )
    assert rep_registration.status_code == 201
    rep_login = client.post(
        "/api/auth/login",
        json={"email": rep_invitation["email"], "password": "representative-password-12"},
    ).json()

    assert representative_activation(auth_headers(employee), "blocked@example.test").status_code == 403
    assert representative_activation(auth_headers(rep_login), "blocked@example.test").status_code == 403
    assert client.post(
        "/api/rules/preview",
        headers=auth_headers(employee),
        json={"rules": {}},
    ).status_code == 403
    assert client.post(
        "/api/rules/preview",
        headers=auth_headers(rep_login),
        json={"rules": {}},
    ).status_code == 403
    assert client.post(
        "/api/auth/employees",
        headers=auth_headers(admin),
        json={"email": "admin-created@example.test"},
    ).status_code == 404
    assert isolated.user_by_email("admin-created@example.test") is None


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
