"""Module Sandbox — expérimentation sans risque."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import copy

from database import get_db
from auth import require_user
import models

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])


def _log_audit(db, user_id, action, entity_type=None, entity_id=None, details=None):
    db.add(models.AuditLog(
        user_id=user_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        details=details,
    ))
    db.commit()


@router.get("/environments")
def list_environments(db: Session = Depends(get_db),
                      user: models.User = Depends(require_user)):
    envs = db.query(models.Environment).all()
    return {
        "count": len(envs),
        "environments": [
            {"id": e.id, "name": e.name, "is_sandbox": e.is_sandbox}
            for e in envs
        ],
    }


@router.post("/clone/{project_id}")
def clone_project_to_sandbox(
    project_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    """Clone un projet (avec ses enquêtes et questions) dans le sandbox."""
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")

    sandbox = db.query(models.Environment).filter(models.Environment.name == "sandbox").first()
    if not sandbox:
        raise HTTPException(status_code=500, detail="Environnement sandbox introuvable")

    # Créer le projet cloné
    clone = models.Project(
        code=f"{project.code}-SBX-{int(datetime.utcnow().timestamp())}",
        name=f"[SANDBOX] {project.name}",
        description=f"Clone sandbox de {project.code}",
        status="active",
        environment_id=sandbox.id,
        created_by=user.id,
    )
    db.add(clone)
    db.flush()

    # Cloner les enquêtes + questions
    surveys = db.query(models.Survey).filter(models.Survey.project_id == project_id).all()
    survey_count = 0
    question_count = 0

    for s in surveys:
        new_survey = models.Survey(
            project_id=clone.id,
            code=s.code,
            title=s.title,
            description=s.description,
            status="draft",
            target_population=s.target_population,
            sample_size=s.sample_size,
            created_by=user.id,
        )
        db.add(new_survey)
        db.flush()
        survey_count += 1

        questions = db.query(models.Question).filter(models.Question.survey_id == s.id).all()
        for q in questions:
            new_q = models.Question(
                survey_id=new_survey.id,
                order_index=q.order_index,
                code=q.code,
                label=q.label,
                question_type=q.question_type,
                options=q.options,
                is_required=q.is_required,
            )
            db.add(new_q)
            question_count += 1

    db.commit()

    _log_audit(db, user.id, "sandbox.clone", "project", clone.id,
               {"source_project": project_id, "surveys": survey_count, "questions": question_count})

    return {
        "status": "cloned",
        "source_project_id": project_id,
        "sandbox_project_id": clone.id,
        "sandbox_code": clone.code,
        "surveys_cloned": survey_count,
        "questions_cloned": question_count,
    }


@router.delete("/reset")
def reset_sandbox(db: Session = Depends(get_db),
                  user: models.User = Depends(require_user)):
    """Supprime TOUS les projets sandbox et leurs dépendances."""
    sandbox = db.query(models.Environment).filter(models.Environment.name == "sandbox").first()
    if not sandbox:
        raise HTTPException(status_code=500, detail="Sandbox introuvable")

    projects = db.query(models.Project).filter(models.Project.environment_id == sandbox.id).all()
    deleted = 0
    for p in projects:
        db.delete(p)  # cascade via FK sur surveys/questions/responses
        deleted += 1

    db.commit()

    _log_audit(db, user.id, "sandbox.reset", "environment", sandbox.id,
               {"projects_deleted": deleted})

    return {"status": "reset", "projects_deleted": deleted}


@router.get("/stats")
def sandbox_stats(db: Session = Depends(get_db),
                  user: models.User = Depends(require_user)):
    sandbox = db.query(models.Environment).filter(models.Environment.name == "sandbox").first()
    if not sandbox:
        return {"error": "Sandbox introuvable"}

    projects = db.query(models.Project).filter(models.Project.environment_id == sandbox.id).all()
    return {
        "sandbox_environment_id": sandbox.id,
        "projects_count": len(projects),
        "projects": [
            {"id": p.id, "code": p.code, "name": p.name, "created_at": p.created_at.isoformat() if p.created_at else None}
            for p in projects
        ],
    }