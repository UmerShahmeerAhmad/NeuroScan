"""Doctor-only endpoints: upload an MRI, get a prediction, browse history."""
import io
import json
import logging
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.database import get_db
from app.dependencies import require_doctor
from app.ml.model_loader import ModelNotReadyError
from app.ml.model_loader import status as model_status
from app.ml.predict import run_prediction
from app.schemas import MessageOut, PredictionOut, SummaryOut, prediction_list, prediction_out

log = logging.getLogger("neuroscan.doctor")

router = APIRouter(prefix="/api/doctor", tags=["Doctor"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_FORMATS = {"JPEG", "PNG"}
MODEL_OFFLINE_MESSAGE = (
    "The classification model is not available right now. Please contact the administrator."
)


def _open_image(data: bytes) -> Image.Image:
    """Opens the upload and makes sure it is really a JPEG or PNG (not just named like one)."""
    problem = HTTPException(status_code=400, detail="This file is not a valid JPG or PNG image.")
    try:
        Image.open(io.BytesIO(data)).verify()   # checks the file is not corrupt
        image = Image.open(io.BytesIO(data))    # verify() closes the image, so open again
        image.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise problem
    if image.format not in ALLOWED_FORMATS:
        raise problem
    return image


def _own_prediction(db: Session, prediction_id: int, doctor: models.User) -> models.Prediction:
    """A doctor can only ever touch their own scans."""
    row = (
        db.query(models.Prediction)
        .filter(models.Prediction.id == prediction_id, models.Prediction.doctor_id == doctor.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Scan not found.")
    return row


def _file_path(row: models.Prediction) -> Path:
    path = (settings.UPLOAD_DIR / row.stored_filename).resolve()
    if settings.UPLOAD_DIR.resolve() not in path.parents:  # safety: stay inside uploads/
        raise HTTPException(status_code=404, detail="Image not found.")
    return path


@router.post("/predict", response_model=PredictionOut)
def predict(
    file: UploadFile = File(...),
    patient_ref: Optional[str] = Form(None),
    doctor: models.User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    """Upload one MRI image and get the model's classification."""
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Please upload a JPG or PNG image.")

    data = file.file.read(settings.MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413, detail=f"The image is larger than {settings.MAX_UPLOAD_MB} MB."
        )

    image = _open_image(data)

    try:
        result = run_prediction(image)
    except ModelNotReadyError as exc:
        log.error("Prediction unavailable: %s", exc)  # the details go to the server log
        raise HTTPException(status_code=503, detail=MODEL_OFFLINE_MESSAGE)
    except Exception:
        log.exception("Prediction failed")
        raise HTTPException(status_code=500, detail="The model could not process this image.")

    # Save the image under a random name, then record the result.
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    stored_path = settings.UPLOAD_DIR / stored_name
    stored_path.write_bytes(data)

    row = models.Prediction(
        doctor_id=doctor.id,
        patient_ref=(patient_ref or "").strip()[:80] or None,
        original_filename=(file.filename or "")[:255] or None,
        stored_filename=stored_name,
        predicted_class=result["predicted_class"],
        confidence=result["confidence"],
        probabilities=json.dumps(result["probabilities"]),
        model_name=result["model_name"],
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        stored_path.unlink(missing_ok=True)  # do not leave an orphan file behind
        raise

    return prediction_out(row)


@router.get("/history", response_model=List[PredictionOut])
def history(
    limit: int = Query(100, ge=1, le=200),
    doctor: models.User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(models.Prediction)
        .filter(models.Prediction.doctor_id == doctor.id)
        .order_by(models.Prediction.created_at.desc(), models.Prediction.id.desc())
        .limit(limit)
        .all()
    )
    return prediction_list(rows)


@router.get("/summary", response_model=SummaryOut)
def summary(doctor: models.User = Depends(require_doctor), db: Session = Depends(get_db)):
    rows = (
        db.query(models.Prediction.predicted_class, func.count(models.Prediction.id))
        .filter(models.Prediction.doctor_id == doctor.id)
        .group_by(models.Prediction.predicted_class)
        .all()
    )
    by_class = {name: total for name, total in rows}
    ready = model_status()["ready"]
    return {
        "total": sum(by_class.values()),
        "by_class": by_class,
        "classes": settings.CLASS_NAMES,
        "model_ready": ready,
        "model_message": None if ready else MODEL_OFFLINE_MESSAGE,
    }


@router.get("/predictions/{prediction_id}/image")
def prediction_image(
    prediction_id: int,
    doctor: models.User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    """The uploaded image. Only the doctor who uploaded it can fetch it."""
    row = _own_prediction(db, prediction_id, doctor)
    path = _file_path(row)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Image file not found.")
    media_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "private, max-age=3600"})


@router.delete("/predictions/{prediction_id}", response_model=MessageOut)
def delete_prediction(
    prediction_id: int,
    doctor: models.User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    """Deletes a scan record and its image file."""
    row = _own_prediction(db, prediction_id, doctor)
    path = _file_path(row)
    db.delete(row)
    db.commit()
    path.unlink(missing_ok=True)
    return {"message": "Scan deleted."}
