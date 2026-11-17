"""Admin-only endpoints: review doctors and watch usage."""
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import audit, emailer, models
from app.database import get_db
from app.dependencies import require_admin
from app.ml.model_loader import class_names, review_threshold
from app.ml.model_loader import status as model_status
from app.routers.auth_routes import make_reset_link
from app.schemas import (ActivityOut, AdminStatsOut, AuditOut, RejectRequest, ResetLinkOut,
                         UserOut)

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
        "classes": class_names(),
        "model_ready": state["ready"],
        "model_message": state["message"],
        "model_arch": state["label"],
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
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    doctor = _get_doctor(db, doctor_id)
    _mark_reviewed(doctor, admin, models.STATUS_APPROVED, None)
    db.commit()
    db.refresh(doctor)
    audit.record(db, admin, "doctor_approved", target=doctor.email)
    subject, body = emailer.approved_email(doctor.full_name)
    background.add_task(emailer.send_email, doctor.email, subject, body)
    return doctor


@router.post("/doctors/{doctor_id}/reject", response_model=UserOut)
def reject_doctor(
    doctor_id: int,
    background: BackgroundTasks,
    payload: Optional[RejectRequest] = None,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """Rejects a pending doctor, or revokes access from an approved one."""
    doctor = _get_doctor(db, doctor_id)
    revoked = doctor.status == models.STATUS_APPROVED
    reason = (payload.reason or "").strip() if payload else ""
    _mark_reviewed(doctor, admin, models.STATUS_REJECTED, reason or None)
    db.commit()
    db.refresh(doctor)
    audit.record(db, admin, "doctor_revoked" if revoked else "doctor_rejected",
                 target=doctor.email, detail=reason or None)
    subject, body = emailer.rejected_email(doctor.full_name, reason, revoked)
    background.add_task(emailer.send_email, doctor.email, subject, body)
    return doctor


@router.post("/doctors/{doctor_id}/reset-password", response_model=ResetLinkOut)
def reset_doctor_password(
    doctor_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """Sends the doctor a one-time link to choose a new password.

    The admin never sees or sets the password. If email is not set up, the link is returned
    so the admin can pass it on in person.
    """
    doctor = _get_doctor(db, doctor_id)
    if doctor.status != models.STATUS_APPROVED:
        raise HTTPException(status_code=400, detail="Only approved doctors can have their password reset.")
    link = make_reset_link(db, doctor)
    subject, body = emailer.reset_email(doctor.full_name, link)
    background.add_task(emailer.send_email, doctor.email, subject, body)
    audit.record(db, admin, "admin_reset_link", target=doctor.email)
    if emailer.email_configured():
        return {"message": f"A reset link was emailed to {doctor.email}.", "link": None}
    return {"message": "Email is not set up, so the link was not sent. Give this link to the doctor.", "link": link}


@router.get("/audit", response_model=List[AuditOut])
def audit_log(
    action: Optional[str] = Query(None, max_length=50),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Newest first. Never contains images or case references."""
    query = db.query(models.AuditLog)
    if action:
        query = query.filter(models.AuditLog.action == action)
    return query.order_by(models.AuditLog.created_at.desc(), models.AuditLog.id.desc()).limit(limit).all()


@router.get("/analytics")
def analytics(days: int = Query(30, ge=7, le=365), db: Session = Depends(get_db)):
    """Numbers for the charts: scans per class, scans per day, rejection rate, doctor feedback."""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    rows = (
        db.query(models.Prediction.created_at, models.Prediction.predicted_class,
                 models.Prediction.confidence, models.Prediction.feedback)
        .filter(models.Prediction.created_at >= start)
        .all()
    )
    per_day = {(start + timedelta(days=i)).date().isoformat(): 0 for i in range(days)}
    by_class = {name: 0 for name in class_names()}
    low_conf = 0
    feedback = {"agree": 0, "disagree": 0, "none": 0}
    for created, cls, conf, fb in rows:
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        per_day[created.astimezone(timezone.utc).date().isoformat()] = \
            per_day.get(created.astimezone(timezone.utc).date().isoformat(), 0) + 1
        by_class[cls] = by_class.get(cls, 0) + 1
        low_conf += conf < review_threshold()
        feedback[fb if fb in ("agree", "disagree") else "none"] += 1

    rejected = (
        db.query(func.count(models.AuditLog.id))
        .filter(models.AuditLog.action == "image_rejected", models.AuditLog.created_at >= start)
        .scalar()
    ) or 0
    accepted = len(rows)
    total_tries = accepted + rejected
    return {
        "days": days,
        "accepted": accepted,
        "rejected": rejected,
        "rejection_rate": (rejected / total_tries) if total_tries else 0.0,
        "low_confidence": int(low_conf),
        "by_class": by_class,
        "per_day": [{"date": d, "count": c} for d, c in per_day.items()],
        "feedback": feedback,
    }


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
            "low_confidence": prediction.confidence < review_threshold(),
            "created_at": prediction.created_at,
        }
        for prediction, doctor in rows
    ]
