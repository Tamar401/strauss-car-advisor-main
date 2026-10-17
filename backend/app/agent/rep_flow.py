"""תשובת נציג → עדכון הפרופיל → חישוב מחדש → הודעה בשיחה של העובד.

דטרמיניסטי לגמרי (בלי מודל שפה): הנציג נתן נתון, המנוע מחשב, וההודעה נבנית מתוצאת המנוע.
שני סוגי שאלות: השתתפות ברכב חדש (participation:CAR-XX), וזיהוי הרכב של היום (current_vehicle).
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from google.genai import types

from app import seed
from app.agent.orchestrator import update_status
from app.agent.tools import run_comparison, vehicle_label
from app.contracts import ChatMessage, OptionRequest, RepQuestion, Tracked
from app.engine import vou
from app.store import ConversationRecord, Store


def _apply_participation(record: ConversationRecord, car_id: str, value: float, note: str | None) -> str:
    record.participations[car_id] = Tracked(value=value, source="rep", confirmed=True, note=note)
    car = next(c for c in seed.catalog() if c["id"] == car_id)
    return f"ההשתתפות שלך ב-{car['model']} היא {value:,.0f} ₪" + (f" ({note})" if note else "")


def _apply_current_vehicle(record: ConversationRecord, key_text: str) -> str:
    key = vou.parse_key(key_text)
    row = vou.lookup(key)
    current = record.state.profile.current_option.value or OptionRequest(kind="car", participation=Tracked(source="missing"))
    option = current.model_copy(update={"kind": "car", "car_id": None, "vou_key": key, "vehicle_label": vehicle_label(row)})
    record.state.profile.current_option = Tracked(value=option, source="rep", confirmed=True)
    return f"זיהיתי את הרכב שלך: {vehicle_label(row)}, {row['model_description']}"


def apply_rep_answer(q: RepQuestion, store: Store) -> None:
    record = store.get(q.conversation_id)
    if record is None or q.answer is None:
        return

    note = f"בתוקף מ-{q.answer.effective_from}" if q.answer.effective_from else None
    car_id = q.field.split(":", 1)[1] if q.field.startswith("participation:") else None
    if car_id:
        answer_text = _apply_participation(record, car_id, float(q.answer.value), note)
    elif q.field == "current_vehicle":
        answer_text = _apply_current_vehicle(record, str(q.answer.value))
    else:
        answer_text = f"{q.answer.value}" + (f" ({note})" if note else "")

    lines = [f"עדכון מנציג התחבורה: {answer_text}."]
    comparison = None
    if record.alternatives:
        comparison = run_comparison(record)
        updated = next((a for a in comparison.alternatives if car_id and a.option.car_id == car_id), None)
        if updated is not None:
            lines.append(updated.explanation)
        elif comparison.current.status == "complete":
            lines.append(comparison.current.explanation.splitlines()[0])
            # הרכב של היום זוהה → עכשיו יש הפרש לכל חלופה שחיכתה לו
            for alt in comparison.alternatives:
                if alt.status == "complete":
                    lines.append(f"{alt.label}: {alt.explanation.splitlines()[0]}")
        else:
            lines.append("עדכנתי את ההשוואה.")
    text = "\n".join(lines)

    record.state.messages.append(
        ChatMessage(id=uuid4().hex, role="assistant", text=text, created_at=datetime.now(timezone.utc), comparison=comparison)
    )
    # הסוכן צריך לדעת מה קרה, כדי להמשיך מאותה נקודה בהודעה הבאה של העובד
    record.history += [
        types.Content(role="user", parts=[types.Part(text=f"[הודעת מערכת: נציג התחבורה ענה — {answer_text}. ההשוואה עודכנה.]")]).model_dump(mode="json", exclude_none=True),
        types.Content(role="model", parts=[types.Part(text=text)]).model_dump(mode="json", exclude_none=True),
    ]
    store.save(record)  # קודם שומרים — update_status קורא את השאלות הפתוחות מה-DB
    update_status(record, store)
    store.save(record)
