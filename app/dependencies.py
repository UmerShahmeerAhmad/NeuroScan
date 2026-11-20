"""Reusable checks that protect routes: who is logged in, and what are they allowed to do."""
from datetime import timezone

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app import models
from app.auth import decode_access_token
from app.database import get_db

# tokenUrl lets the "Authorize" button in /docs log in for testing.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """Reads the token, loads the user, and re-checks that the account is still allowed in."""
    expired = HTTPException(
        status_code=401,
        detail="Your session has ended. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if not payload:
        raise expired
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise expired

    user = db.get(models.User, user_id)
    if user is None:
        raise expired

    # A password change or reset ends every older login.
    if user.password_changed_at is not None:
        changed = user.password_changed_at
        if changed.tzinfo is None:
            changed = changed.replace(tzinfo=timezone.utc)
        if int(payload.get("iat", 0)) < int(changed.timestamp()):
            raise expired

    # Checked on every request, so revoking a doctor takes effect immediately
    # even if they still hold a valid token.
    if user.role == models.ROLE_DOCTOR and user.status != models.STATUS_APPROVED:
        raise HTTPException(
            status_code=401,
            detail="Your access has been removed. Please contact the administrator.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role != models.ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="This area is for administrators only.")
    return user


def require_doctor(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role != models.ROLE_DOCTOR:
        raise HTTPException(status_code=403, detail="This area is for doctors only.")
    return user
