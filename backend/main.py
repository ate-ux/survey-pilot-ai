from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import os

from database import get_db, engine, SessionLocal
import models

from init_admin import ensure_super_admin

# Routeurs
from routers import auth as auth_router
from routers import projects as projects_router
from routers import surveys as surveys_router
from routers import questions as questions_router
from routers import responses as responses_router
from routers import audit as audit_router
from routers import seed as seed_router
from routers import analysis as analysis_router
from routers import ai as ai_router
from routers import sandbox as sandbox_router
from routers import versions as versions_router
from routers import sampling as sampling_router
from routers import knowledge as knowledge_router
from routers import profile as profile_router
from routers import ml as ml_router
from routers import geo as geo_router
from routers import llm as llm_router

app = FastAPI(
    title=os.getenv("APP_NAME", "SurveyPilot AI"),
    version=os.getenv("APP_VERSION", "2.0.0"),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dossier statique pour les avatars
os.makedirs("/app/static/avatars", exist_ok=True)
app.mount("/static", StaticFiles(directory="/app/static"), name="static")


@app.on_event("startup")
def on_startup():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[startup] Connexion DB OK")
        db = SessionLocal()
        try:
            ensure_super_admin(db)
        finally:
            db.close()
    except Exception as e:
        print(f"[startup] Erreur DB: {e}")


# Inclusion des routeurs
app.include_router(auth_router.router)
app.include_router(profile_router.router)
app.include_router(projects_router.router)
app.include_router(surveys_router.router)
app.include_router(questions_router.router)
app.include_router(responses_router.router)
app.include_router(audit_router.router)
app.include_router(seed_router.router)
app.include_router(analysis_router.router)
app.include_router(ai_router.router)
app.include_router(sandbox_router.router)
app.include_router(versions_router.router)
app.include_router(sampling_router.router)
app.include_router(knowledge_router.router)
app.include_router(ml_router.router)
app.include_router(geo_router.router)
app.include_router(llm_router.router)


@app.get("/")
def read_root():
    return {
        "app": os.getenv("APP_NAME", "SurveyPilot AI"),
        "version": os.getenv("APP_VERSION", "2.0.0"),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "status": "operational",
    }


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"
    return {
        "status": "healthy",
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/ai/agents")
def list_ai_agents(db: Session = Depends(get_db)):
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


@app.get("/api/dashboard/kpis")
def dashboard_kpis(db: Session = Depends(get_db)):
    return {
        "projets_actifs": db.query(models.Project).count(),
        "enquetes_en_cours": db.query(models.Survey).count(),
        "enqueteurs_deployes": db.query(models.Interviewer).count(),
        "donnees_collectees": db.query(models.Response).count(),
    }