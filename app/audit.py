"""The audit log: one row for every important action."""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app import models

log = logging.getLogger("neuroscan.audit")





def record(db: Session, actor: Optional[models.User], action: str,
           target: Optional[str] = None, detail: Optional[str] = None,
           actor_name: Optional[str] = None) -> None:
    """Writes one audit row. A failure here is logged but never breaks the request."""
    try:
        db.add(models.AuditLog(
            actor_id=actor.id if actor else None,
            actor_name=(actor.full_name if actor else actor_name) or "Unknown",
            action=action,
            target_label=(target or "")[:255] or None,
            detail=(detail or "")[:1000] or None,
        ))
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        log.exception("Could not write audit entry %s", action)
