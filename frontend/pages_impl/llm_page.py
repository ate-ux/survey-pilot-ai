"""Page Recommandations IA — LLM Groq."""
import streamlit as st
from api_client import get_client


def render():
    st.subheader("🤖 Recommandations IA")
    st.caption("Générez des recommandations et interprétations automatiques grâce à l'IA (Groq + GPT-OSS 120B).")

    client = get_client()

    # --- Statut LLM ---
    status, err = client.get_llm_status()
    if err:
        st.error(f"Erreur : {err}")
        return

    if not status.get("available"):
        st.error("❌ LLM non configuré.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Provider", status.get("provider", "—"))
    col2.metric("Statut", "✅ Disponible")
    col3.metric("Modèle", status.get("model", "—").split("/")[-1])

    st.markdown("---")

    # --- Sélection d'enquête ---
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

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 💡 Recommandations méthodologiques")
        st.caption("L'IA analyse l'enquête et propose 5 recommandations concrètes.")

        if st.button("🚀 Générer les recommandations", use_container_width=True, key="btn_reco"):
            with st.spinner("L'IA analyse votre enquête... (10-30 secondes)"):
                data, err = client.get_llm_recommendations(survey_id)
            if err:
                st.error(f"❌ {err}")
            else:
                st.success(f"✅ Recommandation #{data['recommendation_id']} générée")
                st.markdown("---")
                st.markdown(data["recommendation"])
                st.caption(f"Généré par {data['model']}")

    with col2:
        st.markdown("### 📊 Interprétation des résultats")
        st.caption("L'IA analyse vos données et donne son interprétation.")

        if st.button("🔍 Interpréter les résultats", use_container_width=True, key="btn_interp"):
            with st.spinner("L'IA analyse vos résultats... (10-30 secondes)"):
                data, err = client.get_llm_interpretation(survey_id)
            if err:
                st.error(f"❌ {err}")
            else:
                st.success(f"✅ Interprétation #{data['recommendation_id']} générée")
                st.markdown("---")
                st.markdown(data["interpretation"])
                st.caption(f"Généré par {data['model']}")

    st.markdown("---")

    st.markdown("### 📜 Historique des recommandations")

    recs_data, err = client.list_llm_recommendations(survey_id=survey_id)
    if err:
        st.warning(f"Historique indisponible : {err}")
        return

    recs = recs_data.get("recommendations", [])
    if not recs:
        st.info("Aucune recommandation générée pour cette enquête.")
        return

    for r in recs:
        with st.expander(
            f"#{r['id']} — {r['type']} — {r.get('created_at', '')[:19].replace('T', ' ')}"
        ):
            st.markdown(r.get("content", ""))