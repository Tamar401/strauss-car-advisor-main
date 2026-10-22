"""Invitations, registration, login, and session management.

Accounts are invitation-only: an administrator issues a 5-digit code tied to an email and a role
(employee or representative), and the person registers with it and chooses a password.
"""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth import (
    AuthenticatedUser,
    create_user_session,
    get_current_user,
    require_admin,
    hash_password,
    normalize_email,
    revoke_user_session,
    verify_password,
)
from app.store import get_store

router = APIRouter(prefix="/api/auth", tags=["authentication"])


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)
    role: str | None = Field(default=None, pattern="^(employee|rep|admin)$")


class InvitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(pattern="^(employee|rep)$")
    email: str = Field(min_length=3, max_length=254)
    full_name: str = Field(min_length=1, max_length=100)
    mobile_number: str | None = Field(default=None, max_length=32)

    @field_validator("full_name")
    @classmethod
    def require_full_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Full name is required.")
        return value


class Registration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(pattern="^(employee|rep)$")
    email: str = Field(min_length=3, max_length=254)
    code: str = Field(pattern=r"^[0-9]{5}$")
    password: str = Field(min_length=12, max_length=128)


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    full_name: str | None = None
    mobile_number: str | None = None


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserResponse


class InvitationResponse(BaseModel):
    role: str
    email: str
    code: str
    expires_at: datetime


def _code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("ascii")).hexdigest()


def _new_session(
    user_id: str,
    email: str,
    role: str,
    full_name: str | None = None,
    mobile_number: str | None = None,
) -> SessionResponse:
    token, expires = create_user_session(user_id)
    return SessionResponse(
        access_token=token,
        expires_at=expires,
        user=UserResponse(
            id=user_id,
            email=email,
            role=role,
            full_name=full_name,
            mobile_number=mobile_number,
        ),
    )


@router.post(
    "/invitations",
    response_model=InvitationResponse,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def create_invitation(request: InvitationRequest):
    email = normalize_email(request.email)
    code = f"{secrets.randbelow(100_000):05d}"
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    result = get_store().create_invitation(
        uuid4().hex,
        email,
        request.role,
        _code_hash(code),
        expires_at.isoformat(),
        request.full_name,
        (request.mobile_number or "").strip() or None,
    )
    if result == "exists":
        raise HTTPException(409, "An account or an invitation for another role already exists for this email.")
    return InvitationResponse(role=request.role, email=email, code=code, expires_at=expires_at)


@router.post("/register", response_model=SessionResponse, response_model_exclude_none=True, status_code=201)
def register(registration: Registration, request: Request):
    email = normalize_email(registration.email)
    code_hash = _code_hash(registration.code)
    store = get_store()
    client_ip = request.client.host if request.client else "unknown"
    if not store.registration_attempt_allowed(email, client_ip):
        raise HTTPException(429, "Too many registration attempts. Try again in 15 minutes.")
    role = store.invitation_role(email, code_hash)
    if role is None:
        store.record_registration_failure(email, client_ip)
        raise HTTPException(401, "The email or registration code is invalid, expired, or already used.")
    if role != registration.role:
        raise HTTPException(409, f"This code was issued for the {role} role.")
    user_id = store.accept_invitation(email, code_hash, hash_password(registration.password))
    if user_id is None:
        store.record_registration_failure(email, client_ip)
        raise HTTPException(401, "The email or registration code is invalid, expired, or already used.")
    store.clear_registration_attempts(email, client_ip)
    user = store.user_by_email(email)
    return _new_session(user_id, email, role, user["full_name"], user["mobile_number"])


@router.post("/login", response_model=SessionResponse, response_model_exclude_none=True)
def login(credentials: Credentials):
    email = normalize_email(credentials.email)
    configured_username = os.environ.get("ADMIN_USERNAME", "")
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    if credentials.role == "admin" or (configured_username and email.lower() == configured_username.strip().lower()):
        if not configured_username or not admin_password or len(admin_password) < 12:
            if credentials.role == "admin":
                raise HTTPException(503, "Configure ADMIN_USERNAME as an email and ADMIN_PASSWORD with at least 12 characters.")
        else:
            try:
                admin_username = normalize_email(configured_username)
            except HTTPException as exc:
                if credentials.role == "admin":
                    raise HTTPException(503, "ADMIN_USERNAME must be a valid email address.") from exc
                admin_username = ""
            if credentials.role == "admin" and email != admin_username:
                raise HTTPException(401, "Invalid administrator email or password.")
            if admin_username and email == admin_username:
                if hmac.compare_digest(credentials.password.encode("utf-8"), admin_password.encode("utf-8")):
                    if not get_store().upsert_admin_account(email, hash_password(admin_password)):
                        raise HTTPException(409, "The administrator username is already assigned to another account.")
                    return _new_session("system-admin", email, "admin")
                if credentials.role == "admin":
                    raise HTTPException(401, "Invalid administrator email or password.")
    elif credentials.role == "admin":
        raise HTTPException(401, "Invalid administrator email or password.")
    user = get_store().user_by_email(email)
    if user is None or user["role"] == "admin" or user["password_hash"] == "pending" or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password.")
    return _new_session(
        user["id"], user["email"], user["role"], user["full_name"], user["mobile_number"],
    )


@router.get("/me", response_model=UserResponse, response_model_exclude_none=True)
def me(user: AuthenticatedUser = Depends(get_current_user)):
    return user


@router.post("/logout")
def logout(authorization: str | None = Header(default=None), _: AuthenticatedUser = Depends(get_current_user)):
    revoke_user_session(authorization)
    return {"ok": True}
