"""Payslip extraction and employee-reviewed profile updates."""
from datetime import datetime, timezone
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict

from app.agent.payslip import PayslipFields, extract_payslip
from app.agent.tools import PROFILE_NUMBERS, ToolError, run_comparison, update_profile
from app.auth import AuthenticatedUser, require_employee
from app.contracts import ChatMessage, ConversationState, EmployeeProfile, Tracked
from app.store import ConversationRecord, get_store

router = APIRouter(prefix="/api", tags=["payslip"])
log = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}


class PayslipExtractionResponse(BaseModel):
    conversation_id: str
    fields: PayslipFields


class PayslipConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: dict[str, float]


def _matches_file_signature(data: bytes, mime_type: str) -> bool:
    if mime_type == "application/pdf":
        return data[:1024].lstrip().startswith(b"%PDF-")
    if mime_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if mime_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


@router.post("/payslip/extract", response_model=PayslipExtractionResponse)
async def extract_employee_payslip(
    file: UploadFile = File(...),
    consent: bool = Form(default=False),
    conversation_id: str | None = Form(default=None),
    user: AuthenticatedUser = Depends(require_employee),
):
    if not consent:
        raise HTTPException(400, "נדרש אישור מפורש לפני שליחת התלוש לשירות ה-AI.")
    mime_type = (file.content_type or "").lower()
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(415, "הפורמט הנתמך הוא PDF, JPEG, PNG או WebP.")

    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(400, "הקובץ ריק.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "גודל התלוש המרבי הוא 10 MB.")
    if not _matches_file_signature(data, mime_type):
        raise HTTPException(415, "תוכן הקובץ אינו תואם לפורמט שדווח.")

    store = get_store()
    if conversation_id:
        record = store.get_owned(conversation_id, user.id)
        if record is None:
            raise HTTPException(404, "שיחה לא נמצאה")
    else:
        record = None

    try:
        fields = extract_payslip(data, mime_type)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception:
        log.warning("Payslip extraction failed", exc_info=True)
        raise HTTPException(502, "לא הצלחנו לקרוא את התלוש. אפשר לנסות קובץ ברור יותר או להזין את הנתונים ידנית.")
    finally:
        data = b""
        await file.close()

    if record is None:
        record = ConversationRecord(
            state=ConversationState(
                conversation_id=uuid4().hex,
                status="collecting",
                messages=[],
                profile=store.get_profile(user.id) or EmployeeProfile(),
            )
        )
        store.save_owned(record, user.id)
    return PayslipExtractionResponse(conversation_id=record.state.conversation_id, fields=fields)


@router.post("/conversations/{conversation_id}/payslip/confirm", response_model=ConversationState)
def confirm_payslip_fields(
    conversation_id: str,
    confirmation: PayslipConfirmation,
    user: AuthenticatedUser = Depends(require_employee),
):
    unknown = set(confirmation.fields) - set(PROFILE_NUMBERS)
    if unknown:
        raise HTTPException(400, f"שדות תלוש לא מוכרים: {', '.join(sorted(unknown))}")
    if not confirmation.fields:
        raise HTTPException(400, "לא נמצאו נתונים לאישור. אפשר להזין את הנתונים ידנית.")

    store = get_store()
    record = store.get_owned(conversation_id, user.id)
    if record is None:
        raise HTTPException(404, "שיחה לא נמצאה")
    try:
        update_profile(record, store, **confirmation.fields)
    except ToolError as exc:
        raise HTTPException(400, str(exc)) from exc

    for name in confirmation.fields:
        tracked = getattr(record.state.profile, name)
        setattr(record.state.profile, name, tracked.model_copy(update={"source": "payslip", "confirmed": True}))

    labels = ", ".join(confirmation.fields)
    record.state.messages.append(
        ChatMessage(
            id=uuid4().hex,
            role="system",
            text=f"הנתונים שאישרת מהתלוש נשמרו בפרופיל: {labels}.",
            created_at=datetime.now(timezone.utc),
        )
    )
    if record.alternatives:
        comparison = run_comparison(record)
        record.state.messages.append(
            ChatMessage(
                id=uuid4().hex,
                role="assistant",
                text="עדכנתי את ההשוואה לפי הנתונים שאישרת מהתלוש.",
                created_at=datetime.now(timezone.utc),
                comparison=comparison,
            )
        )
    store.save_owned(record, user.id)
    return record.state