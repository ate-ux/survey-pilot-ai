"""
Module ML — Détection d'anomalies et prédiction de non-réponse.
Utilise scikit-learn (Isolation Forest + Random Forest).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

from database import get_db
from auth import require_user
import models

router = APIRouter(prefix="/api/ml", tags=["ml"])


def _log_audit(db, user_id, action, entity_type=None, entity_id=None, details=None):
    db.add(models.AuditLog(
        user_id=user_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        details=details,
    ))
    db.commit()


def _build_feature_matrix(db: Session, survey_id: int):
    """
    Construit une matrice [n_responses x n_questions] où chaque cellule
    est la valeur encodée numériquement.
    Retourne (X, response_ids, feature_names).
    """
    questions = (
        db.query(models.Question)
        .filter(models.Question.survey_id == survey_id)
        .order_by(models.Question.order_index)
        .all()
    )
    if not questions:
        return None, None, None

    # Récupérer toutes les réponses
    responses = (
        db.query(models.Response)
        .filter(models.Response.survey_id == survey_id)
        .all()
    )
    if len(responses) < 10:
        return None, None, None

    response_ids = [r.id for r in responses]
    q_codes = [q.code for q in questions]
    q_ids = [q.id for q in questions]

    # Map réponse_id -> {question_id: valeur}
    answers = (
        db.query(models.Answer)
        .filter(models.Answer.question_id.in_(q_ids))
        .all()
    )
    ans_map = {}
    for a in answers:
        ans_map.setdefault(a.response_id, {})[a.question_id] = a.value

    # Encoder les valeurs
    # Détecter les questions numériques vs catégorielles
    encoded_categories = {}  # question_id -> {valeur: code}

    # Première passe : construire la matrice brute
    rows = []
    for rid in response_ids:
        row = []
        for q in questions:
            val = ans_map.get(rid, {}).get(q.id, None)
            if val is None:
                row.append(np.nan)
                continue
            # Essayer de convertir en float
            try:
                row.append(float(val))
            except (ValueError, TypeError):
                # Encoder la catégorie
                cat_map = encoded_categories.setdefault(q.id, {})
                if val not in cat_map:
                    cat_map[val] = len(cat_map) + 1
                row.append(float(cat_map[val]))
        rows.append(row)

    X = np.array(rows, dtype=float)
    # Remplacer les NaN par la moyenne de la colonne
    col_means = np.nanmean(X, axis=0)
    inds = np.where(np.isnan(X))
    X[inds] = np.take(col_means, inds[1])

    return X, response_ids, q_codes


# ============================================================
# 1. Détection d'anomalies avec Isolation Forest
# ============================================================
@router.get("/detect-anomalies/{survey_id}")
def detect_anomalies(
    survey_id: int,
    contamination: float = 0.05,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    """
    Détecte les réponses anormales (suspectes) avec Isolation Forest.
    - contamination : proportion attendue d'anomalies (0.05 = 5%)
    """
    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    X, response_ids, feature_names = _build_feature_matrix(db, survey_id)
    if X is None or len(X) < 10:
        raise HTTPException(
            status_code=400,
            detail="Pas assez de données (< 10 réponses) pour lancer la détection"
        )

    if contamination < 0.01 or contamination > 0.5:
        raise HTTPException(status_code=400, detail="contamination doit être entre 0.01 et 0.5")

    # Standardiser
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Isolation Forest
    model = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=100,
    )
    predictions = model.fit_predict(X_scaled)  # -1 = anomalie, 1 = normal
    scores = model.score_samples(X_scaled)     # plus négatif = plus anormal

    anomalies = []
    for i, (rid, pred, score) in enumerate(zip(response_ids, predictions, scores)):
        if pred == -1:
            anomalies.append({
                "response_id": int(rid),
                "anomaly_score": float(score),
                "feature_values": X[i].tolist(),
            })

    # Trier par score croissant (les plus anormaux d'abord)
    anomalies.sort(key=lambda x: x["anomaly_score"])

    _log_audit(db, user.id, "ml.detect_anomalies", "survey", survey_id,
               {"total": len(X), "anomalies": len(anomalies), "contamination": contamination})

    return {
        "survey_id": survey_id,
        "method": "Isolation Forest",
        "n_samples": len(X),
        "contamination": contamination,
        "n_anomalies": len(anomalies),
        "anomaly_percentage": round(len(anomalies) / len(X) * 100, 2),
        "feature_names": feature_names,
        "anomalies": anomalies[:50],  # max 50 pour la réponse
        "interpretation": (
            f"{len(anomalies)} réponses suspectes détectées sur {len(X)} "
            f"({len(anomalies)/len(X)*100:.1f}%). "
            "Ces réponses s'écartent du comportement moyen et méritent vérification."
        ),
    }


# ============================================================
# 2. Prédiction de non-réponse (classification binaire)
# ============================================================
@router.get("/predict-nonresponse/{survey_id}")
def predict_nonresponse(
    survey_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    """
    Entraîne un Random Forest pour prédire quelles réponses sont 'incomplètes'.
    Objectif démo : montrer un pipeline ML supervisé complet.
    """
    X, response_ids, feature_names = _build_feature_matrix(db, survey_id)
    if X is None or len(X) < 20:
        raise HTTPException(
            status_code=400,
            detail="Pas assez de données (< 20 réponses)"
        )

    # Construire la cible : 1 si la réponse a au moins un NaN original (incomplet)
    # On reconstruit la cible en regardant les NaN avant imputation
    questions = (
        db.query(models.Question)
        .filter(models.Question.survey_id == survey_id)
        .all()
    )
    q_ids = [q.id for q in questions]
    answers = (
        db.query(models.Answer)
        .filter(models.Answer.question_id.in_(q_ids))
        .all()
    )
    ans_by_resp = {}
    for a in answers:
        ans_by_resp.setdefault(a.response_id, set()).add(a.question_id)

    y = []
    for rid in response_ids:
        answered = len(ans_by_resp.get(rid, set()))
        # Cible : 1 si moins de 80% des questions répondues
        y.append(1 if answered < 0.8 * len(questions) else 0)
    y = np.array(y)

    # Vérifier qu'il y a au moins 2 classes
    if len(np.unique(y)) < 2:
        # Forcer un cas synthétique : les 20% avec le moins de réponses
        counts = np.array([len(ans_by_resp.get(rid, set())) for rid in response_ids])
        threshold = np.percentile(counts, 20)
        y = (counts <= threshold).astype(int)

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y if len(np.unique(y)) > 1 else None
    )

    # Random Forest
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)

    # Feature importance
    importances = model.feature_importances_
    feature_importance = sorted(
        [{"feature": f, "importance": float(imp)}
         for f, imp in zip(feature_names, importances)],
        key=lambda x: -x["importance"]
    )

    _log_audit(db, user.id, "ml.predict_nonresponse", "survey", survey_id,
               {"n_train": len(X_train), "n_test": len(X_test)})

    return {
        "survey_id": survey_id,
        "method": "Random Forest Classifier",
        "n_train": len(X_train),
        "n_test": len(X_test),
        "classes": {0: "Complet", 1: "Incomplet"},
        "accuracy": round(report.get("accuracy", 0), 3),
        "precision": round(report.get("weighted avg", {}).get("precision", 0), 3),
        "recall": round(report.get("weighted avg", {}).get("recall", 0), 3),
        "f1_score": round(report.get("weighted avg", {}).get("f1-score", 0), 3),
        "feature_importance": feature_importance,
        "interpretation": (
            f"Modèle entraîné sur {len(X_train)} réponses, testé sur {len(X_test)}. "
            f"Accuracy : {report.get('accuracy', 0)*100:.1f}%. "
            f"Les questions les plus prédictives sont : "
            f"{', '.join([f['feature'] for f in feature_importance[:3]])}."
        ),
    }


# ============================================================
# 3. Statistiques descriptives multi-variables
# ============================================================
@router.get("/profile/{survey_id}")
def data_profile(
    survey_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    """Profil rapide des données : moyennes, écarts-types, taux de remplissage."""
    questions = (
        db.query(models.Question)
        .filter(models.Question.survey_id == survey_id)
        .order_by(models.Question.order_index)
        .all()
    )
    responses_count = (
        db.query(models.Response)
        .filter(models.Response.survey_id == survey_id)
        .count()
    )

    profile = []
    for q in questions:
        values = (
            db.query(models.Answer.value)
            .join(models.Response, models.Response.id == models.Answer.response_id)
            .filter(models.Response.survey_id == survey_id)
            .filter(models.Answer.question_id == q.id)
            .all()
        )
        raw = [v[0] for v in values if v[0] is not None]
        numeric = []
        for v in raw:
            try:
                numeric.append(float(v))
            except (ValueError, TypeError):
                pass

        entry = {
            "code": q.code,
            "label": q.label,
            "type": q.question_type,
            "n_answered": len(raw),
            "fill_rate": round(len(raw) / responses_count * 100, 2) if responses_count > 0 else 0,
        }
        if len(numeric) >= len(raw) * 0.7 and numeric:
            arr = np.array(numeric)
            entry.update({
                "mean": round(float(arr.mean()), 2),
                "std": round(float(arr.std(ddof=1)) if len(arr) > 1 else 0, 2),
                "min": round(float(arr.min()), 2),
                "max": round(float(arr.max()), 2),
            })
        profile.append(entry)

    return {
        "survey_id": survey_id,
        "n_responses": responses_count,
        "n_questions": len(questions),
        "profile": profile,
    }