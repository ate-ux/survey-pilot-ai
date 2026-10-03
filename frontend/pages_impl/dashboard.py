"""Page 1 : Dashboard Super Admin."""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

from api_client import get_client


def render():
    st.subheader("👑 Dashboard Super Admin")
    st.caption("Vue consolidée de l'ensemble de la plateforme SurveyPilot AI.")

    client = get_client()

    # KPIs
    kpis, err = client.kpis()
    if err:
        st.error(f"Erreur KPIs : {err}")
        kpis = {"projets_actifs": 0, "enquetes_en_cours": 0,
                "enqueteurs_deployes": 0, "donnees_collectees": 0}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Projets Actifs", kpis["projets_actifs"])
    c2.metric("Enquêtes en cours", kpis["enquetes_en_cours"])
    c3.metric("Enquêteurs déployés", kpis["enqueteurs_deployes"])
    c4.metric("Données collectées", f"{kpis['donnees_collectees']:,}")

    st.markdown("---")

    # --- Progression de la collecte (7 derniers jours) ---
    st.markdown("### 📈 Progression de la Collecte (7 derniers jours)")

    responses, err = client.list_responses()
    if err or not responses or responses.get("count", 0) == 0:
        st.info("Aucune donnée collectée pour l'instant.")
        # Fallback : simulation locale
        df = pd.DataFrame({
            "Jour": pd.date_range(end=pd.Timestamp.today(), periods=7),
            "Collectes": np.random.randint(50, 300, size=7),
        }).set_index("Jour")
    else:
        # Compter les réponses par jour
        raw = responses.get("responses", [])
        if raw:
            df = pd.DataFrame(raw)
            if "collected_at" in df.columns:
                df["collected_at"] = pd.to_datetime(df["collected_at"])
                df = df.set_index("collected_at").resample("D").size().reset_index(name="Collectes")
                df.columns = ["Jour", "Collectes"]
                df = df.set_index("Jour").tail(7)
            else:
                df = pd.DataFrame({"Collectes": [len(raw)]},
                                  index=[pd.Timestamp.today()])
        else:
            df = pd.DataFrame({"Collectes": [0]}, index=[pd.Timestamp.today()])

    fig = px.line(df, y="Collectes", markers=True, title="")
    fig.update_layout(
        height=300, margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="", yaxis_title="Réponses collectées",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # --- Journal d'audit récent ---
    st.markdown("### 📋 Activité récente (audit)")

    audit, err = client.list_audit(limit=10)
    if err:
        st.warning(f"Audit indisponible : {err}")
    elif audit.get("count", 0) == 0:
        st.info("Aucune activité enregistrée.")
    else:
        rows = []
        for e in audit["entries"]:
            rows.append({
                "Date": e.get("created_at", "")[:19].replace("T", " "),
                "Action": e.get("action", ""),
                "Entité": f"{e.get('entity_type', '')}#{e.get('entity_id', '')}",
                "Utilisateur": e.get("user_id", ""),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)