"""Page 5 : Échantillonnage."""
import streamlit as st
import pandas as pd
from api_client import get_client


def render():
    st.subheader("🎯 Échantillonnage")
    st.caption("Plans de sondage et tirages aléatoires.")

    client = get_client()

    # --- Sélection enquête ---
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

    # --- Onglets ---
    tab1, tab2, tab3 = st.tabs(["📋 Plans de l'enquête", "🎲 Tirage aléatoire simple", "🏷️ Tirage stratifié"])

    # === Onglet 1 : Plans existants + création ===
    with tab1:
        st.markdown("#### Créer un plan de sondage")
        with st.form("create_plan"):
            col1, col2 = st.columns(2)
            with col1:
                method = st.selectbox("Méthode",
                                      ["simple_random", "stratified", "exhaustive"])
                sample_size = st.number_input("Taille d'échantillon", min_value=1, value=100)
            with col2:
                confidence = st.slider("Niveau de confiance", 0.90, 0.99, 0.95, 0.01)
                margin = st.slider("Marge d'erreur", 0.01, 0.10, 0.05, 0.01)
            submitted = st.form_submit_button("Créer le plan", use_container_width=True)

        if submitted:
            data, err = client.create_sampling_plan(survey_id, method, int(sample_size), confidence, margin)
            if err:
                st.error(f"❌ {err}")
            else:
                st.success(f"✅ Plan #{data['plan_id']} créé")
                st.rerun()

        st.markdown("---")
        st.markdown("#### Plans existants")
        plans_data, err = client.list_sampling_plans(survey_id)
        if err:
            st.error(f"Erreur : {err}")
        else:
            plans = plans_data.get("plans", [])
            if not plans:
                st.info("Aucun plan pour cette enquête.")
            else:
                df = pd.DataFrame(plans)
                st.dataframe(df, use_container_width=True, hide_index=True)

    # === Onglet 2 : Tirage aléatoire simple ===
    with tab2:
        st.markdown("#### Tirage aléatoire simple")
        col1, col2, col3 = st.columns(3)
        with col1:
            pop_size = st.number_input("Taille population", min_value=10, value=1000, key="pop")
        with col2:
            samp_size = st.number_input("Taille échantillon", min_value=1, value=100, key="samp")
        with col3:
            seed = st.number_input("Seed (optionnel)", min_value=0, value=42, key="seed")

        if st.button("🎲 Lancer le tirage"):
            data, err = client.draw_sample(int(pop_size), int(samp_size), int(seed) if seed else None)
            if err:
                st.error(f"❌ {err}")
            elif "error" in data:
                st.warning(data["error"])
            else:
                st.success(f"✅ {data['sample_size']} individus tirés sur {data['population_size']}")
                st.markdown(f"**Méthode** : `{data['method']}`")
                st.markdown(f"**Note** : {data.get('note', '')}")
                with st.expander("Voir les premiers indices tirés"):
                    st.write(data.get("sample_indices", []))

    # === Onglet 3 : Tirage stratifié ===
    with tab3:
        st.markdown("#### Tirage stratifié")
        st.caption("Saisissez les strates (nom, taille, échantillon).")

        if "strata_rows" not in st.session_state:
            st.session_state.strata_rows = [
                {"name": "Centre", "size": 500, "sample": 50},
                {"name": "Littoral", "size": 300, "sample": 30},
            ]

        # Affichage des strates
        for i, s in enumerate(st.session_state.strata_rows):
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            with col1:
                s["name"] = st.text_input("Nom", value=s["name"], key=f"strata_name_{i}")
            with col2:
                s["size"] = st.number_input("Population", min_value=1, value=s["size"], key=f"strata_size_{i}")
            with col3:
                s["sample"] = st.number_input("Échantillon", min_value=1, value=s["sample"], key=f"strata_sample_{i}")
            with col4:
                if st.button("🗑️", key=f"strata_del_{i}"):
                    st.session_state.strata_rows.pop(i)
                    st.rerun()

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("➕ Ajouter une strate"):
                st.session_state.strata_rows.append({"name": "Nouvelle", "size": 100, "sample": 10})
                st.rerun()
        with col_b:
            if st.button("🚀 Lancer le tirage stratifié", use_container_width=True):
                # Ici on ferait un appel API — pour simplifier on l'affiche localement
                total_sample = sum(s["sample"] for s in st.session_state.strata_rows)
                total_pop = sum(s["size"] for s in st.session_state.strata_rows)

                rows = []
                for s in st.session_state.strata_rows:
                    rows.append({
                        "Strate": s["name"],
                        "Population": s["size"],
                        "Échantillon": s["sample"],
                        "Ratio": round(s["sample"] / s["size"], 4) if s["size"] > 0 else 0,
                    })
                st.success(f"✅ Tirage stratifié : {total_sample} individus sur {total_pop}")
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)