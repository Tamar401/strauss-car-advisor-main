"""סקירת "כל האפשרויות" ומסך הכללים: תצוגת השפעה, שמירה, ביטול — על עותק זמני של קובץ הכללים."""
import json
import shutil

import pytest
from fastapi.testclient import TestClient

from app import seed
from app.main import app

client = TestClient(app)


@pytest.fixture
def rules_copy(tmp_path, monkeypatch):
    path = tmp_path / "strauss-rules.json"
    shutil.copy(seed.RULES_PATH, path)
    monkeypatch.setattr(seed, "RULES_PATH", path)
    return path


def raw_rules():
    return client.get("/api/rules").json()


# ---------- כל האפשרויות ----------


def test_explore_needs_complete_profile(llm):
    llm.script = ["באיזה עיסוק את/ה?"]
    cid = client.post("/api/chat", json={"message": "שלום"}).json()["conversation_id"]
    r = client.post(f"/api/conversations/{cid}/explore")
    assert r.status_code == 409
    assert "חסר לי" in r.json()["detail"]


def test_explore_lists_all_options_sorted():
    cid = client.post("/api/conversations/new/demo/E-001").json()["conversation_id"]
    state = client.post(f"/api/conversations/{cid}/explore").json()
    comparison = state["messages"][-1]["comparison"]
    alts = comparison["alternatives"]
    assert len(alts) == 20  # 19 רכבים (בלי הרכב של היום) + ויתור
    complete = [a for a in alts if a["status"] == "complete"]
    assert [a["delta_net"] for a in complete] == sorted((a["delta_net"] for a in complete), reverse=True)
    assert complete[0]["option"]["kind"] == "waiver"  # לנועה: ויתור הכי משתלם (+3,199)
    assert "הכי משתלמת" in state["messages"][-1]["text"]


def test_explore_uses_known_participation_and_keeps_tracked_alternatives(isolated):
    cid = client.post("/api/conversations/new/demo/E-001").json()["conversation_id"]
    record = isolated.get(cid)
    from app.contracts import OptionRequest, Tracked

    record.participations["CAR-10"] = Tracked(value=350, source="rep")
    record.alternatives = [OptionRequest(kind="car", car_id="CAR-10")]
    isolated.save(record)

    state = client.post(f"/api/conversations/{cid}/explore").json()
    atto3 = next(a for a in state["messages"][-1]["comparison"]["alternatives"] if a["option"]["car_id"] == "CAR-10")
    assert atto3["employee_participation"] == 350
    assert [a.car_id for a in isolated.get(cid).alternatives] == ["CAR-10"]  # הסקירה לא דרסה


# ---------- כללים: תצוגת השפעה ----------


def test_preview_without_changes_changes_nothing(rules_copy):
    impact = client.post("/api/rules/preview", json={"rules": raw_rules()}).json()["impact"]
    assert len(impact) == 6
    assert not any(row["changed"] for row in impact)
    assert next(r for r in impact if r["employee_id"] == "E-001")["delta"] == 661


def test_preview_budget_change_affects_only_family_track(rules_copy):
    raw = raw_rules()
    raw["budgets"]["ב"] = 6000  # מכסה את הקרניבל של דוד כהן (קבוצה ב)
    impact = {r["employee_id"]: r for r in client.post("/api/rules/preview", json={"rules": raw}).json()["impact"]}
    assert impact["E-002"]["changed"]
    assert impact["E-002"]["delta"] - impact["E-002"]["before"]["delta"] == 1150  # חלקו בפער נעלם
    assert not impact["E-001"]["changed"]


def test_preview_electric_bonus_change(rules_copy):
    raw = raw_rules()
    raw["electric"]["netBonus"] = 400
    impact = {r["employee_id"]: r for r in client.post("/api/rules/preview", json={"rules": raw}).json()["impact"]}
    assert impact["E-001"]["delta"] - impact["E-001"]["before"]["delta"] == 150


def test_preview_rejects_invalid_rules_with_hebrew_message(rules_copy):
    raw = raw_rules()
    del raw["budgets"]["ד"]
    r = client.post("/api/rules/preview", json={"rules": raw})
    assert r.status_code == 422
    assert r.json()["detail"]["message"] == "קובץ הכללים לא תקין"


# ---------- כללים: שמירה וביטול ----------


def test_save_applies_immediately_and_undo_restores(rules_copy):
    raw = raw_rules()
    raw["version"] = "test-v2"
    raw["electric"]["netBonus"] = 400
    assert client.put("/api/rules", json={"rules": raw}).json()["saved"]
    assert json.loads(rules_copy.read_text(encoding="utf-8"))["version"] == "test-v2"
    after = client.get("/api/demo/compare/E-001").json()
    assert after["rules_version"] == "test-v2"  # המנוע קורא את הקובץ החדש בלי הפעלה מחדש

    assert client.post("/api/rules/undo").json()["version"] == "mock-2026-10-12"
    assert client.post("/api/rules/undo").status_code == 404  # אין עוד גרסה קודמת


def test_save_rejects_invalid_and_keeps_file(rules_copy):
    before = rules_copy.read_text(encoding="utf-8")
    raw = raw_rules()
    raw["netMethod"]["brackets"][0][0] = 99999
    assert client.put("/api/rules", json={"rules": raw}).status_code == 422
    assert rules_copy.read_text(encoding="utf-8") == before
