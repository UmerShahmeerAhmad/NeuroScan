"""Signup, login, and password reset."""
import hashlib
import secrets
from datetime import timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit, emailer, models
from app.auth import DUMMY_HASH, create_access_token, hash_password, verify_password
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import utcnow
from app.ratelimit import (IP_LIMIT_FACTOR, RESET_LIMIT, describe_wait, login_failures,
                           reset_requests)
from app.schemas import (DoctorSignup, ForgotPasswordRequest, LoginRequest, MessageOut,
                         ResetPasswordRequest, TokenResponse, UserOut)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_reset_link(db: Session, user: models.User) -> str:
    """Creates a one-time reset token (older ones stop working) and returns the link."""
    db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.user_id == user.id,
        models.PasswordResetToken.used_at.is_(None),
    ).update({"used_at": utcnow()})
    raw = secrets.token_urlsafe(32)
    db.add(models.PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        expires_at=utcnow() + timedelta(minutes=settings.RESET_TOKEN_MINUTES),
    ))
    db.commit()
    return f"{settings.APP_BASE_URL}/reset-password?token={raw}"


def _authenticate(db: Session, email: str, password: str) -> models.User:
    """Checks email + password, then checks that a doctor has been approved."""
    user = db.query(models.User).filter(models.User.email == email.strip().lower()).first()

    if user is None:
        verify_password(password, DUMMY_HASH)  # keep timing the same
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    if not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    # The approval rule: only approved doctors can get in.
    if user.role == models.ROLE_DOCTOR:
        if user.status == models.STATUS_PENDING:
            raise HTTPException(
                status_code=403,
                detail="Your registration is waiting for admin approval. "
                       "You can log in once it has been reviewed.",
            )
        if user.status == models.STATUS_REJECTED:
            reason = f" Reason: {user.review_note}" if user.review_note else ""
            raise HTTPException(
                status_code=403,
                detail=f"Your registration was not approved.{reason}",
            )
    return user


def _guarded_login(db: Session, request: Request, email: str, password: str) -> models.User:
    """Login with rate limiting: repeated wrong passwords lock the login for a while."""
    email = email.strip().lower()
    ip = _ip(request)
    user_key, ip_key = f"user:{email}|{ip}", f"ip:{ip}"

    wait = max(
        login_failures.retry_after(user_key, settings.LOGIN_MAX_ATTEMPTS),
        login_failures.retry_after(ip_key, settings.LOGIN_MAX_ATTEMPTS * IP_LIMIT_FACTOR),
    )
    if wait:
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts. Please try again in {describe_wait(wait)}.",
            headers={"Retry-After": str(wait)},
        )
    try:
        user = _authenticate(db, email, password)
    except HTTPException as exc:
        if exc.status_code == 401:   # a wrong password counts; "pending approval" does not
            login_failures.add([user_key, ip_key])
            if login_failures.retry_after(user_key, settings.LOGIN_MAX_ATTEMPTS):
                audit.record(db, None, "login_locked", target=email, actor_name="(anonymous)",
                             detail=f"Locked after {settings.LOGIN_MAX_ATTEMPTS} wrong passwords from {ip}.")
        raise
    login_failures.clear(user_key)
    return user


def _token_for(user: models.User) -> dict:
    return {
        "access_token": create_access_token(user.id, user.role),
        "token_type": "bearer",
        "role": user.role,
        "full_name": user.full_name,
        "email": user.email,
    }


@router.post("/signup", response_model=MessageOut, status_code=201)
def signup(payload: DoctorSignup, background: BackgroundTasks, db: Session = Depends(get_db)):
    """Doctors register here. They start as 'pending' until the admin approves them."""
    email = payload.email.strip().lower()

    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    doctor = models.User(
        full_name=payload.full_name,
        email=email,
        hashed_password=hash_password(payload.password),
        role=models.ROLE_DOCTOR,
        status=models.STATUS_PENDING,
        institution=payload.institution,
        designation=payload.designation,
        license_number=payload.license_number,
    )
    db.add(doctor)
    try:
        db.commit()
    except IntegrityError:  # two signups with the same email at the same moment
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    audit.record(db, doctor, "doctor_signup", target=email, detail=f"Institution: {doctor.institution}")
    subject, body = emailer.new_registration_email(doctor)
    background.add_task(emailer.send_email, settings.ADMIN_NOTIFY_EMAIL, subject, body)   # tell the administrator
    return {"message": "Registration received. The administrator will review your details."}


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Used by the website's login page (JSON body)."""
    return _token_for(_guarded_login(db, request, payload.email, payload.password))


@router.post("/token", include_in_schema=True)
def token_for_docs(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Same login, but as a form. This is what the 'Authorize' button in /docs uses."""
    user = _guarded_login(db, request, form.username, form.password)
    return {"access_token": create_access_token(user.id, user.role), "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user


# ------------------------------------------------------------- password reset
GENERIC_RESET_MESSAGE = (
    "If an account with that email can log in, a reset link has been sent. "
    "Check your inbox (and spam folder). The link works once."
)


@router.post("/forgot-password", response_model=MessageOut)
def forgot_password(payload: ForgotPasswordRequest, request: Request, background: BackgroundTasks,
                    db: Session = Depends(get_db)):
    """Always gives the same answer, so nobody can find out which emails are registered."""
    ip = _ip(request)
    wait = reset_requests.retry_after(f"ip:{ip}", RESET_LIMIT)
    if wait:
        raise HTTPException(
            status_code=429,
            detail=f"Too many reset requests. Please try again in {describe_wait(wait)}.",
            headers={"Retry-After": str(wait)},
        )
    reset_requests.add([f"ip:{ip}"])

    email = payload.email.strip().lower()
    user = db.query(models.User).filter(models.User.email == email).first()
    allowed = user is not None and (user.role == models.ROLE_ADMIN or user.status == models.STATUS_APPROVED)
    if allowed:
        link = make_reset_link(db, user)
        subject, body = emailer.reset_email(user.full_name, link)
        background.add_task(emailer.send_email, user.email, subject, body)
        audit.record(db, user, "password_reset_requested", target=user.email)
    return {"message": GENERIC_RESET_MESSAGE}


@router.post("/reset-password", response_model=MessageOut)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    bad = HTTPException(status_code=400, detail="This reset link is invalid or has expired. Please request a new one.")
    row = (
        db.query(models.PasswordResetToken)
        .filter(models.PasswordResetToken.token_hash == hash_token(payload.token))
        .first()
    )
    if row is None or row.used_at is not None:
        raise bad
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if expires < utcnow():
        raise bad
    user = db.get(models.User, row.user_id)
    if user is None:
        raise bad

    user.hashed_password = hash_password(payload.password)
    user.password_changed_at = utcnow()      # ends every older login
    row.used_at = utcnow()
    db.commit()
    audit.record(db, user, "password_reset_done", target=user.email)
    return {"message": "Your password has been changed. You can log in with it now."}
