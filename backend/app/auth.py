"""הרשאות פשוטות לפיילוט: קוד גישה לנציג וקוד גישה למנהל/ת כללים, בכותרת X-Access-Code.

הקודים ב-.env (REP_ACCESS_CODE, ADMIN_ACCESS_CODE). קוד שלא הוגדר = מצב פיתוח פתוח, עם אזהרה בלוג.
בפיילוט אמיתי מחליפים את זה בהתחברות ארגונית (SSO) — הממשק של התלות (require) נשאר אותו דבר.
המנהל/ת יכול/ה גם לענות כנציג.
"""
import hmac
import logging
import os

from dotenv import load_dotenv
from fastapi import Header, HTTPException

load_dotenv()
log = logging.getLogger(__name__)

ROLES = {"rep": "REP_ACCESS_CODE", "admin": "ADMIN_ACCESS_CODE"}
_warned: set[str] = set()


def _codes(role: str) -> list[str]:
    names = [ROLES[role]] + (["ADMIN_ACCESS_CODE"] if role == "rep" else [])
    return [os.environ[n] for n in names if os.environ.get(n)]


def allowed(role: str, code: str | None) -> bool:
    codes = _codes(role)
    if not os.environ.get(ROLES[role]):
        if role not in _warned:
            log.warning("%s לא הוגדר — מסכי '%s' פתוחים לכולם (מצב פיתוח)", ROLES[role], role)
            _warned.add(role)
        return True
    return bool(code) and any(hmac.compare_digest(code.encode(), c.encode()) for c in codes)


def require(role: str):
    def dependency(x_access_code: str | None = Header(default=None)):
        if not allowed(role, x_access_code):
            raise HTTPException(401, "נדרש קוד גישה")

    return dependency
