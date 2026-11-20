"""Database tables."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base

# Allowed values for User.role and User.status
ROLE_ADMIN = "admin"
ROLE_DOCTOR = "doctor"

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """Both the administrator and the doctors live in this table."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    role = Column(String(20), nullable=False, default=ROLE_DOCTOR)
    # Doctors start as "pending" and cannot log in until the admin approves them.
    status = Column(String(20), nullable=False, default=STATUS_PENDING, index=True)

    # Details the admin checks before approving a doctor
    institution = Column(String(200))
    designation = Column(String(120))
    license_number = Column(String(80))

    # Filled in when the admin approves or rejects
    review_note = Column(Text)
    reviewed_at = Column(DateTime(timezone=True))
    reviewed_by = Column(Integer, ForeignKey("users.id"))

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    # Tokens issued before this moment are no longer accepted (set when the password changes).
    password_changed_at = Column(DateTime(timezone=True))

    predictions = relationship(
        "Prediction", back_populates="doctor", cascade="all, delete-orphan"
    )


class Prediction(Base):
    """One MRI analysed by one doctor."""

    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    patient_ref = Column(String(80))          # optional case number typed by the doctor
    original_filename = Column(String(255))
    stored_filename = Column(String(255), nullable=False)   # random name on disk

    predicted_class = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False)              # 0 to 1
    probabilities = Column(Text, nullable=False)            # JSON: {"glioma": 0.01, ...}
    model_name = Column(String(50))

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    # The doctor's own opinion of the result: "agree" or "disagree", with an optional note.
    feedback = Column(String(10))
    feedback_note = Column(Text)
    feedback_at = Column(DateTime(timezone=True))

    doctor = relationship("User", back_populates="predictions")


class AuditLog(Base):
    """Who did what, and when. Never holds images or patient references."""

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    actor_id = Column(Integer)                 # no foreign key: the log must outlive deleted users
    actor_name = Column(String(160))
    action = Column(String(50), nullable=False, index=True)
    target_label = Column(String(255))
    detail = Column(Text)


class PasswordResetToken(Base):
    """A one-time link for choosing a new password. Only the hash of the token is stored."""

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
