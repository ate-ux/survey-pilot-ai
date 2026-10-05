"""Module Formulaires — génération et saisie dynamique d'enquêtes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from database import get_db
from auth import require_user
import models

router = APIRouter(prefix="/api/forms", tags=["forms"])


# ============================================================
# Schémas Pydantic
# ============================================================
class AnswerInput(BaseModel):
    question_id: int
    value: str


class FullResponseInput(BaseModel):
    survey_id: int
    interviewer_id: Optional[int] = None
    respondent_code: Optional[str] = None
    answers: List[AnswerInput] = []
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gps_accuracy: Optional[float] = None


# ============================================================
# Helpers
# ============================================================
def _log_audit(db, user_id, action, entity_type=None, entity_id=None, details=None):
    db.add(models.AuditLog(
        user_id=user_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        details=details,
    ))
    db.commit()


# ============================================================
# 1. Récupérer le formulaire d'une enquête
# ============================================================
@router.get("/survey/{survey_id}")
def get_survey_form(
    survey_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    """Retourne la structure complète du formulaire d'une enquête."""
    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    questions = (
        db.query(models.Question)
        .filter(models.Question.survey_id == survey_id)
        .order_by(models.Question.order_index)
        .all()
    )

    return {
        "survey_id": survey.id,
        "code": survey.code,
        "title": survey.title,
        "description": survey.description,
        "status": survey.status,
        "nb_questions": len(questions),
        "questions": [
            {
                "id": q.id,
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


# ============================================================
# 2. Enregistrer une réponse complète avec GPS
# ============================================================
@router.post("/response/submit")
def submit_full_response(
    payload: FullResponseInput,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    """Enregistre une réponse complète (avec GPS optionnel)."""
    survey = db.query(models.Survey).filter(models.Survey.id == payload.survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    # Vérifier que les questions appartiennent bien à cette enquête
    question_ids = {a.question_id for a in payload.answers}
    valid_questions = db.query(models.Question).filter(
        models.Question.survey_id == payload.survey_id,
        models.Question.id.in_(question_ids) if question_ids else False,
    ).all()
    valid_ids = {q.id for q in valid_questions}

    invalid = question_ids - valid_ids
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Questions invalides pour cette enquête : {list(invalid)}"
        )

    # Créer la réponse
    response = models.Response(
        survey_id=payload.survey_id,
        interviewer_id=payload.interviewer_id,
        respondent_code=payload.respondent_code or f"R-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        status="collected",
        environment_id=1,
        latitude=payload.latitude,
        longitude=payload.longitude,
        gps_accuracy=payload.gps_accuracy,
        collected_at_gps=datetime.utcnow() if payload.latitude else None,
    )
    db.add(response)
    db.flush()

    # Enregistrer les réponses
    for ans in payload.answers:
        db.add(models.Answer(
            response_id=response.id,
            question_id=ans.question_id,
            value=ans.value,
        ))

    db.commit()
    db.refresh(response)

    _log_audit(db, user.id, "form.response.submit", "response", response.id,
               {"survey_id": payload.survey_id, "nb_answers": len(payload.answers),
                "has_gps": payload.latitude is not None})

    return {
        "status": "created",
        "response_id": response.id,
        "survey_id": response.survey_id,
        "respondent_code": response.respondent_code,
        "nb_answers": len(payload.answers),
        "gps": {
            "latitude": float(response.latitude) if response.latitude else None,
            "longitude": float(response.longitude) if response.longitude else None,
        } if payload.latitude else None,
    }


# ============================================================
# 3. Statistiques de remplissage d'une enquête
# ============================================================
@router.get("/survey/{survey_id}/completion")
def get_survey_completion(
    survey_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    """Statistiques de complétion d'une enquête."""
    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    total_questions = db.query(models.Question).filter(
        models.Question.survey_id == survey_id).count()

    total_responses = db.query(models.Response).filter(
        models.Response.survey_id == survey_id).count()

    responses_with_gps = db.query(models.Response).filter(
        models.Response.survey_id == survey_id,
        models.Response.latitude.isnot(None),
    ).count()

    return {
        "survey_id": survey_id,
        "total_questions": total_questions,
        "total_responses": total_responses,
        "responses_with_gps": responses_with_gps,
        "gps_coverage": round(responses_with_gps / total_responses * 100, 2) if total_responses > 0 else 0,
    }