"""Page : Gestion des Utilisateurs (Super Admin uniquement)."""
import streamlit as st
import pandas as pd
from api_client import get_client


ROLE_NAMES = {
    1: "Super Admin",
    2: "Gestionnaire",
    3: "Analyste",
    4: "Enquêteur",
}


def render():
    st.subheader("👥 Gestion des Utilisateurs")
    st.caption("Réservé au Super Administrateur. Créez, activez, désactivez ou supprimez des comptes.")

    client = get_client()

    me = st.session_state.user or {}
    if me.get("role_id") != 1:
        st.error("🚫 Accès refusé. Cette page est réservée au Super Administrateur.")
        return

    # === Création ===
    with st.expander("➕ Créer un nouvel utilisateur", expanded=False):
        with st.form("create_user_form"):
            col1, col2 = st.columns(2)
            with col1:
                username = st.text_input("Nom d'utilisateur")
                email = st.text_input("Email")
            with col2:
                full_name = st.text_input("Nom complet")
                password = st.text_input("Mot de passe", type="password")
                role_id = st.selectbox("Rôle", options=[1, 2, 3, 4],
                                        format_func=lambda x: ROLE_NAMES.get(x, str(x)))

            submitted = st.form_submit_button("Créer l'utilisateur", use_container_width=True)

        if submitted:
            if not username or not email or not password:
                st.warning("Tous les champs obligatoires doivent être remplis.")
            else:
                data, err = client.create_user(username, email, password, full_name, role_id)
                if err:
                    st.error(f"❌ {err}")
                else:
                    st.success(f"✅ Utilisateur `{data['username']}` créé")
                    st.rerun()

    st.markdown("---")

    # === Liste ===
    data, err = client.list_all_users()
    if err:
        st.error(f"Erreur : {err}")
        return

    users = data.get("users", [])
    st.markdown(f"### 📋 {len(users)} utilisateur(s)")

    for u in users:
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])

            with col1:
                st.markdown(f"**{u.get('full_name') or u['username']}**")
                st.caption(f"@{u['username']} · {u['email']}")

            with col2:
                st.caption(f"🎭 {ROLE_NAMES.get(u.get('role_id'), 'Rôle ?')}")
                st.caption(f"🆔 ID : {u['id']}")
                if u.get("last_login"):
                    st.caption(f"🔑 Dernière connexion : {u['last_login'][:19].replace('T', ' ')}")

            with col3:
                status_icon = "🟢 Actif" if u["is_active"] else "🔴 Inactif"
                st.markdown(status_icon)
                if u["id"] == me.get("id"):
                    st.caption("(vous)")

            with col4:
                # Ne pas pouvoir se désactiver/supprimer soi-même
                if u["id"] != me.get("id"):
                    if st.button("🔄 Basculer", key=f"toggle_{u['id']}", use_container_width=True):
                        _, err = client.toggle_user_active(u["id"])
                        if err:
                            st.error(err)
                        else:
                            st.rerun()
                    if st.button("🗑️ Supprimer", key=f"del_user_{u['id']}", use_container_width=True):
                        _, err = client.delete_user(u["id"])
                        if err:
                            st.error(err)
                        else:
                            st.success("Utilisateur supprimé")
                            st.rerun()
                else:
                    st.caption("—")