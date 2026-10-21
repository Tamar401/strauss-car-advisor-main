from fastapi.testclient import TestClient

from app.main import PRODUCTION_FRONTEND_ORIGIN, _allowed_origins, app


def test_configured_origins_are_trimmed(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", " https://example.com/ , http://localhost:5173 ")

    assert _allowed_origins() == [
        "http://localhost:5173",
        "https://example.com",
        PRODUCTION_FRONTEND_ORIGIN,
    ]


def test_preflight_allows_production_frontend():
    response = TestClient(app).options(
        "/api/auth/representatives",
        headers={
            "Origin": PRODUCTION_FRONTEND_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == PRODUCTION_FRONTEND_ORIGIN


def test_preflight_rejects_unconfigured_origin():
    response = TestClient(app).options(
        "/api/auth/representatives",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
