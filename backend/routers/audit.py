from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from auth import require_user
import models

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
def list_audit(
    limit: int = 100,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    entries = (
        db.query(models.AuditLog)
        .order_by(models.AuditLog.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "count": len(entries),
        "entries": [
            {
                "id": e.id,
                "user_id": e.user_id,
                "action": e.action,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "details": e.details,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ],
    }