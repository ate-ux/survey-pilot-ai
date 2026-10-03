"""Page : Mon Profil — modifier infos, changer mot de passe, uploader avatar."""
import streamlit as st
import requests
from api_client import get_client, BACKEND_URL


def _upload_avatar(token: str, file_bytes, filename: str, content_type: str):
    """Upload direct du fichier via requests."""
    files = {"file": (filename, file_bytes, content_type)}
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{BACKEND_URL}/api/profile/avatar", files=files,
                     headers=headers, timeout=60)
    if r.status_code >= 400:
        try:
            return None, r.json().get("detail", r.text)
        except Exception:
            return None, r.text
    return r.json(), None


def render():
    st.subheader("👤 Mon Profil")
    st.caption("Gérez vos informations personnelles, votre mot de passe et votre photo.")

    client = get_client()

    # --- Récupérer le profil actuel ---
    me, err = client.get_profile()
    if err:
        st.error(f"Erreur : {err}")
        return

    st.markdown("---")

    # === SECTION 1 : Avatar ===
    col_avatar, col_info = st.columns([1, 3])

    with col_avatar:
        avatar_url = me.get("avatar_url")
        if avatar_url:
            full_url = avatar_url.replace("/static/", "http://localhost:8000/static/")
            st.image(full_url, width=150, caption="Photo actuelle")
        else:
            st.markdown(
                "<div style='width:150px;height:150px;background:#e5e7eb;"
                "border-radius:50%;display:flex;align-items:center;"
                "justify-content:center;font-size:60px;'>👤</div>",
                unsafe_allow_html=True,
            )

        uploaded = st.file_uploader("Changer la photo",
                                     type=["jpg", "jpeg", "png", "gif", "webp"],
                                     key="avatar_upload")
        if uploaded is not None:
            if st.button("📤 Envoyer la photo", use_container_width=True):
                with st.spinner("Envoi en cours..."):
                    result, err = _upload_avatar(
                        st.session_state.token,
                        uploaded.getvalue(),
                        uploaded.name,
                        uploaded.type,
                    )
                    if err:
                        st.error(f"❌ {err}")
                    else:
                        st.success("✅ Photo mise à jour")
                        st.rerun()

        if avatar_url:
            if st.button("🗑️ Supprimer la photo", use_container_width=True):
                _, err = client.delete_avatar()
                if err:
                    st.error(f"❌ {err}")
                else:
                    st.success("Photo supprimée")
                    st.rerun()

    with col_info:
        st.markdown(f"### {me.get('full_name') or me.get('username')}")
        st.caption(f"👤 **@{me.get('username')}**")
        st.caption(f"📧 {me.get('email')}")
        st.caption(f"🎭 Rôle ID : {me.get('role_id')} ({'Super Admin' if me.get('role_id') == 1 else 'Utilisateur'})")
        st.caption(f"🆔 ID : {me.get('id')}")

    st.markdown("---")

    # === SECTION 2 : Modifier infos ===
    st.markdown("### ✏️ Modifier mes informations")

    with st.form("update_profile_form"):
        new_full_name = st.text_input("Nom complet", value=me.get("full_name") or "")
        new_email = st.text_input("Email", value=me.get("email") or "")
        submitted = st.form_submit_button("💾 Enregistrer", use_container_width=True)

    if submitted:
        payload = {}
        if new_full_name and new_full_name != me.get("full_name"):
            payload["full_name"] = new_full_name
        if new_email and new_email != me.get("email"):
            payload["email"] = new_email

        if not payload:
            st.info("Aucune modification à enregistrer.")
        else:
            data, err = client.update_profile(**payload)
            if err:
                st.error(f"❌ {err}")
            else:
                st.success("✅ Profil mis à jour")
                st.session_state.user = data
                st.rerun()

    st.markdown("---")

    # === SECTION 3 : Changer mot de passe ===
    st.markdown("### 🔐 Changer mon mot de passe")

    with st.form("change_password_form"):
        current = st.text_input("Mot de passe actuel", type="password")
        new1 = st.text_input("Nouveau mot de passe", type="password")
        new2 = st.text_input("Confirmer le nouveau mot de passe", type="password")
        submitted_pwd = st.form_submit_button("🔑 Changer le mot de passe", use_container_width=True)

    if submitted_pwd:
        if not current or not new1 or not new2:
            st.warning("Tous les champs sont obligatoires.")
        elif new1 != new2:
            st.error("❌ Les deux nouveaux mots de passe ne correspondent pas.")
        elif len(new1) < 6:
            st.error("❌ Le nouveau mot de passe doit faire au moins 6 caractères.")
        else:
            data, err = client.change_password(current, new1)
            if err:
                st.error(f"❌ {err}")
            else:
                st.success("✅ Mot de passe changé avec succès")