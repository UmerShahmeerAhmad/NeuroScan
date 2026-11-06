"""Admin-only endpoints: review doctors and watch usage."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.database import get_db
from app.dependencies import require_admin
from app.ml.model_loader import status as model_status
from app.schemas import ActivityOut, AdminStatsOut, RejectRequest, UserOut

# Every route in this file requires a logged-in administrator.
router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)


def _get_doctor(db: Session, doctor_id: int) -> models.User:
    doctor = db.get(models.User, doctor_id)
    if doctor is None or doctor.role != models.ROLE_DOCTOR:
        raise HTTPException(status_code=404, detail="Doctor not found.")
    return doctor


def _mark_reviewed(doctor: models.User, admin: models.User, status: str, note: Optional[str]):
    from app.models import utcnow

    doctor.status = status
    doctor.review_note = note
    doctor.reviewed_by = admin.id
    doctor.reviewed_at = utcnow()


@router.get("/stats", response_model=AdminStatsOut)
def stats(db: Session = Depends(get_db)):
    """Numbers for the overview tab."""
    doctor_rows = (
        db.query(models.User.status, func.count(models.User.id))
        .filter(models.User.role == models.ROLE_DOCTOR)
        .group_by(models.User.status)
        .all()
    )
    counts = {status: total for status, total in doctor_rows}

    class_rows = (
        db.query(models.Prediction.predicted_class, func.count(models.Prediction.id))
        .group_by(models.Prediction.predicted_class)
        .all()
    )
    by_class = {name: total for name, total in class_rows}

    state = model_status()  # the admin sees the detailed reason if the model is offline
    return {
        "pending": counts.get(models.STATUS_PENDING, 0),
        "approved": counts.get(models.STATUS_APPROVED, 0),
        "rejected": counts.get(models.STATUS_REJECTED, 0),
        "total_scans": sum(by_class.values()),
        "by_class": by_class,
        "classes": settings.CLASS_NAMES,
        "model_ready": state["ready"],
        "model_message": state["message"],
        "model_arch": settings.MODEL_ARCH,
    }


@router.get("/doctors", response_model=List[UserOut])
def list_doctors(
    status: str = Query("all", pattern="^(all|pending|approved|rejected)$"),
    db: Session = Depends(get_db),
):
    """All doctors, or only those with one status. Pending ones are listed oldest first."""
    query = db.query(models.User).filter(models.User.role == models.ROLE_DOCTOR)
    if status != "all":
        query = query.filter(models.User.status == status)

    if status == models.STATUS_PENDING:
        query = query.order_by(models.User.created_at.asc())
    else:
        query = query.order_by(models.User.created_at.desc())
    return query.all()


@router.post("/doctors/{doctor_id}/approve", response_model=UserOut)
def approve_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    doctor = _get_doctor(db, doctor_id)
    _mark_reviewed(doctor, admin, models.STATUS_APPROVED, None)
    db.commit()
    db.refresh(doctor)
    return doctor


@router.post("/doctors/{doctor_id}/reject", response_model=UserOut)
def reject_doctor(
    doctor_id: int,
    payload: Optional[RejectRequest] = None,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """Rejects a pending doctor, or revokes access from an approved one."""
    doctor = _get_doctor(db, doctor_id)
    reason = (payload.reason or "").strip() if payload else ""
    _mark_reviewed(doctor, admin, models.STATUS_REJECTED, reason or None)
    db.commit()
    db.refresh(doctor)
    return doctor


@router.get("/activity", response_model=List[ActivityOut])
def activity(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    """Recent scans across all doctors.

    Deliberately leaves out images and patient references: those are visible
    only to the doctor who uploaded them.
    """
    rows = (
        db.query(models.Prediction, models.User)
        .join(models.User, models.User.id == models.Prediction.doctor_id)
        .order_by(models.Prediction.created_at.desc(), models.Prediction.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": prediction.id,
            "doctor_name": doctor.full_name,
            "doctor_institution": doctor.institution,
            "predicted_class": prediction.predicted_class,
            "confidence": prediction.confidence,
            "low_confidence": prediction.confidence < settings.CONFIDENCE_THRESHOLD,
            "created_at": prediction.created_at,
        }
        for prediction, doctor in rows
    ]
