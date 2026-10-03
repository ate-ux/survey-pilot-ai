"""Module Échantillonnage — plans et tirages."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import random

from database import get_db
from auth import require_user
import models

router = APIRouter(prefix="/api/sampling", tags=["sampling"])


def _log_audit(db, user_id, action, entity_type=None, entity_id=None, details=None):
    db.add(models.AuditLog(
        user_id=user_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        details=details,
    ))
    db.commit()


@router.post("/plan/{survey_id}")
def create_sampling_plan(
    survey_id: int,
    method: str = "simple_random",
    sample_size: int = None,
    confidence: float = 0.95,
    margin: float = 0.05,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    plan = models.SamplingPlan(
        survey_id=survey_id,
        method=method,
        sample_size=sample_size or survey.sample_size or 100,
        confidence_level=confidence,
        margin_error=margin,
        notes=f"Plan {method} généré par l'utilisateur",
        created_by=user.id,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    _log_audit(db, user.id, "sampling.plan.create", "survey", survey_id,
               {"method": method, "sample_size": plan.sample_size})

    return {
        "status": "created",
        "plan_id": plan.id,
        "method": plan.method,
        "sample_size": plan.sample_size,
        "confidence_level": float(plan.confidence_level) if plan.confidence_level else None,
        "margin_error": float(plan.margin_error) if plan.margin_error else None,
    }


@router.get("/plan/{survey_id}")
def list_sampling_plans(survey_id: int,
                        db: Session = Depends(get_db),
                        user: models.User = Depends(require_user)):
    plans = db.query(models.SamplingPlan).filter(models.SamplingPlan.survey_id == survey_id).all()
    return {
        "count": len(plans),
        "plans": [
            {
                "id": p.id, "method": p.method, "sample_size": p.sample_size,
                "confidence_level": float(p.confidence_level) if p.confidence_level else None,
                "margin_error": float(p.margin_error) if p.margin_error else None,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in plans
        ],
    }


@router.post("/draw")
def draw_sample(
    population_size: int,
    sample_size: int,
    seed: int = None,
    user: models.User = Depends(require_user),
):
    """Tirage aléatoire simple dans une population de taille N."""
    if sample_size > population_size:
        raise HTTPException(status_code=400,
                            detail="sample_size ne peut pas dépasser population_size")
    if seed is not None:
        random.seed(seed)

    population = list(range(1, population_size + 1))
    sample = random.sample(population, sample_size)

    return {
        "population_size": population_size,
        "sample_size": sample_size,
        "method": "simple_random",
        "sample_indices": sample[:50],  # renvoyer les 50 premiers pour lisibilité
        "note": f"{sample_size} individus tirés (affichage limité à 50)",
    }


@router.post("/stratified")
def stratified_sample(
    strata: List[dict],  # [{"name": "Centre", "size": 500, "sample": 50}, ...]
    user: models.User = Depends(require_user),
):
    """Tirage stratifié : fournir les strates avec tailles et échantillons."""
    total_sample = 0
    result = []
    for s in strata:
        size = s.get("size", 0)
        n = s.get("sample", 0)
        if n > size:
            raise HTTPException(status_code=400,
                                detail=f"Échantillon > taille pour la strate {s.get('name')}")
        total_sample += n
        result.append({
            "stratum": s.get("name"),
            "population": size,
            "sample": n,
            "sampling_ratio": round(n / size, 4) if size > 0 else 0,
        })

    return {
        "method": "stratified",
        "strata": result,
        "total_sample": total_sample,
    }