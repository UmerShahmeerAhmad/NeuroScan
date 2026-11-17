"""Pydantic schemas: what the API accepts and what it returns."""
import json
import re
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.ml.model_loader import review_threshold


# ------------------------------------------------------------------ requests
class DoctorSignup(BaseModel):
    full_name: str = Field(min_length=3, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)
    institution: str = Field(min_length=2, max_length=200)
    designation: str = Field(min_length=2, max_length=120)
    license_number: str = Field(min_length=3, max_length=80)

    @field_validator("full_name", "institution", "designation", "license_number")
    @classmethod
    def tidy_text(cls, value: str) -> str:
        value = " ".join(value.split())  # trim and collapse extra spaces
        if len(value) < 2:
            raise ValueError("cannot be blank.")
        return value

    @field_validator("password")
    @classmethod
    def strong_enough(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValueError("must include at least one letter and one number.")
        if len(value.encode("utf-8")) > 72:  # bcrypt limit
            raise ValueError("is too long.")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class RejectRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=300)


# ----------------------------------------------------------------- responses
class MessageOut(BaseModel):
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    email: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    role: str
    status: str
    institution: Optional[str] = None
    designation: Optional[str] = None
    license_number: Optional[str] = None
    review_note: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None


class PredictionOut(BaseModel):
    id: int
    patient_ref: Optional[str] = None
    original_filename: Optional[str] = None
    predicted_class: str
    confidence: float
    probabilities: Dict[str, float]
    model_name: Optional[str] = None
    low_confidence: bool
    created_at: datetime


class ReliabilityChecks(BaseModel):
    max_prob: float
    entropy: float
    distance: Optional[float] = None
    distance_limit: Optional[float] = None
    confidence_limit: Optional[float] = None
    entropy_limit: Optional[float] = None
    distance_ok: Optional[bool] = None
    confidence_ok: bool


class PredictResponse(BaseModel):
    """What the upload returns. A rejected image is not saved, so it has no id."""

    rejected: bool = False
    reject_reasons: List[str] = []
    id: Optional[int] = None
    patient_ref: Optional[str] = None
    original_filename: Optional[str] = None
    predicted_class: str
    confidence: float
    probabilities: Dict[str, float]
    model_name: Optional[str] = None
    low_confidence: bool = False
    created_at: Optional[datetime] = None
    checks: Optional[ReliabilityChecks] = None


class ActivityOut(BaseModel):
    id: int
    doctor_name: str
    doctor_institution: Optional[str] = None
    predicted_class: str
    confidence: float
    low_confidence: bool
    created_at: datetime


class SummaryOut(BaseModel):
    total: int
    by_class: Dict[str, int]
    classes: List[str]
    model_ready: bool
    model_message: Optional[str] = None


class AdminStatsOut(BaseModel):
    pending: int
    approved: int
    rejected: int
    total_scans: int
    by_class: Dict[str, int]
    classes: List[str]
    model_ready: bool
    model_message: Optional[str] = None
    model_arch: str


# ------------------------------------------------------------------- helpers
def prediction_out(row) -> dict:
    """Turn a Prediction database row into the JSON the frontend expects."""
    return {
        "id": row.id,
        "patient_ref": row.patient_ref,
        "original_filename": row.original_filename,
        "predicted_class": row.predicted_class,
        "confidence": row.confidence,
        "probabilities": json.loads(row.probabilities),
        "model_name": row.model_name,
        "low_confidence": row.confidence < review_threshold(),
        "created_at": row.created_at,
    }


def prediction_list(rows) -> List[dict]:
    return [prediction_out(row) for row in rows]
