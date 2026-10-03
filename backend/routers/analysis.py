"""Analyse statistique réelle sur les données collectées."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import numpy as np
from scipy import stats as sps

from database import get_db
from auth import require_user
import models

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _fetch_values(db: Session, survey_id: int, question_code: str):
    """Récupère toutes les valeurs (str) pour une question donnée."""
    q = db.query(models.Question).filter(
        models.Question.survey_id == survey_id,
        models.Question.code == question_code,
    ).first()
    if not q:
        raise HTTPException(status_code=404, detail=f"Question '{question_code}' introuvable")

    rows = (
        db.query(models.Answer.value)
        .join(models.Response, models.Response.id == models.Answer.response_id)
        .filter(models.Response.survey_id == survey_id)
        .filter(models.Answer.question_id == q.id)
        .all()
    )
    return q, [r[0] for r in rows if r[0] is not None]


def _to_numeric(values):
    """Convertit en float, ignore les non-numériques."""
    out = []
    for v in values:
        try:
            out.append(float(v))
        except (ValueError, TypeError):
            pass
    return np.array(out)


# ============================================================
# 1. Statistiques descriptives (univariées)
# ============================================================
@router.get("/descriptive/{survey_id}")
def descriptive(
    survey_id: int,
    question_code: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    q, raw_values = _fetch_values(db, survey_id, question_code)
    if not raw_values:
        return {"question": question_code, "count": 0, "message": "Aucune donnée"}

    numeric = _to_numeric(raw_values)

    # Si c'est numérique
    if len(numeric) >= len(raw_values) * 0.7:
        return {
            "question": question_code,
            "label": q.label,
            "type": "numeric",
            "count": int(len(numeric)),
            "mean": float(np.mean(numeric)),
            "median": float(np.median(numeric)),
            "std": float(np.std(numeric, ddof=1)) if len(numeric) > 1 else 0.0,
            "min": float(np.min(numeric)),
            "max": float(np.max(numeric)),
            "q1": float(np.percentile(numeric, 25)),
            "q3": float(np.percentile(numeric, 75)),
        }

    # Sinon, catégoriel : fréquence
    unique, counts = np.unique(raw_values, return_counts=True)
    total = len(raw_values)
    return {
        "question": question_code,
        "label": q.label,
        "type": "categorical",
        "count": total,
        "frequencies": [
            {"value": str(u), "count": int(c), "percent": round(c / total * 100, 2)}
            for u, c in sorted(zip(unique, counts), key=lambda x: -x[1])
        ],
    }


# ============================================================
# 2. Analyse bivariée : corrélation entre deux variables numériques
# ============================================================
@router.get("/bivariate/{survey_id}")
def bivariate(
    survey_id: int,
    x_code: str,
    y_code: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    # Récupérer les paires (x, y) pour une même réponse
    qx = db.query(models.Question).filter(
        models.Question.survey_id == survey_id,
        models.Question.code == x_code,
    ).first()
    qy = db.query(models.Question).filter(
        models.Question.survey_id == survey_id,
        models.Question.code == y_code,
    ).first()
    if not qx or not qy:
        raise HTTPException(status_code=404, detail="Question X ou Y introuvable")

    from sqlalchemy import and_
    ax = models.Answer.__table__.alias("ax")
    ay = models.Answer.__table__.alias("ay")

    rows = (
        db.query(ax.c.value, ay.c.value)
        .select_from(ax)
        .join(ay, and_(ax.c.response_id == ay.c.response_id,
                       ay.c.question_id == qy.id))
        .filter(ax.c.question_id == qx.id)
        .all()
    )

    xs, ys = [], []
    for xv, yv in rows:
        try:
            xs.append(float(xv))
            ys.append(float(yv))
        except (TypeError, ValueError):
            continue

    if len(xs) < 3:
        return {"error": "Pas assez de données numériques appariées", "n": len(xs)}

    xs = np.array(xs)
    ys = np.array(ys)

    pearson_r, pearson_p = sps.pearsonr(xs, ys)
    spearman_r, spearman_p = sps.spearmanr(xs, ys)

    return {
        "x": x_code,
        "y": y_code,
        "n": len(xs),
        "pearson": {"r": float(pearson_r), "p_value": float(pearson_p)},
        "spearman": {"rho": float(spearman_r), "p_value": float(spearman_p)},
        "means": {"x": float(np.mean(xs)), "y": float(np.mean(ys))},
    }


# ============================================================
# 3. Régression linéaire simple
# ============================================================
@router.get("/regression/{survey_id}")
def regression(
    survey_id: int,
    x_code: str,
    y_code: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    qx = db.query(models.Question).filter(
        models.Question.survey_id == survey_id,
        models.Question.code == x_code,
    ).first()
    qy = db.query(models.Question).filter(
        models.Question.survey_id == survey_id,
        models.Question.code == y_code,
    ).first()
    if not qx or not qy:
        raise HTTPException(status_code=404, detail="Question X ou Y introuvable")

    from sqlalchemy import and_
    ax = models.Answer.__table__.alias("ax")
    ay = models.Answer.__table__.alias("ay")

    rows = (
        db.query(ax.c.value, ay.c.value)
        .select_from(ax)
        .join(ay, and_(ax.c.response_id == ay.c.response_id,
                       ay.c.question_id == qy.id))
        .filter(ax.c.question_id == qx.id)
        .all()
    )

    xs, ys = [], []
    for xv, yv in rows:
        try:
            xs.append(float(xv))
            ys.append(float(yv))
        except (TypeError, ValueError):
            continue

    if len(xs) < 3:
        return {"error": "Pas assez de données", "n": len(xs)}

    xs = np.array(xs)
    ys = np.array(ys)

    # Régression linéaire simple : y = a*x + b
    slope, intercept, r_value, p_value, std_err = sps.linregress(xs, ys)

    y_pred = slope * xs + intercept
    ss_res = np.sum((ys - y_pred) ** 2)
    ss_tot = np.sum((ys - np.mean(ys)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    return {
        "x": x_code,
        "y": y_code,
        "n": len(xs),
        "slope": float(slope),
        "intercept": float(intercept),
        "r_squared": float(r_squared),
        "p_value": float(p_value),
        "std_err": float(std_err),
        "equation": f"{y_code} = {slope:.4f} * {x_code} + {intercept:.4f}",
    }


# ============================================================
# 4. Liste des questions d'une enquête (pour l'UI)
# ============================================================
@router.get("/questions/{survey_id}")
def list_questions_for_analysis(
    survey_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    qs = db.query(models.Question).filter(
        models.Question.survey_id == survey_id
    ).order_by(models.Question.order_index).all()
    return {
        "count": len(qs),
        "questions": [
            {"code": q.code, "label": q.label, "type": q.question_type}
            for q in qs
        ],
    }