"""החולשות שתוקנו: רכב של היום מכל המאגר, זיהוי ע״י הנציג, הרשאות, Number Guard מחמיר, מחיקת שיחות ישנות."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import seed
from app.agent import tools
from app.agent.number_guard import allowed_numbers, check, tokens
from app.contracts import CompareRequest, ConversationState, EmployeeProfile, OptionRequest, Tracked
from app.engine import vou
from app.engine.compare import compare, demo_profile
from app.engine.rules import load_rules
from app.main import app
from app.store import ConversationRecord

client = TestClient(app)
EMPLOYEES = {e["id"]: e for e in seed.employees()}
TANG = "2026/2025/2/01014/00003"  # אותו יצרן+דגם כמו ATTO 3, סוג רכב אחר — שווי שימוש 6,950


def demo_record(employee_id="E-001") -> ConversationRecord:
    return ConversationRecord(state=ConversationState(
        conversation_id="c1", status="collecting", messages=[], profile=demo_profile(EMPLOYEES[employee_id])
    ))


# ---------- 1. הרכב של היום — מכל המאגר ----------


def test_find_vehicle_returns_all_trims_and_never_picks(isolated):
    result = tools.find_vehicle(demo_record(), isolated, "COROLLA", 2021)
    values = {c["value_of_use"] for c in result["candidates"]}
    assert len(values) > 1  # כמה רמות גימור עם שווי שימוש שונה
    assert "hint" in result
    assert all("vou_key" in c and "trim" in c for c in result["candidates"])


def test_find_vehicle_by_model_code_needs_the_manufacturer():
    """קוד דגם ייחודי רק בתוך יצרן: '00003' קיים אצל יצרנים רבים."""
    _, alone = vou.search("00003", 2025)
    rows, _ = vou.search("בי ווי די 00003", 2025)
    assert alone > 2
    assert {r["commercial_name"] for r in rows} == {"ATTO 3", "TANG"}


def test_current_car_from_full_database_uses_its_value_of_use(isolated):
    record = demo_record()
    tools.set_current_situation(record, isolated, kind="car", vou_key=TANG, participation=300)
    resp = compare(CompareRequest(profile=record.state.profile, alternatives=[OptionRequest(kind="car", car_id="CAR-10")]))
    assert resp.current.status == "complete"
    assert resp.current.value_of_use == 6950
    assert resp.current.drive == "electric"
    assert "TANG" in resp.current.label
    assert next(t for t in resp.current.trace if t.key == "value_of_use").source.endswith(TANG)


def test_car_outside_catalog_cannot_be_an_alternative():
    p = demo_profile(EMPLOYEES["E-001"])
    alt = compare(CompareRequest(profile=p, alternatives=[OptionRequest(kind="car", vou_key=vou.parse_key(TANG))])).alternatives[0]
    assert alt.status == "blocked"
    assert alt.eligibility.reason_code == "not_in_catalog"


def test_bad_vou_key_is_a_tool_error(isolated):
    with pytest.raises(tools.ToolError):
        tools.set_current_situation(demo_record(), isolated, kind="car", vou_key="2026/1999/1/99999/99999")


def test_unidentified_car_waits_for_rep_then_completes(llm, isolated):
    llm.script = [
        [("update_profile", {"name": "נועה", "occupation": "מנהל/ת מוצר", "base_salary": 18500, "commissions": 0, "bonus": 0,
                             "pension_pct": 6, "study_fund_pct": 2.5, "credit_points": 2.75})],
        [("set_current_situation", {"kind": "car", "vehicle_description": "טויוטה קורולה 2021", "participation": 300})],
        [("compare_options", {"options": [{"kind": "car", "car_id": "CAR-10", "participation": 300}]})],
        [("ask_rep", {"about": "current_vehicle", "question_text": "איזו קורולה 2021 יש לנועה?"})],
        "יש כמה גרסאות של קורולה 2021, שאלתי את הנציג איזו בדיוק יש לך.",
    ]
    state = client.post("/api/chat", json={"message": "יש לי קורולה 2021, משתתפת 300"}).json()
    assert state["status"] == "waiting_for_rep"
    meanwhile = state["messages"][-1]["comparison"]
    assert meanwhile["current"]["missing"] == ["current_vehicle"]

    q = client.get("/api/rep/questions", params={"status": "open"}).json()[0]
    assert q["field"] == "current_vehicle"
    assert client.post(f"/api/rep/questions/{q['id']}/answer", json={"value": "not-a-key"}).status_code == 400

    key = vou.key_text(vou.key_of(vou.search("COROLLA", 2021)[0][0]))
    assert client.post(f"/api/rep/questions/{q['id']}/answer", json={"value": key}).status_code == 200
    resumed = client.get(f"/api/conversations/{state['conversation_id']}").json()
    assert resumed["status"] == "ready"
    assert "זיהיתי את הרכב שלך" in resumed["messages"][-1]["text"]
    current = resumed["messages"][-1]["comparison"]["current"]
    assert current["status"] == "complete"
    assert current["employee_participation"] == 300  # ההשתתפות שהעובדת מסרה לא אבדה


# ---------- 3. הרשאות ----------


@pytest.fixture
def codes(monkeypatch):
    monkeypatch.setenv("REP_ACCESS_CODE", "rep-code")
    monkeypatch.setenv("ADMIN_ACCESS_CODE", "admin-code")


def test_rep_screen_requires_code(codes):
    assert client.get("/api/rep/questions").status_code == 401
    assert client.get("/api/rep/questions", headers={"X-Access-Code": "wrong"}).status_code == 401
    assert client.get("/api/rep/questions", headers={"X-Access-Code": "rep-code"}).status_code == 200
    assert client.get("/api/rep/questions", headers={"X-Access-Code": "admin-code"}).status_code == 200  # מנהל/ת יכול/ה לענות


def test_rules_editing_requires_admin_code(codes):
    raw = client.get("/api/rules").json()  # קריאה פתוחה
    assert client.post("/api/rules/preview", json={"rules": raw}).status_code == 401
    assert client.post("/api/rules/preview", json={"rules": raw}, headers={"X-Access-Code": "rep-code"}).status_code == 401
    assert client.post("/api/rules/preview", json={"rules": raw}, headers={"X-Access-Code": "admin-code"}).status_code == 200


def test_vehicle_search_requires_rep_code(codes):
    assert client.get("/api/vehicles/search", params={"q": "COROLLA"}).status_code == 401
    ok = client.get("/api/vehicles/search", params={"q": "COROLLA", "year": 2021}, headers={"X-Access-Code": "rep-code"})
    assert ok.json()["total"] > 1


def test_access_check_endpoint(codes):
    assert client.get("/api/auth/check/admin", headers={"X-Access-Code": "admin-code"}).status_code == 200
    assert client.get("/api/auth/check/admin", headers={"X-Access-Code": "rep-code"}).status_code == 401


def test_employee_screens_stay_open(codes):
    assert client.post("/api/conversations/new/demo/E-001").status_code == 200


# ---------- 5. Number Guard מחמיר ----------


def test_token_kinds():
    assert tokens("נטו 11,032 ₪, פנסיה 6%, דגם EV3, שנת 2025") == [(11032, "money"), (6, "percent"), (3, "bare"), (2025, "bare")]


def test_money_needs_a_source_even_if_small():
    assert check("תוספת של 5 ₪", set()) == [5]
    assert check("יש לך 3 ילדים, רכב משנת 2021", set()) == []


def test_catalog_prices_are_not_allowed_unless_a_tool_returned_them():
    record = demo_record()
    rules = load_rules()
    assert check("מחיר מחירון 319,900 ₪", allowed_numbers(record, rules, [])) == [319900]
    record.history = [{"role": "user", "parts": [{"function_response": {"name": "list_catalog", "response": {"list_price": 319900}}}]}]
    assert check("מחיר מחירון 319,900 ₪", allowed_numbers(record, rules, [])) == []


# ---------- 2 + 7. שמירה ומחיקה ----------


def test_old_conversations_are_purged(isolated):
    record = demo_record()
    isolated.save(record)
    old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    with isolated._con:
        isolated._con.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (old, "c1"))
    assert isolated.purge_older_than(30) == 1
    assert isolated.get("c1") is None
