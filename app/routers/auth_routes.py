"""Signup and login."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.auth import DUMMY_HASH, create_access_token, hash_password, verify_password
from app.database import get_db
from app.dependencies import get_current_user
from app.schemas import DoctorSignup, LoginRequest, MessageOut, TokenResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


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


def _token_for(user: models.User) -> dict:
    return {
        "access_token": create_access_token(user.id, user.role),
        "token_type": "bearer",
        "role": user.role,
        "full_name": user.full_name,
        "email": user.email,
    }


@router.post("/signup", response_model=MessageOut, status_code=201)
def signup(payload: DoctorSignup, db: Session = Depends(get_db)):
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

    return {"message": "Registration received. The administrator will review your details."}


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Used by the website's login page (JSON body)."""
    return _token_for(_authenticate(db, payload.email, payload.password))


@router.post("/token", include_in_schema=True)
def token_for_docs(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Same login, but as a form. This is what the 'Authorize' button in /docs uses."""
    user = _authenticate(db, form.username, form.password)
    return {"access_token": create_access_token(user.id, user.role), "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user
