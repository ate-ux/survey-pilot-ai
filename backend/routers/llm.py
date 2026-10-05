"""Module LLM - Recommandations et interprétations par IA."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import json

from database import get_db
from auth import require_user
from llm_client import ask_llm, is_available, GROQ_MODEL
import models

router = APIRouter(prefix="/api/llm", tags=["llm"])


def _log_audit(db, user_id, action, entity_type=None, entity_id=None, details=None):
    db.add(models.AuditLog(
        user_id=user_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        details=details,
    ))
    db.commit()


# ============================================================
# 1. Vérifier l'état du LLM
# ============================================================
@router.get("/status")
def llm_status(user: models.User = Depends(require_user)):
    return {
        "available": is_available(),
        "provider": "Groq",
        "model": GROQ_MODEL,
    }


# ============================================================
# 2. Recommandations sur une enquête
# ============================================================
@router.post("/recommend/{survey_id}")
def recommend_for_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    if not is_available():
        raise HTTPException(status_code=503, detail="LLM non configuré (GROQ_API_KEY manquante)")

    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    # Récupérer les stats
    nb_responses = db.query(models.Response).filter(
        models.Response.survey_id == survey_id).count()
    nb_questions = db.query(models.Question).filter(
        models.Question.survey_id == survey_id).count()

    # Récupérer les 5 premières questions
    questions = db.query(models.Question).filter(
        models.Question.survey_id == survey_id
    ).order_by(models.Question.order_index).limit(5).all()

    questions_text = "\n".join([
        f"- {q.code} : {q.label} (type: {q.question_type})"
        for q in questions
    ])

    prompt = f"""Analyse cette enquête et propose 5 recommandations concrètes.

**Contexte :**
- Titre : {survey.title}
- Code : {survey.code}
- Population cible : {survey.target_population or "non renseignée"}
- Taille d'échantillon : {survey.sample_size or "non renseignée"}
- Nombre de questions : {nb_questions}
- Nombre de réponses collectées : {nb_responses}

**Questions principales :**
{questions_text or "Aucune question"}

**Ta mission :**
Donne 5 recommandations numérotées pour améliorer cette enquête :
1. Sur la méthodologie (taille échantillon, plan de sondage)
2. Sur les questions (formulation, ordre)
3. Sur la collecte (formation, terrain)
4. Sur l'analyse (méthodes statistiques suggérées)
5. Sur l'interprétation (points d'attention)

Sois concret et opérationnel. Maximum 400 mots."""

    response = ask_llm(prompt, max_tokens=1000)

    if not response:
        raise HTTPException(status_code=500, detail="Erreur LLM")

    # Sauvegarder la recommandation
    rec = models.AIRecommendation(
        survey_id=survey_id,
        recommendation_type="survey_analysis",
        content=response,
        metadata_json={"model": GROQ_MODEL, "nb_responses": nb_responses},
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    _log_audit(db, user.id, "llm.recommend", "survey", survey_id,
               {"rec_id": rec.id})

    return {
        "status": "generated",
        "recommendation_id": rec.id,
        "survey_id": survey_id,
        "model": GROQ_MODEL,
        "recommendation": response,
    }


# ============================================================
# 3. Interpréter les résultats statistiques
# ============================================================
@router.post("/interpret/{survey_id}")
def interpret_results(
    survey_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    if not is_available():
        raise HTTPException(status_code=503, detail="LLM non configuré")

    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    nb_responses = db.query(models.Response).filter(
        models.Response.survey_id == survey_id).count()

    if nb_responses == 0:
        raise HTTPException(status_code=400, detail="Aucune donnée à interpréter")

    # Compter les anomalies
    anomalies_count = db.query(models.Anomaly).count()

    prompt = f"""Voici les résultats d'une enquête. Interprète-les et donne ton analyse.

**Enquête :** {survey.title}
**Nombre de réponses :** {nb_responses}
**Anomalies détectées :** {anomalies_count}

**Ta mission :**
1. Analyse la qualité globale des données
2. Identifie les points forts
3. Identifie les points faibles
4. Recommande des actions concrètes

Maximum 300 mots. Sois synthétique et professionnel."""

    response = ask_llm(prompt, max_tokens=800)

    if not response:
        raise HTTPException(status_code=500, detail="Erreur LLM")

    rec = models.AIRecommendation(
        survey_id=survey_id,
        recommendation_type="result_interpretation",
        content=response,
        metadata_json={"model": GROQ_MODEL, "nb_responses": nb_responses},
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    _log_audit(db, user.id, "llm.interpret", "survey", survey_id,
               {"rec_id": rec.id})

    return {
        "status": "interpreted",
        "recommendation_id": rec.id,
        "survey_id": survey_id,
        "model": GROQ_MODEL,
        "interpretation": response,
    }


# ============================================================
# 4. Lister les recommandations générées
# ============================================================
@router.get("/recommendations")
def list_recommendations(
    survey_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    q = db.query(models.AIRecommendation)
    if survey_id:
        q = q.filter(models.AIRecommendation.survey_id == survey_id)
    recs = q.order_by(models.AIRecommendation.id.desc()).limit(50).all()

    return {
        "count": len(recs),
        "recommendations": [
            {
                "id": r.id,
                "survey_id": r.survey_id,
                "type": r.recommendation_type,
                "content": r.content,
                "metadata": r.metadata_json,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in recs
        ],
    }