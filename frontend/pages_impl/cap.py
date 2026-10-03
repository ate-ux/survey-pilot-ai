"""Page 7 : Données & Anomalies (CAP)."""
import streamlit as st
import pandas as pd
from api_client import get_client


def render():
    st.subheader("🔍 Données & Anomalies (CAP)")
    st.caption("Contrôle qualité et détection d'anomalies dans les données collectées.")

    client = get_client()

    # Sélection enquête
    surveys_data, err = client.list_surveys()
    if err:
        st.error(f"Erreur : {err}")
        return
    surveys = surveys_data.get("surveys", [])
    if not surveys:
        st.warning("Aucune enquête disponible.")
        return

    survey_options = {f"#{s['id']} — {s['code']} : {s['title']}": s["id"] for s in surveys}
    selected = st.selectbox("Enquête", list(survey_options.keys()))
    survey_id = survey_options[selected]

    # Récupérer les réponses
    resp_data, err = client.list_responses(survey_id=survey_id)
    if err:
        st.error(f"Erreur : {err}")
        return

    responses = resp_data.get("responses", [])
    st.markdown(f"### 📦 {len(responses)} réponse(s) collectée(s)")

    if not responses:
        st.info("Aucune donnée. Générez des réponses dans la page **Analyse Statistique**.")
        return

    # Stats rapides
    df = pd.DataFrame(responses)
    col1, col2, col3 = st.columns(3)
    col1.metric("Total", len(df))
    if "status" in df.columns:
        col2.metric("Statut principal", df["status"].mode()[0] if len(df["status"].mode()) > 0 else "—")
    if "collected_at" in df.columns:
        df["collected_at"] = pd.to_datetime(df["collected_at"])
        col3.metric("Dernière collecte", df["collected_at"].max().strftime("%d/%m %H:%M"))

    st.markdown("---")

    # --- Détection d'anomalies basique ---
    st.markdown("### 🚨 Détection d'anomalies (règles simples)")

    st.caption("Détection basée sur : doublons de respondent_code, dates suspectes.")

    anomalies = []

    # Doublons
    if "respondent_code" in df.columns:
        dupes = df[df.duplicated("respondent_code", keep=False)]
        if len(dupes) > 0:
            anomalies.append({
                "Type": "Doublons",
                "Description": f"{len(dupes)} réponses avec respondent_code dupliqué",
                "Sévérité": "medium",
            })

    # Réponses très récentes (potentiellement suspectes)
    if "collected_at" in df.columns:
        df["collected_at"] = pd.to_datetime(df["collected_at"])
        cutoff = df["collected_at"].max() - pd.Timedelta(minutes=1)
        recent = df[df["collected_at"] > cutoff]
        if len(recent) > 50:
            anomalies.append({
                "Type": "Collecte trop rapide",
                "Description": f"{len(recent)} réponses collectées dans la même minute",
                "Sévérité": "high",
            })

    if not anomalies:
        st.success("✅ Aucune anomalie détectée avec les règles actuelles.")
    else:
        for a in anomalies:
            icon = "🔴" if a["Sévérité"] == "high" else "🟡"
            st.warning(f"{icon} **{a['Type']}** — {a['Description']} (sévérité : {a['Sévérité']})")

    st.markdown("---")

    # --- Tableau des réponses ---
    st.markdown("### 📊 Aperçu des réponses")
    display_cols = [c for c in ["id", "respondent_code", "status", "collected_at"] if c in df.columns]
    st.dataframe(df[display_cols].head(100), use_container_width=True, hide_index=True)