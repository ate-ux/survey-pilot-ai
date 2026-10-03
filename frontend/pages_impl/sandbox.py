"""Page 9 : Sandbox."""
import streamlit as st
import pandas as pd
from api_client import get_client


def render():
    st.subheader("🧪 Sandbox")
    st.caption("Environnement d'expérimentation isolé. Clonez un projet pour tester "
               "sans risque, puis réinitialisez en un clic.")

    client = get_client()

    # --- Stats sandbox ---
    st.markdown("### 📊 État actuel du sandbox")
    stats, err = client.sandbox_stats()
    if err:
        st.error(f"Erreur : {err}")
        return

    col1, col2 = st.columns(2)
    col1.metric("Projets en sandbox", stats.get("projects_count", 0))
    col2.metric("Environnement ID", stats.get("sandbox_environment_id", "—"))

    projects = stats.get("projects", [])
    if projects:
        st.markdown("#### Projets clonés")
        df = pd.DataFrame(projects)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Aucun projet dans le sandbox.")

    st.markdown("---")

    # --- Clone ---
    st.markdown("### 📥 Cloner un projet en sandbox")

    projects_data, err = client.list_projects()
    if err:
        st.error(f"Erreur : {err}")
        return

    real_projects = projects_data.get("projects", [])
    # Exclure ceux déjà clonés
    real_projects = [p for p in real_projects if "SANDBOX" not in p.get("name", "")]

    if not real_projects:
        st.warning("Aucun projet réel disponible à cloner.")
    else:
        options = {f"#{p['id']} — {p['code']} : {p['name']}": p["id"] for p in real_projects}
        selected = st.selectbox("Projet à cloner", list(options.keys()))
        if st.button("📥 Cloner en sandbox", use_container_width=True):
            data, err = client.sandbox_clone(options[selected])
            if err:
                st.error(f"❌ {err}")
            else:
                st.success(
                    f"✅ Clone créé : `{data['sandbox_code']}` "
                    f"({data['surveys_cloned']} enquêtes, {data['questions_cloned']} questions)"
                )
                st.rerun()

    st.markdown("---")

    # --- Reset ---
    st.markdown("### 🗑️ Réinitialiser le sandbox")
    st.warning("⚠️ Cette action supprime **tous** les projets en sandbox. Les données réelles ne sont pas affectées.")

    if st.button("🔴 Réinitialiser le sandbox", use_container_width=True):
        data, err = client.sandbox_reset()
        if err:
            st.error(f"❌ {err}")
        else:
            st.success(f"✅ Sandbox réinitialisé — {data['projects_deleted']} projet(s) supprimé(s)")
            st.rerun()