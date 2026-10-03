"""Page 2 : Projets — CRUD visuel."""
import streamlit as st
import pandas as pd
from api_client import get_client


def render():
    st.subheader("📁 Projets")
    st.caption("Gérez vos projets d'enquête (ISSEA, Santé, Marketing, …)")

    client = get_client()

    # --- Formulaire de création ---
    with st.expander("➕ Créer un nouveau projet", expanded=False):
        with st.form("create_project_form"):
            col1, col2 = st.columns(2)
            with col1:
                code = st.text_input("Code projet", placeholder="ISSEA")
                name = st.text_input("Nom du projet", placeholder="Projet ISSEA")
            with col2:
                description = st.text_area("Description", placeholder="Enquête pilote…")
            submitted = st.form_submit_button("Créer", use_container_width=True)

        if submitted:
            if not code or not name:
                st.warning("Code et nom sont obligatoires.")
            else:
                data, err = client.create_project(code, name, description)
                if err:
                    st.error(f"❌ {err}")
                else:
                    st.success(f"✅ Projet créé (ID={data['id']})")
                    st.rerun()

    st.markdown("---")

    # --- Liste des projets ---
    data, err = client.list_projects()
    if err:
        st.error(f"Erreur : {err}")
        return

    projects = data.get("projects", [])
    if not projects:
        st.info("Aucun projet pour l'instant. Créez-en un avec le formulaire ci-dessus.")
        return

    st.markdown(f"### 📋 {len(projects)} projet(s)")

    for p in projects:
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            with col1:
                st.markdown(f"**{p['name']}**  \n`{p['code']}` — {p.get('description') or '_Pas de description_'}")
            with col2:
                st.metric("Statut", p.get("status", "—"))
            with col3:
                st.caption(f"ID: {p['id']}")

            with col4:
                if st.button("🗑️ Supprimer", key=f"del_proj_{p['id']}"):
                    _, err = client.delete_project(p["id"])
                    if err:
                        st.error(f"❌ {err}")
                    else:
                        st.success("Supprimé")
                        st.rerun()