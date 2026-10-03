import streamlit as st
from api_client import get_client

st.set_page_config(
    page_title="SurveyPilot AI V2",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Initialisation de la session ---
if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None

client = get_client()


# ============================================================
# 1. ÉCRAN DE LOGIN
# ============================================================
def login_screen():
    st.title("📊 SurveyPilot AI V2")
    st.caption("Plateforme d'enquêtes statistiques multi-projets")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 🔐 Connexion")
        with st.form("login_form"):
            username = st.text_input("Nom d'utilisateur", value="admin")
            password = st.text_input("Mot de passe", type="password", value="admin123")
            submitted = st.form_submit_button("Connexion", use_container_width=True)

        if submitted:
            data, err = client.login(username, password)
            if err:
                st.error(f"❌ Échec de connexion : {err}")
            else:
                st.session_state.token = data["access_token"]
                me, _ = client.me()
                st.session_state.user = me
                st.success("✅ Connexion réussie")
                st.rerun()

        st.info("💡 **Démo** : `admin` / `admin123`")


# ============================================================
# 2. NAVIGATION
# ============================================================
MODULES = [
    "Dashboard Super Admin",
    "Projets",
    "Orchestrateur IA",
    "Base de Connaissances",
    "Échantillonnage",
    "Supervision Enquêteurs",
    "Données & Anomalies (CAP)",
    "Analyse Statistique",
    "Machine Learning",
    "Sandbox",
    "Approbations",
    "Mon Profil",
    "Utilisateurs",
]


def sidebar():
    with st.sidebar:
        st.title("SurveyPilot AI - V2")
        st.markdown("**Aller à :**")
        choix = st.radio("Navigation", MODULES, label_visibility="collapsed")

        st.markdown("---")
        user = st.session_state.user or {}

        # Avatar si présent
        avatar_url = user.get("avatar_url")
        if avatar_url:
            full_url = avatar_url.replace("/static/", "http://localhost:8000/static/")
            try:
                st.image(full_url, width=60)
            except Exception:
                pass

        st.caption(f"👤 **{user.get('full_name') or user.get('username', 'inconnu')}**")
        st.caption(f"@{user.get('username', '')}")
        st.caption(f"📧 {user.get('email', '')}")

        if st.button("🚪 Déconnexion", use_container_width=True):
            st.session_state.token = None
            st.session_state.user = None
            st.rerun()

        return choix


# ============================================================
# 3. ROUTAGE
# ============================================================
def main():
    if not st.session_state.token:
        login_screen()
        return

    choix = sidebar()

    if choix == "Dashboard Super Admin":
        from pages_impl import dashboard
        dashboard.render()

    elif choix == "Projets":
        from pages_impl import projects
        projects.render()

    elif choix == "Orchestrateur IA":
        from pages_impl import orchestrator
        orchestrator.render()

    elif choix == "Base de Connaissances":
        from pages_impl import knowledge
        knowledge.render()

    elif choix == "Échantillonnage":
        from pages_impl import sampling
        sampling.render()

    elif choix == "Supervision Enquêteurs":
        from pages_impl import interviewers
        interviewers.render()

    elif choix == "Données & Anomalies (CAP)":
        from pages_impl import cap
        cap.render()

    elif choix == "Analyse Statistique":
        from pages_impl import analysis_page
        analysis_page.render()

    elif choix == "Machine Learning":
        from pages_impl import ml_page
        ml_page.render()

    elif choix == "Sandbox":
        from pages_impl import sandbox
        sandbox.render()

    elif choix == "Approbations":
        from pages_impl import approvals
        approvals.render()

    elif choix == "Mon Profil":
        from pages_impl import profile as profile_page
        profile_page.render()

    elif choix == "Utilisateurs":
        from pages_impl import users_admin
        users_admin.render()


if __name__ == "__main__":
    main()