"""Page 8 : Analyse Statistique — descriptives, bivariée, régression."""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

from api_client import get_client


def render():
    st.subheader("📊 Analyse Statistique & Reporting")
    st.caption("Exécutez des analyses sur les données collectées.")

    client = get_client()

    # --- Sélection de l'enquête ---
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

    # --- Récupérer les questions ---
    questions_data, err = client.analysis_questions(survey_id)
    if err:
        st.error(f"Erreur questions : {err}")
        return

    questions = questions_data.get("questions", [])
    if not questions:
        st.warning("Aucune question dans cette enquête.")
        return

    question_codes = [q["code"] for q in questions]
    question_labels = {q["code"]: q["label"] for q in questions}

    # --- Bouton pour générer des données de test ---
    with st.expander("🧪 Générer des données de test", expanded=False):
        st.caption("Génère 200 réponses fictives cohérentes (age, genre, satisfaction).")
        if st.button("Générer 200 réponses"):
            data, err = client.seed_responses(survey_id, count=200)
            if err:
                st.error(f"❌ {err}")
            else:
                st.success(f"✅ {data['count']} réponses générées")
                st.rerun()

    st.markdown("---")

    # --- Onglets ---
    tab1, tab2, tab3 = st.tabs(["📈 Descriptives", "🔗 Bivariée", "📉 Régression"])

    # === Onglet 1 : Descriptives ===
    with tab1:
        st.markdown("#### Analyse univariée")
        q_code = st.selectbox("Question", question_codes,
                              format_func=lambda c: f"{c} — {question_labels[c]}",
                              key="desc_q")
        if st.button("Lancer l'analyse descriptive"):
            data, err = client.descriptive(survey_id, q_code)
            if err:
                st.error(f"❌ {err}")
            elif data.get("type") == "numeric":
                cols = st.columns(4)
                cols[0].metric("N", data["count"])
                cols[1].metric("Moyenne", f"{data['mean']:.2f}")
                cols[2].metric("Médiane", f"{data['median']:.2f}")
                cols[3].metric("Écart-type", f"{data['std']:.2f}")

                cols2 = st.columns(4)
                cols2[0].metric("Min", f"{data['min']:.0f}")
                cols2[1].metric("Q1", f"{data['q1']:.0f}")
                cols2[2].metric("Q3", f"{data['q3']:.0f}")
                cols2[3].metric("Max", f"{data['max']:.0f}")

                # Petit graphique
                df = pd.DataFrame({
                    "Stat": ["Moyenne", "Médiane", "Q1", "Q3"],
                    "Valeur": [data["mean"], data["median"], data["q1"], data["q3"]],
                })
                fig = px.bar(df, x="Stat", y="Valeur", title="Résumé")
                st.plotly_chart(fig, use_container_width=True)
            elif data.get("type") == "categorical":
                st.metric("N", data["count"])
                df = pd.DataFrame(data["frequencies"])
                fig = px.bar(df, x="value", y="count",
                             text="percent", title="Distribution")
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info(data.get("message", "Aucune donnée"))

    # === Onglet 2 : Bivariée ===
    with tab2:
        st.markdown("#### Corrélation entre deux variables numériques")
        col1, col2 = st.columns(2)
        with col1:
            x_code = st.selectbox("Variable X", question_codes, key="biv_x")
        with col2:
            y_code = st.selectbox("Variable Y", question_codes,
                                  index=min(1, len(question_codes) - 1), key="biv_y")

        if st.button("Calculer la corrélation"):
            data, err = client.bivariate(survey_id, x_code, y_code)
            if err:
                st.error(f"❌ {err}")
            elif "error" in data:
                st.warning(data["error"])
            else:
                cols = st.columns(3)
                cols[0].metric("N", data["n"])
                cols[1].metric("Pearson r", f"{data['pearson']['r']:.3f}",
                               help=f"p-value = {data['pearson']['p_value']:.4f}")
                cols[2].metric("Spearman ρ", f"{data['spearman']['rho']:.3f}",
                               help=f"p-value = {data['spearman']['p_value']:.4f}")

                st.info(
                    f"**Interprétation** : corrélation "
                    f"{'positive' if data['pearson']['r'] > 0 else 'négative'} "
                    f"{'significative' if data['pearson']['p_value'] < 0.05 else 'non significative'} "
                    f"(p = {data['pearson']['p_value']:.4f})"
                )

    # === Onglet 3 : Régression ===
    with tab3:
        st.markdown("#### Régression linéaire simple")
        col1, col2 = st.columns(2)
        with col1:
            x_reg = st.selectbox("Variable explicative (X)", question_codes, key="reg_x")
        with col2:
            y_reg = st.selectbox("Variable expliquée (Y)", question_codes,
                                 index=min(1, len(question_codes) - 1), key="reg_y")

        if st.button("Lancer la régression"):
            data, err = client.regression(survey_id, x_reg, y_reg)
            if err:
                st.error(f"❌ {err}")
            elif "error" in data:
                st.warning(data["error"])
            else:
                st.success(f"**Équation** : `{data['equation']}`")
                cols = st.columns(4)
                cols[0].metric("N", data["n"])
                cols[1].metric("Pente", f"{data['slope']:.4f}")
                cols[2].metric("R²", f"{data['r_squared']:.4f}")
                cols[3].metric("p-value", f"{data['p_value']:.4f}")

                st.info(
                    f"Le modèle explique **{data['r_squared']*100:.1f}%** de la variance de "
                    f"`{y_reg}`. Le coefficient est "
                    f"{'significatif' if data['p_value'] < 0.05 else 'non significatif'}."
                )