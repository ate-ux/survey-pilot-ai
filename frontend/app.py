import streamlit as st
import requests
import pandas as pd
import numpy as np
import os

st.set_page_config(
    page_title="SurveyPilot AI V2",
    layout="wide",
    initial_sidebar_state="expanded",
)

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")

# --- Sidebar ---
st.sidebar.title("SurveyPilot AI - V2")
st.sidebar.markdown("**Aller à :**")

modules = [
    "Dashboard Super Admin",
    "Projets",
    "Orchestrateur IA",
    "Base de Connaissances",
    "Échantillonnage",
    "Supervision Enquêteurs",
    "Données & Anomalies (CAP)",
    "Analyse Statistique",
    "Sandbox",
    "Approbations",
]
choix = st.sidebar.radio("Navigation", modules, label_visibility="collapsed")

st.title("SurveyPilot AI - V2")

# --- Dashboard ---
if choix == "Dashboard Super Admin":
    st.subheader("👑 Dashboard Super Admin")
    st.caption("Vue consolidée de l'ensemble de la plateforme SurveyPilot AI.")

    try:
        kpis = requests.get(f"{BACKEND_URL}/api/dashboard/kpis", timeout=5).json()
    except Exception:
        kpis = {
            "projets_actifs": 0,
            "enquetes_en_cours": 0,
            "enqueteurs_deployes": 0,
            "donnees_collectees": 0,
        }

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Projets Actifs", kpis["projets_actifs"])
    c2.metric("Enquêtes en cours", kpis["enquetes_en_cours"])
    c3.metric("Enquêteurs déployés", kpis["enqueteurs_deployes"])
    c4.metric("Données collectées", f"{kpis['donnees_collectees']:,}")

    st.markdown("### Progression de la Collecte (7 derniers jours)")

    # Simulation locale (corrige le bug numpy du PDF)
    df = pd.DataFrame(
        {
            "Jour": pd.date_range(end=pd.Timestamp.today(), periods=7),
            "Collectes": np.random.randint(100, 500, size=7),
        }
    ).set_index("Jour")

    st.line_chart(df)

# --- Projets ---
elif choix == "Projets":
    st.subheader("📁 Projets")
    try:
        data = requests.get(f"{BACKEND_URL}/api/projects", timeout=5).json()
        st.dataframe(pd.DataFrame(data["projects"]))
    except Exception as e:
        st.error(f"Backend indisponible : {e}")

# --- Analyse Statistique ---
elif choix == "Analyse Statistique":
    st.subheader("📊 Analyse Statistique & Reporting")
    st.caption("Exécutez des analyses statistiques sur les données collectées (simulation locale).")

    onglet1, onglet2, onglet3 = st.tabs(
        ["Statistiques Descriptives", "Analyse Bivariée", "Régression"]
    )

    with onglet1:
        st.markdown("#### Analyse Univariate")
        variables = st.multiselect(
            "Sélectionnez les variables",
            ["age", "genre", "region", "revenu"],
            default=["age", "genre"],
        )
        if st.button("Lancer l'analyse descriptive"):
            df = pd.DataFrame(
                np.random.randint(18, 70, size=(100, len(variables))),
                columns=variables,
            )
            st.dataframe(df.describe())
            st.bar_chart(df.mean())

    with onglet2:
        st.info("Analyse bivariée — à venir.")

    with onglet3:
        st.info("Modèles de régression — à venir.")

# --- Autres modules (placeholders) ---
else:
    st.subheader(f"🧩 {choix}")
    st.info("Module en cours de développement.")

st.sidebar.markdown("---")
st.sidebar.caption(f"Backend : {BACKEND_URL}")