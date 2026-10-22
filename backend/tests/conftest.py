"""בכל בדיקה: DB זמני ומודל מתוסרט. הבדיקות אף פעם לא פונות לרשת ולא נוגעות ב-data/app.db.

TEST_DATABASE_URL מריץ את אותן בדיקות מול PostgreSQL (DB ריק שנועד לבדיקות — הטבלאות מתרוקנות בכל בדיקה).
"""
import os

import pytest
from google.genai import types

from app.agent import orchestrator
from app.auth import AuthenticatedUser, get_current_user, require_representative
from app.main import app
from app.store import Store, use_store

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
TABLES = (
    "auth_sessions, conversations, employee_profiles, rep_questions, users, "
    "employee_setup_attempts, representative_activation_codes"
)


def make_store(tmp_path) -> Store:
    """אותו DB בכל קריאה בתוך בדיקה — כמו הפעלה מחדש של השרת."""
    return Store(tmp_path / "app.db", url=TEST_DATABASE_URL)


class ScriptedLLM:
    """מחזיר תשובות מוכנות מראש, לפי הסדר. כל פריט: טקסט, או רשימת (שם כלי, ארגומנטים)."""

    def __init__(self, script=()):
        self.script = list(script)
        self.calls = []

    def generate(self, history, system):
        self.calls.append({"history": list(history), "system": system})  # תמונת מצב — הרשימה ממשיכה לגדול
        if not self.script:
            raise AssertionError("המודל המתוסרט נקרא יותר פעמים מהצפוי")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, str):
            return types.Content(role="model", parts=[types.Part(text=item)])
        return types.Content(
            role="model",
            parts=[types.Part(function_call=types.FunctionCall(name=name, args=args)) for name, args in item],
        )


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    # מצב פתוח כברירת מחדל בבדיקות, בלי קשר ל-.env; בדיקות ההרשאות מגדירות קודים בעצמן
    monkeypatch.delenv("REP_ACCESS_CODE", raising=False)
    monkeypatch.delenv("ADMIN_ACCESS_CODE", raising=False)
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    store = make_store(tmp_path)
    if TEST_DATABASE_URL:
        store._con.execute(f"TRUNCATE {TABLES}")
    use_store(store)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id="test-employee", email="employee@example.test",
    )
    app.dependency_overrides[require_representative] = lambda: AuthenticatedUser(
        id="test-rep", email="representative@example.test", role="rep",
    )
    llm = ScriptedLLM()
    orchestrator.use_llm(llm)
    yield store
    orchestrator.use_llm(None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_representative, None)


@pytest.fixture
def llm():
    llm = ScriptedLLM()
    orchestrator.use_llm(llm)
    return llm
