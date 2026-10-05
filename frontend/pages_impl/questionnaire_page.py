"""Page Questionnaire - Créer et gérer les questions d'une enquête."""
import streamlit as st
from api_client import get_client


QUESTION_TYPES = {
    "text": "📝 Texte libre",
    "number": "🔢 Nombre",
    "select": "📋 Choix unique",
    "multiselect": "☑️ Choix multiple",
    "boolean": "✅ Oui/Non",
    "date": "📅 Date",
}


def render():
    st.subheader("📋 Questionnaire")
    st.caption("Créez, modifiez et organisez les questions de vos enquêtes.")

    client = get_client()

    # --- Sélection enquête ---
    surveys_data, err = client.list_surveys()
    if err:
        st.error(f"Erreur : {err}")
        return
    surveys = surveys_data.get("surveys", [])
    if not surveys:
        st.warning("Aucune enquête disponible. Créez-en une d'abord dans Projets.")
        return

    survey_options = {f"#{s['id']} — {s['code']} : {s['title']}": s["id"] for s in surveys}
    selected = st.selectbox("Enquête", list(survey_options.keys()), key="q_survey")
    survey_id = survey_options[selected]

    st.markdown("---")

    # --- Charger les questions ---
    data, err = client.list_questions(survey_id)
    if err:
        st.error(f"Erreur : {err}")
        return
    questions = data.get("questions", [])

    # --- KPIs ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Nombre de questions", len(questions))

    if questions:
        nb_required = sum(1 for q in questions if q.get("is_required"))
        types_used = set(q.get("question_type") for q in questions)
        col2.metric("Obligatoires", nb_required)
        col3.metric("Types différents", len(types_used))

    st.markdown("---")

    # ========================================================
    # Onglets
    # ========================================================
    tab1, tab2, tab3 = st.tabs([
        "📝 Liste des questions",
        "➕ Créer une question",
        "👁️ Aperçu du questionnaire",
    ])

    # --------------------------------------------------------
    # Onglet 1 : Liste
    # --------------------------------------------------------
    with tab1:
        if not questions:
            st.info("Aucune question pour l'instant. Utilisez l'onglet « Créer une question ».")
        else:
            st.markdown(f"**{len(questions)} question(s)** — ordre d'apparition :")

            for q in questions:
                with st.container(border=True):
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        type_label = QUESTION_TYPES.get(q["question_type"], q["question_type"])
                        st.markdown(f"**{q['order_index']}. {q['label']}**")
                        st.caption(
                            f"Code : `{q['code']}` · Type : {type_label} · "
                            f"{'Obligatoire' if q.get('is_required') else 'Optionnel'}"
                        )
                        if q.get("options"):
                            st.caption(f"Options : {q['options']}")

                    with col2:
                        if st.button("🗑️", key=f"del_q_{q['id']}", help="Supprimer"):
                            _, err = client.delete_question(q["id"])
                            if err:
                                st.error(err)
                            else:
                                st.success("Question supprimée")
                                st.rerun()

            # Bouton tout supprimer
            with st.expander("⚠️ Zone dangereuse"):
                if st.button("🗑️ Supprimer TOUTES les questions", key="del_all_q"):
                    for q in questions:
                        client.delete_question(q["id"])
                    st.success("Toutes les questions supprimées")
                    st.rerun()

    # --------------------------------------------------------
    # Onglet 2 : Créer une question
    # --------------------------------------------------------
    with tab2:
        with st.form("create_question_form"):
            st.markdown("### Nouvelle question")

            col1, col2 = st.columns(2)
            with col1:
                q_code = st.text_input("Code (unique)", placeholder="ex: age, genre, satisfaction")
            with col2:
                q_type = st.selectbox(
                    "Type de question",
                    options=list(QUESTION_TYPES.keys()),
                    format_func=lambda x: QUESTION_TYPES[x],
                )

            q_label = st.text_area(
                "Question (texte affiché à l'enquêté)",
                placeholder="ex: Quel âge avez-vous ?",
            )

            # Options conditionnelles
            q_options = None
            if q_type in ("select", "multiselect"):
                opts_text = st.text_input(
                    "Options (séparées par des virgules)",
                    placeholder="ex: M,F",
                )
                if opts_text:
                    q_options = [o.strip() for o in opts_text.split(",") if o.strip()]

            q_required = st.checkbox("Question obligatoire", value=True)

            submitted = st.form_submit_button("➕ Créer la question", use_container_width=True)

        if submitted:
            if not q_code or not q_label:
                st.warning("Code et libellé obligatoires.")
            else:
                next_order = max([q["order_index"] for q in questions], default=0) + 1

                data, err = client.create_question(
                    survey_id=survey_id,
                    order_index=next_order,
                    code=q_code.strip(),
                    label=q_label.strip(),
                    question_type=q_type,
                    options=q_options,
                    is_required=q_required,
                )
                if err:
                    st.error(f"❌ {err}")
                else:
                    st.success(f"✅ Question « {q_code} » créée")
                    st.rerun()

    # --------------------------------------------------------
    # Onglet 3 : Aperçu
    # --------------------------------------------------------
    with tab3:
        st.markdown("### 👁️ Aperçu du questionnaire (comme le verra l'enquêté)")

        if not questions:
            st.info("Aucune question à afficher.")
        else:
            for i, q in enumerate(questions, start=1):
                st.markdown(f"**{i}. {q['label']}**")
                if q.get("is_required"):
                    st.caption("*(obligatoire)*")

                q_type = q["question_type"]
                if q_type == "text":
                    st.text_input("Réponse", key=f"preview_text_{q['id']}", disabled=True)
                elif q_type == "number":
                    st.number_input("Réponse", key=f"preview_num_{q['id']}", disabled=True)
                elif q_type == "select" and q.get("options"):
                    st.radio("Choix", q["options"], key=f"preview_sel_{q['id']}", disabled=True)
                elif q_type == "multiselect" and q.get("options"):
                    st.multiselect("Choix multiples", q["options"], key=f"preview_ms_{q['id']}", disabled=True)
                elif q_type == "boolean":
                    st.radio("Réponse", ["Oui", "Non"], key=f"preview_bool_{q['id']}", disabled=True)
                elif q_type == "date":
                    st.date_input("Date", key=f"preview_date_{q['id']}", disabled=True)
                st.markdown("---")