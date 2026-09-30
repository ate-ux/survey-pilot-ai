from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os

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


@app.get("/")
def read_root():
    return {
        "app": os.getenv("APP_NAME", "SurveyPilot AI"),
        "version": os.getenv("APP_VERSION", "2.0.0"),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "status": "operational",
    }


@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/projects")
def list_projects():
    """Liste des projets (données de démonstration)."""
    return {
        "projects": [
            {"id": 1, "name": "ISSEA", "status": "active"},
            {"id": 2, "name": "Santé", "status": "active"},
            {"id": 3, "name": "Marketing", "status": "active"},
        ]
    }


@app.get("/api/dashboard/kpis")
def dashboard_kpis():
    """KPIs du Dashboard Super Admin."""
    return {
        "projets_actifs": 12,
        "enquetes_en_cours": 7,
        "enqueteurs_deployes": 145,
        "donnees_collectees": 12450,
    }