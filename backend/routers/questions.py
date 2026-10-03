from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from auth import require_user
from schemas import QuestionCreate, QuestionOut
import models

router = APIRouter(prefix="/api/questions", tags=["questions"])


def _log_audit(db, user_id, action, entity_type=None, entity_id=None, details=None):
    db.add(models.AuditLog(
        user_id=user_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        details=details,
    ))
    db.commit()


@router.get("")
def list_questions(
    survey_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    qs = (
        db.query(models.Question)
        .filter(models.Question.survey_id == survey_id)
        .order_by(models.Question.order_index)
        .all()
    )
    return {
        "count": len(qs),
        "questions": [QuestionOut.model_validate(q).model_dump() for q in qs],
    }


@router.post("", response_model=QuestionOut)
def create_question(
    payload: QuestionCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    survey = db.query(models.Survey).filter(models.Survey.id == payload.survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    existing = db.query(models.Question).filter(
        models.Question.survey_id == payload.survey_id,
        models.Question.code == payload.code,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Code question déjà utilisé")

    question = models.Question(
        survey_id=payload.survey_id,
        order_index=payload.order_index,
        code=payload.code,
        label=payload.label,
        question_type=payload.question_type,
        options=payload.options,
        is_required=payload.is_required,
    )
    db.add(question)
    db.commit()
    db.refresh(question)

    _log_audit(db, user.id, "question.create", "question", question.id,
               {"code": question.code, "survey_id": question.survey_id})

    return question


@router.post("/bulk")
def bulk_create_questions(
    survey_id: int,
    questions: List[QuestionCreate],
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    """Créer plusieurs questions d'un coup."""
    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    created = []
    for idx, q_data in enumerate(questions, start=1):
        q = models.Question(
            survey_id=survey_id,
            order_index=q_data.order_index or idx,
            code=q_data.code,
            label=q_data.label,
            question_type=q_data.question_type,
            options=q_data.options,
            is_required=q_data.is_required,
        )
        db.add(q)
        created.append(q)

    db.commit()
    _log_audit(db, user.id, "question.bulk_create", "survey", survey_id,
               {"count": len(created)})

    return {"status": "created", "count": len(created)}


@router.delete("/{question_id}")
def delete_question(question_id: int, db: Session = Depends(get_db),
                    user: models.User = Depends(require_user)):
    q = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question introuvable")
    _log_audit(db, user.id, "question.delete", "question", q.id, {"code": q.code})
    db.delete(q)
    db.commit()
    return {"status": "deleted", "id": question_id}