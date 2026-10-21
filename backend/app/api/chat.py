"""/api/chat ו-/api/conversations — השיחה עם הסוכן. בעלות: מפתחת ב'."""
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from google.genai import types
from pydantic import BaseModel

from app import seed
from app.agent.orchestrator import handle_message
from app.agent.tools import PROFILE_NUMBERS, ToolError, missing_profile_fields, run_comparison, update_profile
from app.auth import AuthenticatedUser, require_employee
from app.contracts import ChatMessage, ChatRequest, CompareRequest, ConversationState, EmployeeProfile, Tracked
from app.engine.compare import FIELD_NAMES, all_options, compare, demo_profile
from app.store import ConversationRecord, get_store

router = APIRouter(prefix="/api", tags=["chat"])


def _get(conversation_id: str, user_id: str) -> ConversationRecord:
    record = get_store().get_owned(conversation_id, user_id)
    if record is None:
        raise HTTPException(404, "שיחה לא נמצאה")
    return record


@router.post("/chat", response_model=ConversationState)
def chat(req: ChatRequest, user: AuthenticatedUser = Depends(require_employee)):
    store = get_store()
    if not req.message.strip():
        raise HTTPException(400, "הודעה ריקה")
    if req.conversation_id is None:
        record = ConversationRecord(
            state=ConversationState(
                conversation_id=uuid4().hex,
                status="collecting",
                messages=[],
                profile=store.get_profile(user.id) or EmployeeProfile(),
            )
        )
    else:
        record = _get(req.conversation_id, user.id)
    record = handle_message(record, req.message.strip()[:2000], store)
    store.save_owned(record, user.id)
    return record.state


@router.get("/conversations/{conversation_id}", response_model=ConversationState)
def get_conversation(conversation_id: str, user: AuthenticatedUser = Depends(require_employee)):
    return _get(conversation_id, user.id).state


class ProfileCorrection(BaseModel):
    """תיקון ישיר מכרטיס הפרופיל. אותה ולידציה כמו הכלי של הסוכן (update_profile)."""

    fields: dict = {}
    current_participation: Optional[float] = None


@router.patch("/conversations/{conversation_id}/profile", response_model=ConversationState)
def correct_profile(
    conversation_id: str, body: ProfileCorrection, user: AuthenticatedUser = Depends(require_employee),
):
    store = get_store()
    record = _get(conversation_id, user.id)
    allowed_fields = set(PROFILE_NUMBERS) | {"occupation", "children_under_23"}
    unknown = set(body.fields) - allowed_fields
    if unknown:
        raise HTTPException(400, f"שדות לא מוכרים: {', '.join(sorted(unknown))}")
    try:
        update_profile(record, store, **body.fields)
    except ToolError as e:
        raise HTTPException(400, str(e))

    changes = [FIELD_NAMES.get(k, k) for k in body.fields]
    if body.current_participation is not None:
        current = record.state.profile.current_option.value
        if current is None or current.kind != "car":
            raise HTTPException(400, "אין רכב היום — אין השתתפות לתקן")
        if body.current_participation < 0:
            raise HTTPException(400, "השתתפות לא יכולה להיות שלילית")
        record.state.profile.current_option.value = current.model_copy(
            update={"participation": Tracked(value=body.current_participation, source="employee", confirmed=True)}
        )
        changes.append("ההשתתפות ברכב של היום")
    if not changes:
        raise HTTPException(400, "לא נשלח שום תיקון")

    text = f"עדכנתי לפי התיקון שלך: {', '.join(changes)}."
    comparison = None
    if record.alternatives:
        comparison = run_comparison(record)
        text += "\nההשוואה חושבה מחדש עם הנתונים המעודכנים."
    record.state.messages.append(
        ChatMessage(id=uuid4().hex, role="system", text=text, created_at=datetime.now(timezone.utc))
    )
    if comparison is not None:
        record.state.messages.append(
            ChatMessage(
                id=uuid4().hex, role="assistant", created_at=datetime.now(timezone.utc), comparison=comparison,
                text=comparison.current.explanation.splitlines()[0] if comparison.current.status == "complete" else "ההשוואה עודכנה.",
            )
        )
    # הסוכן ימשיך מהנתונים המעודכנים (הפרופיל נכנס לפרומפט בכל תור; ההערה כאן — כדי שיידע שהעובד תיקן)
    record.history.append(
        types.Content(role="user", parts=[types.Part(text=f"[הודעת מערכת: העובד/ת תיקן/ה בכרטיס הפרופיל: {', '.join(changes)}]")]).model_dump(mode="json", exclude_none=True)
    )
    record.history.append(types.Content(role="model", parts=[types.Part(text=text)]).model_dump(mode="json", exclude_none=True))
    store.save_owned(record, user.id)
    return record.state


@router.post("/conversations/{conversation_id}/explore", response_model=ConversationState)
def explore_all_options(conversation_id: str, user: AuthenticatedUser = Depends(require_employee)):
    """כל החלופות בבת אחת, מהמשתלמת ביותר. דטרמיניסטי — בלי מודל שפה, בלי מכסה."""
    store = get_store()
    record = _get(conversation_id, user.id)
    missing = missing_profile_fields(record)
    if missing:
        names = ", ".join(FIELD_NAMES.get(m, m) for m in missing)
        raise HTTPException(409, f"כדי להציג את כל האפשרויות חסר לי עוד: {names}")

    # השתתפות ידועה (מהעובד / מהנציג) — משתמשים בה; אחרת ברירת המחדל מהקטלוג, ומסומנת ככזו בכרטיס.
    # לא נוגעים ב-record.alternatives: הסקירה לא מחליפה את החלופות שהשיחה עוקבת אחריהן.
    options = [
        o.model_copy(update={"participation": record.participations.get(o.car_id)}) if o.kind == "car" else o
        for o in all_options(record.state.profile)
    ]
    comparison = compare(CompareRequest(profile=record.state.profile, alternatives=options))
    comparison.alternatives.sort(key=lambda a: ({"complete": 0, "partial": 1, "blocked": 2}[a.status], -(a.delta_net or 0)))
    record.state.last_comparison = comparison

    available = [a for a in comparison.alternatives if a.status == "complete"]
    blocked = sum(a.status == "blocked" for a in comparison.alternatives)
    if available:
        best = available[0]
        text = (
            f"הנה כל האפשרויות שלך ({len(available)} זמינות), מהמשתלמת ביותר.\n"
            f"הכי משתלמת: {best.label} — {best.explanation.splitlines()[0]}"
        )
    else:
        text = "בדקתי את כל האפשרויות, ואף אחת מהן לא זמינה לך כרגע."
    if blocked:
        text += f"\n{blocked} אפשרויות לא זמינות לך, וגם הן מופיעות עם הסיבה."
    text += "\nבחלופות שלא שאלנו עליהן, ההשתתפות היא ברירת המחדל מהקטלוג (מסומן בכל כרטיס)."

    record.state.messages.append(
        ChatMessage(id=uuid4().hex, role="assistant", text=text, created_at=datetime.now(timezone.utc), comparison=comparison)
    )
    store.save_owned(record, user.id)
    return record.state


@router.post("/conversations/{conversation_id}/demo/{employee_id}", response_model=ConversationState)
def load_demo_employee(
    conversation_id: str, employee_id: str, user: AuthenticatedUser = Depends(require_employee),
):
    """ממלא את הפרופיל מאחד העובדים לדוגמה — כדי להדגים בלי להקליד את כל הנתונים."""
    store = get_store()
    employee = next((e for e in seed.employees() if e["id"] == employee_id), None)
    if employee is None:
        raise HTTPException(404, "עובד לדוגמה לא נמצא")
    if conversation_id == "new":
        record = None
    else:
        record = store.get_owned(conversation_id, user.id)
        if record is None:
            raise HTTPException(404, "שיחה לא נמצאה")
    if record is None:
        record = ConversationRecord(
            state=ConversationState(conversation_id=uuid4().hex, status="collecting", messages=[], profile=EmployeeProfile())
        )
    record.state.profile = demo_profile(employee)
    record.state.employee_display_name = employee["name"].split()[0]
    record.state.messages.append(ChatMessage(
        id=uuid4().hex,
        role="system",
        text=f"נטענו נתוני הדמו של {employee['name']} ({employee['occupation']}). אפשר לשאול: {employee['question']}",
        created_at=datetime.now(timezone.utc),
    ))
    store.save_owned(record, user.id)
    return record.state
