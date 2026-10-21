"""Employee registration, representative activation, login, and session management."""
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


class RepresentativeActivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)


class RepresentativeRegistration(Credentials):
    registration_code: str = Field(pattern=r"^[A-Za-z0-9_-]{40,64}$")
    password: str = Field(min_length=12, max_length=128)


class EmployeeRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=1, max_length=100)
    mobile_number: str | None = Field(default=None, max_length=32)

    @field_validator("full_name")
    @classmethod
    def require_full_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Full name is required.")
        return value


class PasswordSetup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    setup_code: str = Field(pattern=r"^[0-9]{5}$")
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


class RepresentativeActivationResponse(BaseModel):
    email: str
    registration_code: str
    expires_at: datetime


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
    "/representatives",
    response_model=RepresentativeActivationResponse,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def create_representative_activation(request: RepresentativeActivationRequest):
    email = normalize_email(request.email)
    store = get_store()
    if store.user_by_email(email):
        raise HTTPException(409, "An account with this email already exists.")
    registration_code = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    store.create_representative_activation(
        email,
        hashlib.sha256(registration_code.encode("ascii")).hexdigest(),
        expires_at.isoformat(),
    )
    return RepresentativeActivationResponse(
        email=email,
        registration_code=registration_code,
        expires_at=expires_at,
    )


@router.post(
    "/representatives/register",
    response_model=UserResponse,
    status_code=201,
)
def register_representative(registration: RepresentativeRegistration):
    email = normalize_email(registration.email)
    user_id = uuid4().hex
    registration_hash = hashlib.sha256(registration.registration_code.encode("ascii")).hexdigest()
    store = get_store()
    if not store.representative_activation_valid(email, registration_hash):
        raise HTTPException(401, "The registration code is invalid, expired, or already used.")
    result = store.activate_representative(
        user_id,
        email,
        hash_password(registration.password),
        registration_hash,
    )
    if result == "invalid":
        raise HTTPException(401, "The registration code is invalid, expired, or already used.")
    if result == "exists":
        raise HTTPException(409, "An account with this email already exists.")
    return UserResponse(id=user_id, email=email, role="rep")


@router.post(
    "/employees/register",
    response_model=SessionResponse,
    response_model_exclude_none=True,
    status_code=201,
)
def register_employee(registration: EmployeeRegistration):
    email = normalize_email(registration.email)
    full_name = registration.full_name
    mobile_number = (registration.mobile_number or "").strip() or None
    user_id = uuid4().hex
    if not get_store().create_account(
        user_id,
        email,
        hash_password(registration.password),
        "employee",
        full_name=full_name,
        mobile_number=mobile_number,
    ):
        raise HTTPException(409, "An account with this email already exists.")
    return _new_session(user_id, email, "employee", full_name, mobile_number)


@router.post("/set-password", response_model=SessionResponse, response_model_exclude_none=True)
def set_employee_password(setup: PasswordSetup, request: Request):
    email = normalize_email(setup.email)
    setup_hash = hashlib.sha256(setup.setup_code.encode("ascii")).hexdigest()
    store = get_store()
    client_ip = request.client.host if request.client else "unknown"
    if not store.employee_setup_attempt_allowed(email, client_ip):
        raise HTTPException(429, "Too many setup-code attempts. Try again in 15 minutes.")
    if not store.employee_setup_valid(email, setup_hash):
        store.record_employee_setup_failure(email, client_ip)
        raise HTTPException(401, "The account or setup code is invalid or already used.")
    user_id = store.set_employee_password(email, setup_hash, hash_password(setup.password))
    if user_id is None:
        store.record_employee_setup_failure(email, client_ip)
        raise HTTPException(401, "The account or setup code is invalid or already used.")
    store.clear_employee_setup_attempts(email, client_ip)
    user = get_store().user_by_email(email)
    return _new_session(user_id, email, "employee", user["full_name"], user["mobile_number"])


@router.post("/login", response_model=SessionResponse, response_model_exclude_none=True)
def login(credentials: Credentials):
    email = normalize_email(credentials.email)
    configured_username = os.environ.get("ADMIN_USERNAME", "")
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    if bool(configured_username) != bool(admin_password) or (admin_password and len(admin_password) < 12):
        raise HTTPException(503, "Configure both ADMIN_USERNAME and an ADMIN_PASSWORD of at least 12 characters.")
    if configured_username and admin_password:
        admin_username = normalize_email(configured_username)
    else:
        admin_username = ""
    if admin_username and hmac.compare_digest(email, admin_username):
        if hmac.compare_digest(credentials.password.encode("utf-8"), admin_password.encode("utf-8")):
            if not get_store().upsert_admin_account(email, hash_password(admin_password)):
                raise HTTPException(409, "The administrator username is already assigned to another account.")
            return _new_session("system-admin", email, "admin")
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
