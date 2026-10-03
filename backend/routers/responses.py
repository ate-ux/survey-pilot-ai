from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import csv
import io

from database import get_db
from auth import require_user
from schemas import ResponseCreate, ResponseOut, AnswerOut
import models

router = APIRouter(prefix="/api/responses", tags=["responses"])


def _log_audit(db, user_id, action, entity_type=None, entity_id=None, details=None):
    db.add(models.AuditLog(
        user_id=user_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        details=details,
    ))
    db.commit()


@router.get("")
def list_responses(
    survey_id: int = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    q = db.query(models.Response)
    if survey_id:
        q = q.filter(models.Response.survey_id == survey_id)
    responses = q.order_by(models.Response.id.desc()).limit(500).all()
    return {
        "count": len(responses),
        "responses": [ResponseOut.model_validate(r).model_dump() for r in responses],
    }


@router.post("", response_model=ResponseOut)
def create_response(
    payload: ResponseCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    survey = db.query(models.Survey).filter(models.Survey.id == payload.survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    response = models.Response(
        survey_id=payload.survey_id,
        interviewer_id=payload.interviewer_id,
        respondent_code=payload.respondent_code or f"R{survey.id}-auto",
        environment_id=1,
    )
    db.add(response)
    db.flush()  # pour obtenir response.id

    # Enregistrer les réponses
    for ans in payload.answers:
        db.add(models.Answer(
            response_id=response.id,
            question_id=ans.question_id,
            value=ans.value,
        ))

    db.commit()
    db.refresh(response)

    _log_audit(db, user.id, "response.create", "response", response.id,
               {"survey_id": response.survey_id, "answers": len(payload.answers)})

    return response


@router.get("/{response_id}/answers")
def get_answers(response_id: int, db: Session = Depends(get_db),
                user: models.User = Depends(require_user)):
    answers = db.query(models.Answer).filter(models.Answer.response_id == response_id).all()
    return {
        "count": len(answers),
        "answers": [AnswerOut.model_validate(a).model_dump() for a in answers],
    }


@router.post("/import-csv")
async def import_csv(
    survey_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    """
    Import CSV. Format attendu :
      - 1ère ligne : en-tête avec les codes de questions (ex: age,genre,revenu)
      - Lignes suivantes : une réponse par ligne
    """
    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []

    # Récupérer les questions de l'enquête par code
    questions = db.query(models.Question).filter(models.Question.survey_id == survey_id).all()
    code_to_qid = {q.code: q.id for q in questions}

    # Vérifier que toutes les colonnes correspondent à des questions
    missing = [h for h in headers if h not in code_to_qid]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Colonnes sans question correspondante : {missing}. "
                   f"Codes disponibles : {list(code_to_qid.keys())}"
        )

    imported = 0
    for row_idx, row in enumerate(reader, start=1):
        response = models.Response(
            survey_id=survey_id,
            respondent_code=f"CSV-{row_idx}",
            environment_id=1,
        )
        db.add(response)
        db.flush()

        for code, value in row.items():
            if value is None or value == "":
                continue
            db.add(models.Answer(
                response_id=response.id,
                question_id=code_to_qid[code],
                value=str(value),
            ))
        imported += 1

    db.commit()

    _log_audit(db, user.id, "response.import_csv", "survey", survey_id,
               {"imported": imported})

    return {"status": "imported", "count": imported, "survey_id": survey_id}