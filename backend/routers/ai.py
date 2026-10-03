"""
Endpoints pour les agents IA + workflow de validation.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from auth import require_user
from schemas import ProposalCreate, ProposalDecision, ProposalOut
from agents import methodologue_agent, echantillonneur_agent
import models

router = APIRouter(prefix="/api/ai", tags=["ai"])


# ============================================================
# Helpers
# ============================================================
def _log_audit(db, user_id, action, entity_type=None, entity_id=None, details=None):
    db.add(models.AuditLog(
        user_id=user_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        details=details,
    ))
    db.commit()


def _agent_by_code(db: Session, code: str):
    return db.query(models.AIAgent).filter(models.AIAgent.code == code).first()


def _create_proposal(db, user_id, proposal_type, payload,
                     project_id=None, survey_id=None, ai_code=None):
    proposal = models.Proposal(
        project_id=project_id,
        survey_id=survey_id,
        proposal_type=proposal_type,
        payload=payload,
        status="pending",
        proposed_by=user_id,
        proposed_by_ai=bool(ai_code),
    )
    db.add(proposal)
    db.flush()

    # Tracer l'action de l'agent
    if ai_code:
        agent = _agent_by_code(db, ai_code)
        if agent:
            db.add(models.AIAction(
                agent_id=agent.id,
                proposal_id=proposal.id,
                action_type=proposal_type,
                input_data={"survey_id": survey_id, "project_id": project_id},
                output_data=payload,
            ))

    db.commit()
    db.refresh(proposal)
    return proposal


# ============================================================
# Liste des agents (déjà dans main.py, mais on en ajoute un dédié)
# ============================================================
@router.get("/agents")
def list_agents(db: Session = Depends(get_db),
                user: models.User = Depends(require_user)):
    agents = db.query(models.AIAgent).all()
    return {
        "count": len(agents),
        "agents": [
            {
                "id": a.id, "code": a.code, "name": a.name,
                "agent_type": a.agent_type,
                "autonomy_level": a.autonomy_level,
                "is_enabled": a.is_enabled,
            }
            for a in agents
        ],
    }


# ============================================================
# Agent Méthodologue : propose un plan de sondage
# ============================================================
@router.post("/methodologue/propose/{survey_id}")
def methodologue_propose(
    survey_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    proposal_data = methodologue_agent.propose_plan({
        "target_population": survey.target_population,
        "sample_size": survey.sample_size,
    })

    proposal = _create_proposal(
        db, user.id,
        proposal_type="methodologue.plan",
        payload=proposal_data,
        project_id=survey.project_id,
        survey_id=survey.id,
        ai_code="methodologue",
    )

    _log_audit(db, user.id, "ai.methodologue.propose", "proposal", proposal.id,
               {"survey_id": survey_id})

    return {
        "status": "pending",
        "proposal_id": proposal.id,
        "agent": methodologue_agent.name,
        "proposal": proposal_data,
    }


# ============================================================
# Agent Échantillonneur : propose une taille d'échantillon
# ============================================================
@router.post("/echantillonneur/propose/{survey_id}")
def echantillonneur_propose(
    survey_id: int,
    confidence: float = 0.95,
    margin: float = 0.05,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    target = survey.target_population or 1000
    proposal_data = echantillonneur_agent.propose_sample_size(
        target_population=target,
        confidence_level=confidence,
        margin_error=margin,
    )

    proposal = _create_proposal(
        db, user.id,
        proposal_type="echantillonneur.sample_size",
        payload=proposal_data,
        project_id=survey.project_id,
        survey_id=survey.id,
        ai_code="echantillonneur",
    )

    _log_audit(db, user.id, "ai.echantillonneur.propose", "proposal", proposal.id,
               {"survey_id": survey_id})

    return {
        "status": "pending",
        "proposal_id": proposal.id,
        "agent": echantillonneur_agent.name,
        "proposal": proposal_data,
    }


# ============================================================
# Liste des propositions
# ============================================================
@router.get("/proposals")
def list_proposals(
    status: str = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    q = db.query(models.Proposal)
    if status:
        q = q.filter(models.Proposal.status == status)
    proposals = q.order_by(models.Proposal.id.desc()).all()
    return {
        "count": len(proposals),
        "proposals": [
            {
                "id": p.id,
                "proposal_type": p.proposal_type,
                "status": p.status,
                "proposed_by_ai": p.proposed_by_ai,
                "project_id": p.project_id,
                "survey_id": p.survey_id,
                "payload": p.payload,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in proposals
        ],
    }


# ============================================================
# Décision : approuver ou refuser une proposition
# ============================================================
@router.post("/proposals/{proposal_id}/decide")
def decide_proposal(
    proposal_id: int,
    payload: ProposalDecision,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    proposal = db.query(models.Proposal).filter(models.Proposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposition introuvable")

    if proposal.status != "pending":
        raise HTTPException(status_code=400, detail=f"Proposition déjà {proposal.status}")

    if payload.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="decision doit être 'approved' ou 'rejected'")

    proposal.status = payload.decision
    proposal.decided_by = user.id
    proposal.decision_note = payload.decision_note
    proposal.decided_at = datetime.utcnow()

    # Si approuvé et c'est un plan d'échantillonnage → appliquer à l'enquête
    if payload.decision == "approved" and proposal.survey_id:
        survey = db.query(models.Survey).filter(models.Survey.id == proposal.survey_id).first()
        if survey and proposal.proposal_type == "echantillonneur.sample_size":
            survey.sample_size = proposal.payload.get("calculated_sample_size", survey.sample_size)
        elif survey and proposal.proposal_type == "methodologue.plan":
            survey.sample_size = proposal.payload.get("sample_size", survey.sample_size)

    db.commit()
    db.refresh(proposal)

    _log_audit(db, user.id, f"proposal.{payload.decision}", "proposal", proposal.id,
               {"note": payload.decision_note})

    return {
        "status": "decided",
        "proposal_id": proposal.id,
        "decision": proposal.status,
        "decided_at": proposal.decided_at.isoformat(),
    }


# ============================================================
# Journal des actions des agents IA
# ============================================================
@router.get("/actions")
def list_ai_actions(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    actions = (
        db.query(models.AIAction)
        .order_by(models.AIAction.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "count": len(actions),
        "actions": [
            {
                "id": a.id,
                "agent_id": a.agent_id,
                "proposal_id": a.proposal_id,
                "action_type": a.action_type,
                "input_data": a.input_data,
                "output_data": a.output_data,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in actions
        ],
    }