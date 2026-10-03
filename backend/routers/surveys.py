from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from auth import require_user
from schemas import SurveyCreate, SurveyOut
import models

router = APIRouter(prefix="/api/surveys", tags=["surveys"])


def _log_audit(db, user_id, action, entity_type=None, entity_id=None, details=None):
    db.add(models.AuditLog(
        user_id=user_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        details=details,
    ))
    db.commit()


@router.get("")
def list_surveys(
    project_id: int = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    q = db.query(models.Survey)
    if project_id:
        q = q.filter(models.Survey.project_id == project_id)
    surveys = q.order_by(models.Survey.id).all()
    return {
        "count": len(surveys),
        "surveys": [SurveyOut.model_validate(s).model_dump() for s in surveys],
    }


@router.post("", response_model=SurveyOut)
def create_survey(
    payload: SurveyCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    # Vérifier que le projet existe
    project = db.query(models.Project).filter(models.Project.id == payload.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")

    # Vérifier unicité (project_id, code)
    existing = db.query(models.Survey).filter(
        models.Survey.project_id == payload.project_id,
        models.Survey.code == payload.code,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Code enquête déjà utilisé pour ce projet")

    survey = models.Survey(
        project_id=payload.project_id,
        code=payload.code,
        title=payload.title,
        description=payload.description,
        target_population=payload.target_population,
        sample_size=payload.sample_size,
        start_date=payload.start_date,
        end_date=payload.end_date,
        created_by=user.id,
    )
    db.add(survey)
    db.commit()
    db.refresh(survey)

    _log_audit(db, user.id, "survey.create", "survey", survey.id,
               {"code": survey.code, "title": survey.title})

    return survey


@router.get("/{survey_id}", response_model=SurveyOut)
def get_survey(survey_id: int, db: Session = Depends(get_db),
               user: models.User = Depends(require_user)):
    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")
    return survey


@router.patch("/{survey_id}", response_model=SurveyOut)
def update_survey(
    survey_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    allowed = {"title", "description", "status", "target_population",
               "sample_size", "start_date", "end_date"}
    for field, value in payload.items():
        if field in allowed:
            setattr(survey, field, value)

    db.commit()
    db.refresh(survey)

    _log_audit(db, user.id, "survey.update", "survey", survey.id, payload)

    return survey


@router.delete("/{survey_id}")
def delete_survey(survey_id: int, db: Session = Depends(get_db),
                  user: models.User = Depends(require_user)):
    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    _log_audit(db, user.id, "survey.delete", "survey", survey.id, {"code": survey.code})

    db.delete(survey)
    db.commit()
    return {"status": "deleted", "id": survey_id}