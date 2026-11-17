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

    doctor = relationship("User", back_populates="predictions")
