"""Module Base de Connaissances — articles, guides, best practices."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List

from database import get_db
from auth import require_user
import models

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _log_audit(db, user_id, action, entity_type=None, entity_id=None, details=None):
    db.add(models.AuditLog(
        user_id=user_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        details=details,
    ))
    db.commit()


@router.get("")
def list_entries(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    q = db.query(models.KnowledgeEntry)
    if category:
        q = q.filter(models.KnowledgeEntry.category == category)
    entries = q.order_by(models.KnowledgeEntry.id.desc()).all()
    return {
        "count": len(entries),
        "entries": [
            {
                "id": e.id, "title": e.title, "category": e.category,
                "content": e.content, "tags": e.tags,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ],
    }


@router.post("")
def create_entry(
    title: str,
    content: str,
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    entry = models.KnowledgeEntry(
        title=title,
        content=content,
        category=category,
        tags=tags or [],
        created_by=user.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    _log_audit(db, user.id, "knowledge.create", "knowledge", entry.id,
               {"title": title, "category": category})

    return {
        "status": "created",
        "id": entry.id,
        "title": entry.title,
        "category": entry.category,
    }


@router.get("/{entry_id}")
def get_entry(entry_id: int,
              db: Session = Depends(get_db),
              user: models.User = Depends(require_user)):
    entry = db.query(models.KnowledgeEntry).filter(models.KnowledgeEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entrée introuvable")
    return {
        "id": entry.id, "title": entry.title, "category": entry.category,
        "content": entry.content, "tags": entry.tags,
    }


@router.delete("/{entry_id}")
def delete_entry(entry_id: int,
                 db: Session = Depends(get_db),
                 user: models.User = Depends(require_user)):
    entry = db.query(models.KnowledgeEntry).filter(models.KnowledgeEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entrée introuvable")
    _log_audit(db, user.id, "knowledge.delete", "knowledge", entry.id, {"title": entry.title})
    db.delete(entry)
    db.commit()
    return {"status": "deleted", "id": entry_id}


@router.post("/seed")
def seed_knowledge(db: Session = Depends(get_db),
                   user: models.User = Depends(require_user)):
    """Insère quelques articles de démonstration."""
    samples = [
        {
            "title": "Calcul de la taille d'échantillon",
            "category": "Méthodologie",
            "content": "Pour une population finie N, la formule est : n = (z² × p × (1-p) / e²) / (1 + (n0-1)/N). Utilisez z=1.96 pour 95% de confiance, p=0.5 en l'absence d'information, e=0.05 pour 5% de marge.",
            "tags": ["échantillonnage", "formule", "statistiques"],
        },
        {
            "title": "Bonnes pratiques de collecte terrain",
            "category": "Collecte",
            "content": "1. Former les enquêteurs. 2. Faire un test pilote sur 5% de l'échantillon. 3. Prévoir 10% de sur-échantillonnage pour la non-réponse. 4. Contrôler quotidiennement les données saisies.",
            "tags": ["terrain", "qualité", "enquêteurs"],
        },
        {
            "title": "Détection des anomalies",
            "category": "CAP",
            "content": "Anomalies fréquentes : valeurs hors bornes, réponses identiques en série, temps de saisie trop court. Utilisez des règles de validation à la saisie et post-collecte.",
            "tags": ["contrôle qualité", "anomalies"],
        },
    ]

    created = 0
    for s in samples:
        existing = db.query(models.KnowledgeEntry).filter(
            models.KnowledgeEntry.title == s["title"]).first()
        if existing:
            continue
        db.add(models.KnowledgeEntry(
            title=s["title"], category=s["category"],
            content=s["content"], tags=s["tags"], created_by=user.id,
        ))
        created += 1

    db.commit()

    return {"status": "seeded", "created": created, "total_samples": len(samples)}