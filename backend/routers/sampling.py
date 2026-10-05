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


# ============================================================
# 1. Créer un plan d'échantillonnage
# ============================================================
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


# ============================================================
# 2. Lister les plans d'une enquête
# ============================================================
@router.get("/plan/{survey_id}")
def list_sampling_plans(survey_id: int,
                        db: Session = Depends(get_db),
                        user: models.User = Depends(require_user)):
    plans = db.query(models.SamplingPlan).filter(
        models.SamplingPlan.survey_id == survey_id).all()
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


# ============================================================
# 3. Tirage ALÉATOIRE SIMPLE
# ============================================================
@router.post("/draw")
def draw_sample(
    population_size: int,
    sample_size: int,
    seed: int = None,
    user: models.User = Depends(require_user),
):
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
        "sample_indices": sample[:50],
        "note": f"{sample_size} individus tirés (affichage limité à 50)",
    }


# ============================================================
# 4. Tirage STRATIFIÉ
# ============================================================
@router.post("/stratified")
def stratified_sample(
    strata: List[dict],
    user: models.User = Depends(require_user),
):
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


# ============================================================
# NOUVELLES MÉTHODES AVANCÉES (V2.1)
# ============================================================

# ============================================================
# 5. Tirage SYSTÉMATIQUE (1 sur k)
# ============================================================
@router.post("/systematic")
def systematic_sample(
    population_size: int,
    sample_size: int,
    seed: int = None,
    user: models.User = Depends(require_user),
):
    """
    Tirage systématique : on prend 1 individu tous les k.
    k = N / n. On choisit un point de départ aléatoire entre 1 et k.
    """
    if sample_size > population_size:
        raise HTTPException(status_code=400,
                            detail="sample_size ne peut pas dépasser population_size")
    if sample_size <= 0 or population_size <= 0:
        raise HTTPException(status_code=400, detail="Tailles doivent être > 0")

    if seed is not None:
        random.seed(seed)

    k = population_size / sample_size
    start = random.uniform(1, k)

    sample_indices = []
    for i in range(sample_size):
        idx = int(round(start + i * k))
        if 1 <= idx <= population_size:
            sample_indices.append(idx)

    return {
        "method": "systematic",
        "population_size": population_size,
        "sample_size": len(sample_indices),
        "sampling_interval_k": round(k, 4),
        "start_point": round(start, 2),
        "sample_indices": sample_indices[:50],
        "note": f"1 individu tous les {round(k, 2)} — affichage limité à 50",
        "formula": "k = N/n, puis sélection de start, start+k, start+2k, ...",
    }


# ============================================================
# 6. Tirage par GRAPPES (clusters)
# ============================================================
@router.post("/cluster")
def cluster_sample(
    n_clusters: int,
    cluster_size: int,
    n_clusters_to_select: int,
    seed: int = None,
    user: models.User = Depends(require_user),
):
    """
    Tirage par grappes : la population est divisée en N grappes,
    on sélectionne aléatoirement n grappes, et on enquête TOUS les
    individus des grappes sélectionnées.
    """
    if n_clusters_to_select > n_clusters:
        raise HTTPException(status_code=400,
                            detail="On ne peut pas sélectionner plus de grappes qu'il n'en existe")

    if seed is not None:
        random.seed(seed)

    all_clusters = list(range(1, n_clusters + 1))
    selected_clusters = random.sample(all_clusters, n_clusters_to_select)

    total_individuals = n_clusters_to_select * cluster_size

    return {
        "method": "cluster",
        "n_clusters_total": n_clusters,
        "cluster_size": cluster_size,
        "n_clusters_selected": n_clusters_to_select,
        "selected_clusters": selected_clusters,
        "total_individuals_sampled": total_individuals,
        "note": f"{n_clusters_to_select} grappes tirées sur {n_clusters} — tous les individus des grappes sont enquêtés",
        "formula": "Sélection aléatoire de n grappes parmi N, puis recensement complet de chaque grappe",
    }


# ============================================================
# 7. Tirage MULTI-DEGRÉS
# ============================================================
@router.post("/multistage")
def multistage_sample(
    strata: List[dict],
    n_clusters_per_stratum: int,
    individuals_per_cluster: int,
    seed: int = None,
    user: models.User = Depends(require_user),
):
    """
    Tirage multi-degrés :
    - 1er degré : sélection de grappes dans chaque strate
    - 2ème degré : sélection d'individus dans chaque grappe
    """
    if seed is not None:
        random.seed(seed)

    result = []
    total_sample = 0

    for s in strata:
        stratum_name = s.get("name", "?")
        n_clusters = s.get("n_clusters", 0)
        cluster_size = s.get("cluster_size", 0)

        if n_clusters_per_stratum > n_clusters:
            raise HTTPException(
                status_code=400,
                detail=f"Strate {stratum_name} : on ne peut pas sélectionner {n_clusters_per_stratum} grappes sur {n_clusters}"
            )

        all_clusters = list(range(1, n_clusters + 1))
        selected_clusters = random.sample(all_clusters, n_clusters_per_stratum)

        individuals_selected = n_clusters_per_stratum * individuals_per_cluster
        total_sample += individuals_selected

        result.append({
            "stratum": stratum_name,
            "n_clusters_total": n_clusters,
            "n_clusters_selected": n_clusters_per_stratum,
            "selected_clusters": selected_clusters,
            "individuals_per_cluster": individuals_per_cluster,
            "individuals_selected": individuals_selected,
        })

    return {
        "method": "multistage",
        "n_strata": len(strata),
        "strata": result,
        "total_sample": total_sample,
        "note": "2 degrés : sélection de grappes, puis d'individus dans chaque grappe",
        "formula": "1er degré : n grappes/strate. 2ème degré : m individus/grappe.",
    }


# ============================================================
# 8. ALLOCATION STRATIFIÉE OPTIMALE
# ============================================================
@router.post("/optimal-allocation")
def optimal_allocation(
    strata: List[dict],
    total_sample: int,
    method: str = "proportional",
    user: models.User = Depends(require_user),
):
    """
    Calcule l'allocation optimale de l'échantillon entre les strates.

    Méthodes :
    - proportional : n_h = n × (N_h / N)
    - neyman : n_h = n × (N_h × S_h) / Σ(N_i × S_i)
    - equal : n_h = n / H
    """
    if not strata:
        raise HTTPException(status_code=400, detail="Aucune strate fournie")
    if total_sample <= 0:
        raise HTTPException(status_code=400, detail="total_sample doit être > 0")

    total_population = sum(s.get("size", 0) for s in strata)
    n_strata = len(strata)

    allocations = []

    if method == "proportional":
        for s in strata:
            n_h = round(total_sample * (s.get("size", 0) / total_population))
            allocations.append({
                "stratum": s.get("name", "?"),
                "population": s.get("size", 0),
                "sample_allocated": n_h,
                "sampling_ratio": round(n_h / s.get("size", 1), 4) if s.get("size", 0) > 0 else 0,
            })

    elif method == "neyman":
        weights = []
        for s in strata:
            weight = s.get("size", 0) * s.get("std", 1.0)
            weights.append(weight)
        total_weight = sum(weights)

        for i, s in enumerate(strata):
            n_h = round(total_sample * (weights[i] / total_weight)) if total_weight > 0 else 0
            allocations.append({
                "stratum": s.get("name", "?"),
                "population": s.get("size", 0),
                "std": s.get("std", 1.0),
                "sample_allocated": n_h,
                "sampling_ratio": round(n_h / s.get("size", 1), 4) if s.get("size", 0) > 0 else 0,
            })

    elif method == "equal":
        n_h = total_sample // n_strata
        remainder = total_sample - (n_h * n_strata)
        for i, s in enumerate(strata):
            alloc = n_h + (1 if i < remainder else 0)
            allocations.append({
                "stratum": s.get("name", "?"),
                "population": s.get("size", 0),
                "sample_allocated": alloc,
                "sampling_ratio": round(alloc / s.get("size", 1), 4) if s.get("size", 0) > 0 else 0,
            })

    else:
        raise HTTPException(status_code=400,
                            detail="method doit être 'proportional', 'neyman' ou 'equal'")

    return {
        "method": f"optimal_allocation_{method}",
        "total_population": total_population,
        "total_sample_requested": total_sample,
        "total_sample_allocated": sum(a["sample_allocated"] for a in allocations),
        "n_strata": n_strata,
        "allocations": allocations,
        "formula": {
            "proportional": "n_h = n × (N_h / N)",
            "neyman": "n_h = n × (N_h × S_h) / Σ(N_i × S_i)",
            "equal": "n_h = n / H",
        }.get(method, ""),
    }