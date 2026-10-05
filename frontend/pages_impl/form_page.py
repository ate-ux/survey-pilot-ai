"""Page Saisir une réponse — formulaire dynamique."""
import streamlit as st
from datetime import datetime
from api_client import get_client


def render():
    st.subheader("✍️ Saisir une réponse")
    st.caption("Remplissez le formulaire d'enquête. La position GPS peut être capturée automatiquement.")

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
    selected = st.selectbox("Sélectionnez une enquête", list(survey_options.keys()))
    survey_id = survey_options[selected]

    # --- Récupérer la structure du formulaire ---
    form_data, err = client.get_survey_form(survey_id)
    if err:
        st.error(f"Erreur : {err}")
        return

    questions = form_data.get("questions", [])
    if not questions:
        st.warning("Cette enquête n'a aucune question.")
        return

    st.markdown(f"### 📋 {form_data['title']}")
    st.caption(f"{len(questions)} questions · Statut : {form_data['status']}")

    # --- Info complétion ---
    completion, _ = client.get_survey_completion(survey_id)
    if completion:
        col1, col2, col3 = st.columns(3)
        col1.metric("Réponses collectées", completion.get("total_responses", 0))
        col2.metric("Avec GPS", completion.get("responses_with_gps", 0))
        col3.metric("Couverture GPS", f"{completion.get('gps_coverage', 0)}%")

    st.markdown("---")

    # --- Formulaire dynamique ---
    with st.form("dynamic_survey_form"):
        st.markdown("#### 👤 Informations du répondant")

        col1, col2 = st.columns(2)
        with col1:
            respondent_code = st.text_input(
                "Code répondant (optionnel)",
                placeholder="ex : R-2026-0001",
            )
        with col2:
            st.caption("💡 Laissez vide pour générer automatiquement")

        st.markdown("---")
        st.markdown("#### ❓ Questions")

        answers = {}

        for q in questions:
            q_id = q["id"]
            q_code = q["code"]
            q_label = q["label"]
            q_type = q["question_type"]
            q_options = q.get("options")
            required = q.get("is_required", True)

            label_md = f"**{q['order_index']}. {q_label}**"
            if required:
                label_md += " *"

            st.markdown(label_md)

            key = f"q_{q_id}"

            if q_type == "number":
                val = st.number_input(
                    f"Réponse pour {q_code}",
                    key=key,
                    value=0,
                    label_visibility="collapsed",
                )
                answers[q_id] = str(val)

            elif q_type == "select" and q_options:
                val = st.selectbox(
                    f"Choisir pour {q_code}",
                    options=[""] + q_options,
                    key=key,
                    label_visibility="collapsed",
                )
                answers[q_id] = val

            elif q_type == "boolean":
                val = st.radio(
                    f"Réponse pour {q_code}",
                    options=["Oui", "Non"],
                    key=key,
                    horizontal=True,
                    label_visibility="collapsed",
                )
                answers[q_id] = val

            elif q_type == "scale":
                val = st.slider(
                    f"Échelle pour {q_code}",
                    min_value=1, max_value=5, value=3,
                    key=key,
                )
                answers[q_id] = str(val)

            else:  # text par défaut
                val = st.text_input(
                    f"Réponse pour {q_code}",
                    key=key,
                    label_visibility="collapsed",
                )
                answers[q_id] = val

        st.markdown("---")
        st.markdown("#### 📍 Localisation GPS")
        st.caption("Renseignez manuellement les coordonnées ou copiez-les depuis votre téléphone.")

        col1, col2, col3 = st.columns(3)
        with col1:
            latitude = st.number_input("Latitude", value=3.8480, format="%.6f", key="gps_lat")
        with col2:
            longitude = st.number_input("Longitude", value=11.5021, format="%.6f", key="gps_lon")
        with col3:
            gps_accuracy = st.number_input("Précision (m)", value=10.0, format="%.1f", key="gps_acc")

        include_gps = st.checkbox("📍 Inclure la position GPS dans cette réponse", value=True)

        st.markdown("---")

        submitted = st.form_submit_button(
            "💾 Enregistrer la réponse",
            use_container_width=True,
            type="primary",
        )

    # --- Traitement de la soumission ---
    if submitted:
        # Vérifier les champs obligatoires
        missing = []
        for q in questions:
            if q.get("is_required", True):
                val = answers.get(q["id"], "")
                if not val or val == "":
                    missing.append(q["label"])

        if missing:
            st.error(f"❌ Champs obligatoires manquants : {', '.join(missing)}")
            return

        # Construire le payload
        payload = {
            "survey_id": survey_id,
            "respondent_code": respondent_code or None,
            "answers": [
                {"question_id": qid, "value": str(val)}
                for qid, val in answers.items()
                if val != "" and val is not None
            ],
            "latitude": latitude if include_gps else None,
            "longitude": longitude if include_gps else None,
            "gps_accuracy": gps_accuracy if include_gps else None,
        }

        result, err = client.submit_full_response(payload)
        if err:
            st.error(f"❌ Erreur : {err}")
        else:
            st.success(f"✅ Réponse #{result['response_id']} enregistrée !")
            st.balloons()
            with st.expander("Voir le détail"):
                st.json(result)