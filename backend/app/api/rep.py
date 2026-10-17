"""/api/rep — תור השאלות לנציג התחבורה. בעלות: מפתחת א'.

מענה → עדכון הפרופיל בשיחה (source='rep') → חישוב מחדש → הודעה לעובד. הכל נשמר ב-SQLite.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.agent.rep_flow import apply_rep_answer
from app.auth import require
from app.contracts import RepAnswer, RepQuestion
from app.engine import vou
from app.store import get_store

router = APIRouter(prefix="/api/rep", tags=["rep"], dependencies=[Depends(require("rep"))])


@router.get("/questions", response_model=list[RepQuestion])
def list_questions(status: str | None = None):
    return get_store().questions(status=status)


@router.post("/questions/{question_id}/answer", response_model=RepQuestion)
def answer_question(question_id: str, answer: RepAnswer):
    store = get_store()
    q = store.question(question_id)
    if q is None:
        raise HTTPException(404, "שאלה לא נמצאה")
    if q.status == "answered":
        raise HTTPException(409, "השאלה כבר נענתה")
    if q.field.startswith("participation:"):
        try:
            if float(answer.value) < 0:
                raise ValueError
        except (TypeError, ValueError):
            raise HTTPException(400, "השתתפות חייבת להיות סכום חיובי בש״ח")
    if q.field == "current_vehicle":
        try:
            if vou.lookup(vou.parse_key(str(answer.value))) is None:
                raise ValueError
        except ValueError:
            raise HTTPException(400, "יש לבחור רכב מתוך החיפוש במאגר")
    q.answer = answer
    q.status = "answered"
    q.answered_at = datetime.now(timezone.utc)
    store.save_question(q)
    apply_rep_answer(q, store)
    return q
