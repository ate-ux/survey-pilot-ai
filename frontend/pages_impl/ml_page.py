"""Page ML — Détection d'anomalies et prédiction."""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

from api_client import get_client


def render():
    st.subheader("🤖 Machine Learning")
    st.caption("Modèles ML appliqués à vos données d'enquête : détection d'anomalies, prédiction, profilage.")

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

    st.markdown("---")

    # Onglets
    tab1, tab2, tab3 = st.tabs([
        "🚨 Détection d'anomalies (Isolation Forest)",
        "📉 Prédiction de non-réponse (Random Forest)",
        "📊 Profil des données",
    ])

    # === Onglet 1 : Isolation Forest ===
    with tab1:
        st.markdown("### 🚨 Isolation Forest — détection d'anomalies")
        st.markdown(
            "L'**Isolation Forest** est un algorithme **non supervisé** qui isole les "
            "observations aberrantes en construisant des arbres aléatoires. "
            "Il détecte les réponses qui s'écartent du comportement moyen."
        )

        col1, col2 = st.columns([1, 2])
        with col1:
            contamination = st.slider(
                "Contamination attendue (%)",
                min_value=1, max_value=30, value=5, step=1,
            ) / 100
        with col2:
            st.caption(
                f"Le modèle considérera environ **{int(contamination*100)}%** "
                "des réponses comme anormales."
            )

        if st.button("🚀 Lancer la détection", use_container_width=True, key="if_btn"):
            with st.spinner("Entraînement de l'Isolation Forest..."):
                data, err = client.detect_anomalies(survey_id, contamination)
            if err:
                st.error(f"❌ {err}")
            else:
                st.success(
                    f"✅ **{data['n_anomalies']} anomalies détectées** "
                    f"sur {data['n_samples']} réponses ({data['anomaly_percentage']}%)"
                )
                st.info(data["interpretation"])

                col1, col2, col3 = st.columns(3)
                col1.metric("N réponses", data["n_samples"])
                col2.metric("N anomalies", data["n_anomalies"])
                col3.metric("% anomalies", f"{data['anomaly_percentage']}%")

                anomalies = data.get("anomalies", [])
                if anomalies:
                    df = pd.DataFrame(anomalies)
                    df["anomaly_score"] = df["anomaly_score"].round(4)

                    # Graphique : distribution des scores
                    fig = px.histogram(
                        df, x="anomaly_score", nbins=20,
                        title="Distribution des scores d'anomalie",
                        labels={"anomaly_score": "Score (plus négatif = plus anormal)"},
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # Tableau
                    st.markdown("#### 🔍 Détail des anomalies")
                    display_df = df[["response_id", "anomaly_score"]].copy()
                    display_df.columns = ["ID Réponse", "Score d'anomalie"]
                    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # === Onglet 2 : Random Forest ===
    with tab2:
        st.markdown("### 📉 Random Forest — Prédiction de non-réponse")
        st.markdown(
            "Un **Random Forest** est un ensemble d'arbres de décision. "
            "Ici, il apprend à prédire quelles réponses seront **incomplètes** "
            "à partir des patterns observés."
        )

        if st.button("🚀 Entraîner le modèle", use_container_width=True, key="rf_btn"):
            with st.spinner("Entraînement du Random Forest..."):
                data, err = client.predict_nonresponse(survey_id)
            if err:
                st.error(f"❌ {err}")
            else:
                st.success("✅ Modèle entraîné et évalué")
                st.info(data["interpretation"])

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Accuracy", f"{data['accuracy']*100:.1f}%")
                col2.metric("Precision", f"{data['precision']*100:.1f}%")
                col3.metric("Recall", f"{data['recall']*100:.1f}%")
                col4.metric("F1-Score", f"{data['f1_score']*100:.1f}%")

                # Feature importance
                fi = pd.DataFrame(data["feature_importance"])
                if not fi.empty:
                    fig = px.bar(
                        fi.head(10), x="importance", y="feature",
                        orientation="h",
                        title="Top 10 des variables les plus prédictives",
                    )
                    fig.update_layout(yaxis=dict(autorange="reversed"))
                    st.plotly_chart(fig, use_container_width=True)

    # === Onglet 3 : Profil ===
    with tab3:
        st.markdown("### 📊 Profil des données")
        st.caption("Vue synthétique : taux de remplissage, moyennes, écarts-types.")

        if st.button("🚀 Générer le profil", use_container_width=True, key="prof_btn"):
            with st.spinner("Analyse..."):
                data, err = client.data_profile(survey_id)
            if err:
                st.error(f"❌ {err}")
            else:
                st.success(f"✅ {data['n_responses']} réponses, {data['n_questions']} questions")

                df = pd.DataFrame(data["profile"])
                st.dataframe(df, use_container_width=True, hide_index=True)

                # Graphique taux de remplissage
                if not df.empty:
                    fig = px.bar(
                        df, x="code", y="fill_rate",
                        title="Taux de remplissage par question (%)",
                        labels={"fill_rate": "% répondu", "code": "Question"},
                    )
                    fig.update_yaxes(range=[0, 100])
                    st.plotly_chart(fig, use_container_width=True)