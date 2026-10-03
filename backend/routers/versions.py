"""Module Versioning — snapshots et restauration."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from auth import require_user
from schemas import QuestionOut, SurveyOut
import models

router = APIRouter(prefix="/api/versions", tags=["versions"])


def _log_audit(db, user_id, action, entity_type=None, entity_id=None, details=None):
    db.add(models.AuditLog(
        user_id=user_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        details=details,
    ))
    db.commit()


def _next_version(db: Session, entity_type: str, entity_id: int) -> int:
    last = (
        db.query(models.Version)
        .filter(models.Version.entity_type == entity_type,
                models.Version.entity_id == entity_id)
        .order_by(models.Version.version_number.desc())
        .first()
    )
    return (last.version_number + 1) if last else 1


@router.post("/survey/{survey_id}/snapshot")
def snapshot_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    """Crée un snapshot de l'enquête + ses questions."""
    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    questions = (
        db.query(models.Question)
        .filter(models.Question.survey_id == survey_id)
        .order_by(models.Question.order_index)
        .all()
    )

    snapshot_data = {
        "survey": {
            "code": survey.code,
            "title": survey.title,
            "description": survey.description,
            "status": survey.status,
            "target_population": survey.target_population,
            "sample_size": survey.sample_size,
        },
        "questions": [
            {
                "order_index": q.order_index,
                "code": q.code,
                "label": q.label,
                "question_type": q.question_type,
                "options": q.options,
                "is_required": q.is_required,
            }
            for q in questions
        ],
    }

    version_number = _next_version(db, "survey", survey_id)
    version = models.Version(
        entity_type="survey",
        entity_id=survey_id,
        version_number=version_number,
        snapshot=snapshot_data,
        created_by=user.id,
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    _log_audit(db, user.id, "version.snapshot", "survey", survey_id,
               {"version_number": version_number})

    return {
        "status": "snapshot_created",
        "version_id": version.id,
        "version_number": version_number,
        "survey_id": survey_id,
        "questions_count": len(questions),
    }


@router.get("/survey/{survey_id}")
def list_survey_versions(survey_id: int,
                         db: Session = Depends(get_db),
                         user: models.User = Depends(require_user)):
    versions = (
        db.query(models.Version)
        .filter(models.Version.entity_type == "survey",
                models.Version.entity_id == survey_id)
        .order_by(models.Version.version_number.desc())
        .all()
    )
    return {
        "count": len(versions),
        "versions": [
            {
                "id": v.id,
                "version_number": v.version_number,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "questions_count": len(v.snapshot.get("questions", [])),
            }
            for v in versions
        ],
    }


@router.post("/survey/{survey_id}/restore/{version_number}")
def restore_survey(
    survey_id: int,
    version_number: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    """Restaure une version antérieure (crée un nouveau snapshot avant)."""
    version = (
        db.query(models.Version)
        .filter(models.Version.entity_type == "survey",
                models.Version.entity_id == survey_id,
                models.Version.version_number == version_number)
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="Version introuvable")

    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    # Snapshot de l'état actuel avant restauration (sécurité)
    current_questions = db.query(models.Question).filter(
        models.Question.survey_id == survey_id).all()
    current_data = {
        "survey": {
            "code": survey.code, "title": survey.title, "description": survey.description,
            "status": survey.status, "target_population": survey.target_population,
            "sample_size": survey.sample_size,
        },
        "questions": [
            {"order_index": q.order_index, "code": q.code, "label": q.label,
             "question_type": q.question_type, "options": q.options,
             "is_required": q.is_required}
            for q in current_questions
        ],
    }
    safety_version = _next_version(db, "survey", survey_id)
    db.add(models.Version(
        entity_type="survey", entity_id=survey_id,
        version_number=safety_version, snapshot=current_data,
        created_by=user.id,
    ))

    # Restaurer
    snap = version.snapshot
    s = snap["survey"]
    survey.title = s["title"]
    survey.description = s.get("description")
    survey.target_population = s.get("target_population")
    survey.sample_size = s.get("sample_size")

    # Supprimer les questions actuelles et recréer
    db.query(models.Question).filter(models.Question.survey_id == survey_id).delete()
    for q in snap.get("questions", []):
        db.add(models.Question(
            survey_id=survey_id,
            order_index=q["order_index"],
            code=q["code"],
            label=q["label"],
            question_type=q["question_type"],
            options=q.get("options"),
            is_required=q.get("is_required", True),
        ))

    db.commit()

    _log_audit(db, user.id, "version.restore", "survey", survey_id,
               {"restored_to": version_number, "safety_snapshot": safety_version})

    return {
        "status": "restored",
        "survey_id": survey_id,
        "restored_to_version": version_number,
        "safety_snapshot_version": safety_version,
    }