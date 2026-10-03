"""Génère des données fictives pour tester l'analyse statistique."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import numpy as np

from database import get_db
from auth import require_user
import models

router = APIRouter(prefix="/api/seed", tags=["seed"])


@router.post("/responses/{survey_id}")
def seed_responses(
    survey_id: int,
    count: int = 200,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    """
    Génère `count` réponses fictives pour l'enquête donnée.
    Suppose que les questions contiennent 'age', 'genre', 'satisfaction' (ou similaires).
    """
    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    questions = db.query(models.Question).filter(
        models.Question.survey_id == survey_id
    ).order_by(models.Question.order_index).all()

    if not questions:
        raise HTTPException(status_code=400, detail="Aucune question pour cette enquête")

    np.random.seed(42)  # reproductible

    # Génération cohérente : age et satisfaction corrélés
    ages = np.random.normal(loc=35, scale=12, size=count).clip(18, 80).astype(int)
    noise = np.random.normal(loc=0, scale=0.8, size=count)

    for i in range(count):
        response = models.Response(
            survey_id=survey_id,
            respondent_code=f"SEED-{i+1:04d}",
            environment_id=1,
        )
        db.add(response)
        db.flush()

        for q in questions:
            code = q.code.lower()
            if "age" in code:
                value = str(ages[i])
            elif "genre" in code or "sexe" in code:
                value = "M" if np.random.rand() < 0.48 else "F"
            elif "satisf" in code:
                # satisfaction dépend légèrement de l'âge (les plus jeunes plus exigeants)
                base = 5 - (ages[i] - 18) * 0.02 + noise[i]
                value = str(int(np.clip(round(base), 1, 5)))
            elif "revenu" in code or "salaire" in code:
                value = str(int(np.clip(np.random.normal(250000, 80000), 50000, 800000)))
            elif "region" in code:
                value = np.random.choice(["Centre", "Littoral", "Ouest", "Nord", "Sud"])
            else:
                value = str(round(np.random.uniform(1, 10), 2))

            db.add(models.Answer(
                response_id=response.id,
                question_id=q.id,
                value=value,
            ))

    db.commit()

    db.add(models.AuditLog(
        user_id=user.id,
        action="seed.responses",
        entity_type="survey",
        entity_id=survey_id,
        details={"count": count},
    ))
    db.commit()

    return {"status": "seeded", "survey_id": survey_id, "count": count}