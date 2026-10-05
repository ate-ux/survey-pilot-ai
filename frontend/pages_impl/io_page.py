"""Page Import/Export - Upload, téléchargement, rapports."""
import streamlit as st
import requests
import os
from api_client import get_client, BACKEND_URL


def render():
    st.subheader("📥 Import / Export")
    st.caption("Importez vos données (CSV, Excel, Word, PDF) et générez vos rapports.")

    client = get_client()

    # Sélection de l'enquête
    surveys_data, err = client.list_surveys()
    if err:
        st.error(f"Erreur : {err}")
        return
    surveys = surveys_data.get("surveys", [])
    if not surveys:
        st.warning("Aucune enquête disponible. Créez-en une d'abord.")
        return

    survey_options = {f"#{s['id']} — {s['code']} : {s['title']}": s["id"] for s in surveys}
    selected = st.selectbox("Enquête cible", list(survey_options.keys()))
    survey_id = survey_options[selected]

    st.markdown("---")

    # ========================================================
    # SECTION 1 : IMPORT
    # ========================================================
    st.markdown("### 📤 Importer des données")

    tab1, tab2, tab3 = st.tabs([
        "📊 Réponses (CSV/Excel)",
        "❓ Questions (Excel/Word/PDF)",
        "📄 Modèles vierges",
    ])

    # --- Onglet 1 : Réponses ---
    with tab1:
        st.markdown("**Importez des réponses** (colonnes = codes des questions)")

        file_type = st.radio("Format", ["CSV", "Excel"], horizontal=True, key="resp_import_type")

        uploaded = st.file_uploader(
            "Fichier de réponses",
            type=["csv"] if file_type == "CSV" else ["xlsx", "xls"],
            key="resp_import_file",
        )

        if uploaded is not None:
            if st.button("📥 Importer les réponses", use_container_width=True):
                with st.spinner("Import en cours..."):
                    endpoint = "csv" if file_type == "CSV" else "excel"
                    files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
                    data = {"survey_id": str(survey_id)}
                    headers = {"Authorization": f"Bearer {st.session_state.token}"}
                    r = requests.post(
                        f"{BACKEND_URL}/api/io/import/responses/{endpoint}",
                        files=files, data=data, headers=headers, timeout=120,
                    )
                    if r.status_code >= 400:
                        try:
                            st.error(f"❌ {r.json().get('detail', r.text)}")
                        except Exception:
                            st.error(f"❌ {r.text}")
                    else:
                        result = r.json()
                        st.success(f"✅ {result['count']} réponses importées")
                        st.balloons()

        # Modèle téléchargeable
        st.markdown("**📄 Télécharger un modèle pour cette enquête :**")
        if st.button("📥 Modèle CSV (colonnes prêtes)", key="dl_template_csv"):
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            r = requests.get(
                f"{BACKEND_URL}/api/io/template/responses/{survey_id}",
                headers=headers, timeout=30,
            )
            if r.status_code == 200:
                st.download_button(
                    "💾 Télécharger",
                    data=r.content,
                    file_name=f"template_survey_{survey_id}.csv",
                    mime="text/csv",
                    key="dl_tpl_csv_btn",
                )
            else:
                st.error("Erreur téléchargement modèle")

    # --- Onglet 2 : Questions ---
    with tab2:
        st.markdown("**Importez des questions pour créer/ajouter à un questionnaire**")

        q_format = st.radio("Format", ["Excel", "Word", "PDF"], horizontal=True, key="q_import_type")

        extensions = {
            "Excel": ["xlsx", "xls"],
            "Word": ["docx"],
            "PDF": ["pdf"],
        }
        uploaded_q = st.file_uploader(
            "Fichier de questions",
            type=extensions[q_format],
            key="q_import_file",
        )

        st.caption({
            "Excel": "Colonnes : code, label, question_type, options (optionnel)",
            "Word": "Paragraphes numérotés (ex : '1. Quel âge avez-vous ?')",
            "PDF": "Même format que Word",
        }[q_format])

        if uploaded_q is not None:
            if st.button("📥 Importer les questions", use_container_width=True):
                with st.spinner("Import en cours..."):
                    endpoint = {
                        "Excel": "excel",
                        "Word": "word",
                        "PDF": "pdf",
                    }[q_format]
                    files = {"file": (uploaded_q.name, uploaded_q.getvalue(), uploaded_q.type)}
                    data = {"survey_id": str(survey_id)}
                    headers = {"Authorization": f"Bearer {st.session_state.token}"}
                    r = requests.post(
                        f"{BACKEND_URL}/api/io/import/questions/{endpoint}",
                        files=files, data=data, headers=headers, timeout=120,
                    )
                    if r.status_code >= 400:
                        try:
                            st.error(f"❌ {r.json().get('detail', r.text)}")
                        except Exception:
                            st.error(f"❌ {r.text}")
                    else:
                        result = r.json()
                        st.success(f"✅ {result['count']} questions importées")
                        st.balloons()

    # --- Onglet 3 : Modèles ---
    with tab3:
        st.markdown("**Téléchargez des modèles vierges**")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Modèle Excel de questions**")
            if st.button("📥 Modèle questions (Excel)", use_container_width=True):
                headers = {"Authorization": f"Bearer {st.session_state.token}"}
                r = requests.get(
                    f"{BACKEND_URL}/api/io/template/questions",
                    headers=headers, timeout=30,
                )
                if r.status_code == 200:
                    st.download_button(
                        "💾 Télécharger questions.xlsx",
                        data=r.content,
                        file_name="template_questions.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_questions_xlsx",
                    )

        with col2:
            st.markdown("**Modèle CSV de réponses**")
            if st.button("📥 Modèle réponses (CSV)", use_container_width=True):
                headers = {"Authorization": f"Bearer {st.session_state.token}"}
                r = requests.get(
                    f"{BACKEND_URL}/api/io/template/responses/{survey_id}",
                    headers=headers, timeout=30,
                )
                if r.status_code == 200:
                    st.download_button(
                        "💾 Télécharger réponses.csv",
                        data=r.content,
                        file_name=f"template_survey_{survey_id}.csv",
                        mime="text/csv",
                        key="dl_resp_csv",
                    )

    st.markdown("---")

    # ========================================================
    # SECTION 2 : EXPORT
    # ========================================================
    st.markdown("### 📥 Exporter les données")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**📊 Réponses (données brutes)**")
        if st.button("Export CSV", use_container_width=True, key="exp_csv"):
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            r = requests.get(
                f"{BACKEND_URL}/api/io/export/responses/csv/{survey_id}",
                headers=headers, timeout=60,
            )
            if r.status_code == 200:
                st.download_button(
                    "💾 Télécharger CSV",
                    data=r.content,
                    file_name=f"responses_survey_{survey_id}.csv",
                    mime="text/csv",
                    key="dl_csv_btn",
                )
            else:
                st.error(f"Erreur {r.status_code}")

        if st.button("Export Excel", use_container_width=True, key="exp_xlsx"):
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            r = requests.get(
                f"{BACKEND_URL}/api/io/export/responses/excel/{survey_id}",
                headers=headers, timeout=60,
            )
            if r.status_code == 200:
                st.download_button(
                    "💾 Télécharger Excel",
                    data=r.content,
                    file_name=f"responses_survey_{survey_id}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_xlsx_btn",
                )
            else:
                st.error(f"Erreur {r.status_code}")

    with col2:
        st.markdown("**📄 Questionnaire vierge**")
        if st.button("Questionnaire Word", use_container_width=True, key="exp_q_docx"):
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            r = requests.get(
                f"{BACKEND_URL}/api/io/export/questions/word/{survey_id}",
                headers=headers, timeout=60,
            )
            if r.status_code == 200:
                st.download_button(
                    "💾 Télécharger Word",
                    data=r.content,
                    file_name=f"questionnaire_{survey_id}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="dl_q_docx",
                )
            else:
                st.error(f"Erreur {r.status_code}")

        if st.button("Questionnaire PDF", use_container_width=True, key="exp_q_pdf"):
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            r = requests.get(
                f"{BACKEND_URL}/api/io/export/questions/pdf/{survey_id}",
                headers=headers, timeout=60,
            )
            if r.status_code == 200:
                st.download_button(
                    "💾 Télécharger PDF",
                    data=r.content,
                    file_name=f"questionnaire_{survey_id}.pdf",
                    mime="application/pdf",
                    key="dl_q_pdf",
                )
            else:
                st.error(f"Erreur {r.status_code}")

    with col3:
        st.markdown("**📊 Rapport d'analyse pro**")
        if st.button("Rapport PDF", use_container_width=True, key="exp_rep_pdf"):
            with st.spinner("Génération du rapport..."):
                headers = {"Authorization": f"Bearer {st.session_state.token}"}
                r = requests.get(
                    f"{BACKEND_URL}/api/io/report/pdf/{survey_id}",
                    headers=headers, timeout=120,
                )
                if r.status_code == 200:
                    st.download_button(
                        "💾 Télécharger rapport PDF",
                        data=r.content,
                        file_name=f"rapport_survey_{survey_id}.pdf",
                        mime="application/pdf",
                        key="dl_rep_pdf",
                    )
                else:
                    st.error(f"Erreur {r.status_code}")

        if st.button("Rapport Word", use_container_width=True, key="exp_rep_docx"):
            with st.spinner("Génération du rapport..."):
                headers = {"Authorization": f"Bearer {st.session_state.token}"}
                r = requests.get(
                    f"{BACKEND_URL}/api/io/report/word/{survey_id}",
                    headers=headers, timeout=120,
                )
                if r.status_code == 200:
                    st.download_button(
                        "💾 Télécharger rapport Word",
                        data=r.content,
                        file_name=f"rapport_survey_{survey_id}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="dl_rep_docx",
                    )
                else:
                    st.error(f"Erreur {r.status_code}")