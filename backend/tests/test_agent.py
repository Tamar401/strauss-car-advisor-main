"""הסוכן מקצה לקצה עם מודל מתוסרט: כלים, Number Guard, שאלה לנציג והמשך השיחה, שמירה ושחזור."""
from fastapi.testclient import TestClient
from google.genai import errors as genai_errors

from app.agent.number_guard import check, numbers_in
from app.agent.orchestrator import ERROR_TEXT, FALLBACK_TEXT
from app.main import app
from app.store import Store, use_store

client = TestClient(app)

# נועה לוי (E-001), כפי שהייתה מוסרת את הנתונים בשיחה
PROFILE_CALLS = [
    ("update_profile", {"name": "נועה", "occupation": "מנהל/ת מוצר", "base_salary": 18500, "commissions": 0, "bonus": 0,
                        "pension_pct": 6, "study_fund_pct": 2.5, "credit_points": 2.75}),
    ("set_current_situation", {"kind": "car", "car_id": "CAR-09", "participation": 300}),
]


def say(message, conversation_id=None):
    r = client.post("/api/chat", json={"conversation_id": conversation_id, "message": message})
    assert r.status_code == 200, r.text
    return r.json()


# ---------- זרימה מלאה: חסר מידע → נציג → המשך ----------


def test_missing_participation_goes_to_rep_and_conversation_resumes(llm):
    llm.script = [
        PROFILE_CALLS,
        [("ask_rep", {"car_id": "CAR-10", "question_text": "מה ההשתתפות ב-ATTO 3?"})],
        "חסר לי סכום ההשתתפות ב-ATTO 3, שאלתי את הנציג. בינתיים: הנטו שלך היום 11,032 ₪.",
    ]
    state = say("אני רוצה לעבור ל-ATTO 3")
    cid = state["conversation_id"]

    assert state["status"] == "waiting_for_rep"
    assert len(state["pending_questions"]) == 1
    meanwhile = state["messages"][-1]["comparison"]
    assert round(meanwhile["current"]["net"]) == 11032
    assert meanwhile["alternatives"][0]["status"] == "partial"

    q = client.get("/api/rep/questions", params={"status": "open"}).json()[0]
    assert q["employee_display_name"] == "נועה"
    assert "קבוצה ג" in q["context"]
    client.post(f"/api/rep/questions/{q['id']}/answer", json={"value": 300, "effective_from": "2027-01-01"})

    resumed = client.get(f"/api/conversations/{cid}").json()
    assert resumed["status"] == "ready"
    assert resumed["pending_questions"] == []
    update = resumed["messages"][-1]
    assert "עדכון מנציג התחבורה" in update["text"]
    alt = update["comparison"]["alternatives"][0]
    assert alt["status"] == "complete"
    assert alt["delta_display"] == 661  # נטו הייחוס של E-001
    assert next(t for t in alt["trace"] if t["key"] == "participation")["source"] == "נציג התחבורה"


def test_answered_question_cannot_be_answered_twice(llm):
    llm.script = [PROFILE_CALLS, [("ask_rep", {"car_id": "CAR-10", "question_text": "?"})], "שאלתי את הנציג."]
    say("ATTO 3")
    q = client.get("/api/rep/questions").json()[0]
    assert client.post(f"/api/rep/questions/{q['id']}/answer", json={"value": 300}).status_code == 200
    assert client.post(f"/api/rep/questions/{q['id']}/answer", json={"value": 999}).status_code == 409


def test_rep_rejects_negative_participation(llm):
    llm.script = [PROFILE_CALLS, [("ask_rep", {"car_id": "CAR-10", "question_text": "?"})], "שאלתי את הנציג."]
    say("ATTO 3")
    q = client.get("/api/rep/questions").json()[0]
    assert client.post(f"/api/rep/questions/{q['id']}/answer", json={"value": -50}).status_code == 400


def test_duplicate_rep_question_not_created(llm):
    ask = [("ask_rep", {"car_id": "CAR-10", "question_text": "?"})]
    llm.script = [PROFILE_CALLS, ask, ask, "שאלתי את הנציג."]
    say("ATTO 3")
    assert len(client.get("/api/rep/questions").json()) == 1


# ---------- השוואה ----------


def test_compare_attaches_comparison_and_skips_current_car(llm):
    llm.script = [
        PROFILE_CALLS,
        [("compare_options", {"options": [{"kind": "car", "car_id": "CAR-10", "participation": 300},
                                          {"kind": "car", "car_id": "CAR-09", "participation": 300}]})],
        "הנטו עולה ב-661 ₪ בחודש: מ-11,032 ל-11,693 ₪.",
    ]
    state = say("ATTO 3, ההשתתפות 300")
    assert state["status"] == "ready"
    comparison = state["messages"][-1]["comparison"]
    assert [a["option"]["car_id"] for a in comparison["alternatives"]] == ["CAR-10"]
    assert state["messages"][-1]["text"].startswith("הנטו עולה ב-661")


def test_tool_errors_are_returned_to_the_model_not_raised(llm):
    llm.script = [[("update_profile", {"occupation": "אסטרונאוט/ית"})], "באיזה עיסוק את/ה עובד/ת?"]
    state = say("אני אסטרונאוטית")
    response = llm.calls[1]["history"][-1].parts[0].function_response.response
    assert "עיסוק לא מוכר" in response["error"]
    assert state["messages"][-1]["text"] == "באיזה עיסוק את/ה עובד/ת?"


def test_profile_summary_is_in_the_prompt_every_turn(llm):
    llm.script = [PROFILE_CALLS, "קיבלתי.", "מה עוד?"]
    cid = say("הנתונים שלי")["conversation_id"]
    say("ומה עכשיו?", cid)
    assert '"base_salary": 18500' in llm.calls[-1]["system"]


# ---------- Number Guard ----------


def test_guard_blocks_invented_number_then_accepts_rewrite(llm, isolated):
    llm.script = [
        PROFILE_CALLS,
        "הנטו שלך יעלה בערך ב-9,999 ₪.",  # מספר מומצא
        "כדי לחשב את ההפרש אני צריך להריץ השוואה — לאיזה רכב?",
    ]
    state = say("כמה ארוויח?")
    assert state["messages"][-1]["text"].startswith("כדי לחשב")
    record = isolated.get(state["conversation_id"])
    assert record.guard_events[0]["unbacked"] == [9999.0]


def test_guard_falls_back_when_model_insists(llm):
    llm.script = [PROFILE_CALLS, "בערך 9,999 ₪.", "נו, בערך 8,888 ₪."]
    state = say("כמה ארוויח?")
    assert state["messages"][-1]["text"] == FALLBACK_TEXT


def test_number_parsing():
    assert numbers_in("נטו 11,032 ₪, פנסיה 2.5%, רכב MG4, הפרש -440") == [11032, 2.5, 4, 440]


def test_guard_allows_rounding_but_not_inventions():
    allowed = {11031.82, 250.0}
    assert check("הנטו 11,032 ₪ ועוד 250", allowed) == []
    assert check("הנטו 12,000 ₪", allowed) == [12000]


# ---------- עמידות ושמירה ----------


def test_llm_failure_keeps_conversation(llm, isolated):
    llm.script = [PROFILE_CALLS, "מה הרכב שלך היום?"]
    cid = say("שלום")["conversation_id"]
    llm.script = [genai_errors.APIError(503, {"error": {"message": "overloaded"}})]
    state = say("טוסון", cid)
    assert state["messages"][-1]["text"] == ERROR_TEXT
    assert state["profile"]["base_salary"]["value"] == 18500  # שום נתון לא אבד


def test_conversation_survives_server_restart(llm, isolated, tmp_path):
    llm.script = [PROFILE_CALLS, "קיבלתי."]
    cid = say("הנתונים שלי")["conversation_id"]
    use_store(Store(tmp_path / "app.db"))  # "הפעלה מחדש": חיבור חדש לאותו קובץ
    restored = client.get(f"/api/conversations/{cid}").json()
    assert len(restored["messages"]) == 2
    assert restored["profile"]["credit_points"]["value"] == 2.75


def test_unknown_conversation_404():
    assert client.get("/api/conversations/nope").status_code == 404


def test_demo_employee_loads_profile_without_llm():
    state = client.post("/api/conversations/new/demo/E-003").json()
    assert state["profile"]["occupation"]["value"] == "מפתח/ת תוכנה"
    assert state["profile"]["current_option"]["value"]["kind"] == "waiver"
    assert state["messages"][0]["role"] == "system"
