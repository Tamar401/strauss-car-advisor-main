from fastapi.testclient import TestClient

from app.agent.payslip import PayslipFields, extract_payslip
from app.auth import get_current_user, hash_password
from app.main import app

client = TestClient(app)


def test_payslip_extraction_requires_vertex_or_explicit_paid_api_approval(monkeypatch):
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    monkeypatch.delenv("PAYSLIP_ALLOW_GEMINI_API", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    try:
        extract_payslip(b"%PDF-1.4", "application/pdf")
    except RuntimeError as exc:
        assert "Vertex AI" in str(exc)
    else:
        raise AssertionError("Payslip processing must be disabled without an approved provider")


def test_payslip_fields_require_review_before_being_saved(monkeypatch, isolated):
    received = {}

    def extract(data, mime_type):
        received["data"] = data
        received["mime_type"] = mime_type
        return PayslipFields(
            base_salary=14200,
            commissions=1000,
            pension_pct=6,
            study_fund_pct=2.5,
            credit_points=2.25,
        )

    monkeypatch.setattr("app.api.payslip.extract_payslip", extract)
    document = b"%PDF-1.7\nprivate-payslip-content"
    response = client.post(
        "/api/payslip/extract",
        files={"file": ("payslip.pdf", document, "application/pdf")},
        data={"consent": "true"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["fields"]["base_salary"] == 14200
    assert received == {"data": document, "mime_type": "application/pdf"}
    record = isolated.get_owned(result["conversation_id"], "test-employee")
    assert record.state.profile.base_salary.value is None
    assert "private-payslip-content" not in record.model_dump_json()

    confirmed = client.post(
        f"/api/conversations/{result['conversation_id']}/payslip/confirm",
        json={"fields": {"base_salary": 14200, "pension_pct": 6}},
    )
    assert confirmed.status_code == 200
    profile = confirmed.json()["profile"]
    assert profile["base_salary"] == {
        "value": 14200,
        "source": "payslip",
        "confirmed": True,
        "note": None,
    }
    assert profile["pension_pct"]["source"] == "payslip"
    assert profile["commissions"]["value"] is None


def test_payslip_upload_rejects_unsupported_and_mismatched_files(monkeypatch):
    called = False

    def extract(*_args):
        nonlocal called
        called = True
        return PayslipFields()

    monkeypatch.setattr("app.api.payslip.extract_payslip", extract)
    unsupported = client.post(
        "/api/payslip/extract",
        files={"file": ("payslip.txt", b"text", "text/plain")},
        data={"consent": "true"},
    )
    mismatched = client.post(
        "/api/payslip/extract",
        files={"file": ("payslip.pdf", b"not a PDF", "application/pdf")},
        data={"consent": "true"},
    )
    assert unsupported.status_code == 415
    assert mismatched.status_code == 415
    assert not called


def test_payslip_upload_requires_consent():
    response = client.post(
        "/api/payslip/extract",
        files={"file": ("payslip.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert response.status_code == 400


def test_payslip_confirmation_rejects_unapproved_fields(isolated):
    app.dependency_overrides.pop(get_current_user, None)
    assert isolated.create_account(
        "payslip-employee", "payslip.employee@example.test", hash_password("employee-password-12"), "employee",
    )
    registered = client.post(
        "/api/auth/login",
        json={"email": "payslip.employee@example.test", "password": "employee-password-12"},
    ).json()
    conversation = client.post(
        "/api/conversations/new/demo/E-001",
        headers={"Authorization": f"Bearer {registered['access_token']}"},
    ).json()
    response = client.post(
        f"/api/conversations/{conversation['conversation_id']}/payslip/confirm",
        headers={"Authorization": f"Bearer {registered['access_token']}"},
        json={"fields": {"national_id": 123}},
    )
    assert response.status_code == 400