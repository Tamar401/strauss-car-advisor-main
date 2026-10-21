"""תיקון נתונים מכרטיס הפרופיל (דרישה בהנחיות): ולידציה כמו בכלי, חישוב מחדש, והסוכן יודע."""
from fastapi.testclient import TestClient

from app.contracts import OptionRequest
from app.main import app

client = TestClient(app)


def demo_conversation(isolated, with_alternative=True):
    cid = client.post("/api/conversations/new/demo/E-001").json()["conversation_id"]
    if with_alternative:
        record = isolated.get(cid)
        record.alternatives = [OptionRequest(kind="car", car_id="CAR-10")]
        isolated.save(record)
    return cid


def test_correction_updates_profile_and_recomputes(isolated):
    cid = demo_conversation(isolated)
    state = client.patch(f"/api/conversations/{cid}/profile", json={"fields": {"base_salary": 20000}}).json()
    assert state["profile"]["base_salary"]["value"] == 20000
    assert state["profile"]["base_salary"]["source"] == "employee"
    note, update = state["messages"][-2], state["messages"][-1]
    assert note["role"] == "system" and "שכר הבסיס" in note["text"]
    assert update["comparison"]["current"]["gross"] == 20000
    # הסוכן יראה את התיקון בהיסטוריה
    assert "תיקן/ה בכרטיס הפרופיל" in str(isolated.get(cid).history)


def test_correct_current_participation(isolated):
    cid = demo_conversation(isolated)
    state = client.patch(f"/api/conversations/{cid}/profile", json={"current_participation": 450}).json()
    assert state["profile"]["current_option"]["value"]["participation"]["value"] == 450
    assert state["messages"][-1]["comparison"]["current"]["employee_participation"] == 450


def test_correction_without_alternatives_just_saves(isolated):
    cid = demo_conversation(isolated, with_alternative=False)
    state = client.patch(f"/api/conversations/{cid}/profile", json={"fields": {"credit_points": 3}}).json()
    assert state["profile"]["credit_points"]["value"] == 3
    assert state["messages"][-1]["role"] == "system"


def test_new_conversation_reuses_employee_profile(isolated, monkeypatch):
    cid = demo_conversation(isolated, with_alternative=False)
    updated = client.patch(
        f"/api/conversations/{cid}/profile",
        json={"fields": {"base_salary": 23456}},
    ).json()
    assert updated["profile"]["base_salary"]["value"] == 23456

    # Background updates (for example, a representative identifying the current car) use Store.save.
    record = isolated.get(cid)
    record.state.profile.base_salary.value = 24567
    isolated.save(record)

    monkeypatch.setattr("app.api.chat.handle_message", lambda record, message, store: record)
    new_state = client.post("/api/chat", json={"message": "שיחה חדשה"}).json()

    assert new_state["conversation_id"] != cid
    assert new_state["profile"]["base_salary"]["value"] == 24567
    assert new_state["profile"]["occupation"] == updated["profile"]["occupation"]


def test_correction_uses_the_same_validation_as_the_agent(isolated):
    cid = demo_conversation(isolated)
    assert client.patch(f"/api/conversations/{cid}/profile", json={"fields": {"occupation": "אסטרונאוט/ית"}}).status_code == 400
    assert client.patch(f"/api/conversations/{cid}/profile", json={"fields": {"pension_pct": 80}}).status_code == 400
    assert client.patch(f"/api/conversations/{cid}/profile", json={"fields": {"national_id": "1"}}).status_code == 400
    assert client.patch(f"/api/conversations/{cid}/profile", json={"current_participation": -5}).status_code == 400
    assert client.patch(f"/api/conversations/{cid}/profile", json={}).status_code == 400


def test_occupation_correction_changes_the_group(isolated):
    cid = demo_conversation(isolated)
    state = client.patch(f"/api/conversations/{cid}/profile", json={"fields": {"occupation": "מנהל/ת חטיבה"}}).json()
    assert state["messages"][-1]["comparison"]["current"]["budget"] == 5200  # קבוצה ד
