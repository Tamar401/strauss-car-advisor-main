"""keep-alive: השרת פונה לעצמו כדי ש-Render החינמי לא יירדם — רק כשהוא רץ ב-Render."""
import time

import httpx
from fastapi.testclient import TestClient

from app import main


def _run_app(monkeypatch, env_url):
    pinged = []

    async def fake_get(self, url, **kwargs):
        pinged.append(url)
        return httpx.Response(200)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(main, "KEEP_ALIVE_SECONDS", 0.01)
    if env_url:
        monkeypatch.setenv("RENDER_EXTERNAL_URL", env_url)
    else:
        monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    with TestClient(main.app):
        time.sleep(0.2)
    return pinged


def test_pings_own_health_endpoint_on_render(monkeypatch):
    pinged = _run_app(monkeypatch, "https://api.example.onrender.com/")
    assert pinged and set(pinged) == {"https://api.example.onrender.com/api/health"}


def test_no_keep_alive_outside_render(monkeypatch):
    assert _run_app(monkeypatch, None) == []


def test_old_conversations_purged_daily_not_only_at_startup(monkeypatch, isolated):
    """השרת לא נרדם יותר, אז מחיקת שיחות ישנות (נתוני שכר) חייבת לרוץ גם בזמן ריצה."""
    calls = []
    monkeypatch.setattr(isolated, "purge_older_than", lambda days: calls.append(days) or 0)
    monkeypatch.setattr(main, "PURGE_SECONDS", 0.01)
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    with TestClient(main.app):
        time.sleep(0.2)
    assert len(calls) > 1  # פעם בעלייה, ושוב מהמשימה התקופתית
