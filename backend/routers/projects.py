from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from auth import require_user
from schemas import ProjectCreate, ProjectUpdate, ProjectOut
import models

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _log_audit(db, user_id, action, entity_type=None, entity_id=None, details=None):
    db.add(models.AuditLog(
        user_id=user_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        details=details,
    ))
    db.commit()


@router.get("", response_model=dict)
def list_projects(db: Session = Depends(get_db), user: models.User = Depends(require_user)):
    projects = db.query(models.Project).order_by(models.Project.id).all()
    return {
        "count": len(projects),
        "projects": [ProjectOut.model_validate(p).model_dump() for p in projects],
    }


@router.post("", response_model=ProjectOut)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    if db.query(models.Project).filter(models.Project.code == payload.code).first():
        raise HTTPException(status_code=400, detail="Code projet déjà utilisé")

    project = models.Project(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        environment_id=payload.environment_id or 1,
        created_by=user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    _log_audit(db, user.id, "project.create", "project", project.id,
               {"code": project.code, "name": project.name})

    return project


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db),
                user: models.User = Depends(require_user)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)

    _log_audit(db, user.id, "project.update", "project", project.id,
               payload.model_dump(exclude_unset=True))

    return project


@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db),
                   user: models.User = Depends(require_user)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")

    _log_audit(db, user.id, "project.delete", "project", project.id,
               {"code": project.code})

    db.delete(project)
    db.commit()
    return {"status": "deleted", "id": project_id}