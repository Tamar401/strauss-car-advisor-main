"""הרשאות פשוטות לפיילוט: קוד גישה לנציג וקוד גישה למנהל/ת כללים, בכותרת X-Access-Code.

הקודים ב-.env (REP_ACCESS_CODE, ADMIN_ACCESS_CODE). קוד שלא הוגדר = מצב פיתוח פתוח, עם אזהרה בלוג.
בפיילוט אמיתי מחליפים את זה בהתחברות ארגונית (SSO) — הממשק של התלות (require) נשאר אותו דבר.
המנהל/ת יכול/ה גם לענות כנציג.
"""
import hmac
import logging
import os
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

load_dotenv()
log = logging.getLogger(__name__)

ROLES = {"rep": "REP_ACCESS_CODE", "admin": "ADMIN_ACCESS_CODE"}
_warned: set[str] = set()
SESSION_DAYS = 30
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s.]+(?:\.[^@\s.]+)+$")


class AuthenticatedUser(BaseModel):
    id: str
    email: str
    role: str = "employee"
    full_name: str | None = None
    mobile_number: str | None = None


def normalize_email(email: str) -> str:
    value = email.strip().lower()
    if len(value) > 254 or not _EMAIL.fullmatch(value):
        raise HTTPException(422, "Enter a valid email address.")
    return value


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32, maxmem=64 * 1024 * 1024)
    return f"scrypt${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = stored.split("$")
        if algorithm != "scrypt":
            return False
        salt, expected = bytes.fromhex(salt_hex), bytes.fromhex(digest_hex)
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=len(expected), maxmem=64 * 1024 * 1024,
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _session_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, hashlib.sha256(token.encode("ascii")).hexdigest()


def create_user_session(user_id: str) -> tuple[str, datetime]:
    from app.store import get_store

    token, token_hash = _session_token()
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    get_store().create_session(token_hash, user_id, expires.isoformat())
    return token, expires


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    return token if scheme.lower() == "bearer" and re.fullmatch(r"[A-Za-z0-9_-]{40,64}", token) else None


def get_current_user(authorization: str | None = Header(default=None)) -> AuthenticatedUser:
    from app.store import get_store

    token = _bearer_token(authorization)
    if token is None:
        raise HTTPException(401, "Please log in to continue.", headers={"WWW-Authenticate": "Bearer"})
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    user = get_store().session_user(token_hash)
    if user is None:
        raise HTTPException(401, "Your session has expired. Please log in again.", headers={"WWW-Authenticate": "Bearer"})
    return AuthenticatedUser(**user)


def require_employee(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if user.role != "employee":
        raise HTTPException(403, "An employee account is required.")
    return user


def require_admin(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if user.role != "admin":
        raise HTTPException(403, "An administrator account is required.")
    return user


def require_representative(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if user.role != "rep":
        raise HTTPException(403, "A representative account is required.")
    return user


def revoke_user_session(authorization: str | None) -> None:
    from app.store import get_store

    token = _bearer_token(authorization)
    if token:
        token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
        get_store().delete_session(token_hash)


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
    def dependency(
        x_access_code: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
    ):
        token = _bearer_token(authorization)
        if role == "rep" and token:
            from app.store import get_store

            user = get_store().session_user(hashlib.sha256(token.encode("ascii")).hexdigest())
            if user and user["role"] == "rep":
                return
        if not allowed(role, x_access_code):
            raise HTTPException(401, "נדרש קוד גישה")

    return dependency
