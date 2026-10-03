"""Page 4 : Base de Connaissances."""
import streamlit as st
from api_client import get_client


def render():
    st.subheader("📚 Base de Connaissances")
    st.caption("Référentiel de méthodes, guides et bonnes pratiques.")

    client = get_client()

    # Bouton seed
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("📥 Charger les articles par défaut", use_container_width=True):
            data, err = client.seed_knowledge()
            if err:
                st.error(f"❌ {err}")
            else:
                st.success(f"✅ {data.get('created', 0)} articles ajoutés")
                st.rerun()

    st.markdown("---")

    # Formulaire de création
    with st.expander("➕ Ajouter un article", expanded=False):
        with st.form("create_article"):
            title = st.text_input("Titre")
            category = st.text_input("Catégorie", placeholder="Méthodologie")
            content = st.text_area("Contenu", height=150)
            tags_input = st.text_input("Tags (séparés par des virgules)")
            submitted = st.form_submit_button("Créer", use_container_width=True)

        if submitted:
            if not title or not content:
                st.warning("Titre et contenu obligatoires.")
            else:
                st.info("Le endpoint de création n'est pas encore branché côté frontend. Utilisez le seed.")

    st.markdown("---")

    # Liste
    data, err = client.list_knowledge()
    if err:
        st.error(f"Erreur : {err}")
        return

    entries = data.get("entries", [])
    if not entries:
        st.info("Aucun article. Cliquez sur **Charger les articles par défaut** en haut.")
        return

    st.markdown(f"### 📖 {len(entries)} article(s)")

    for e in entries:
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"### {e['title']}")
                st.caption(f"Catégorie : **{e.get('category') or '—'}** · "
                           f"Ajouté le {e.get('created_at', '')[:10]}")
            with col2:
                st.caption(f"ID: {e['id']}")
            st.markdown(e.get("content", ""))
            if e.get("tags"):
                tags = e["tags"]
                if isinstance(tags, list):
                    st.caption("🏷️ " + " · ".join([f"`{t}`" for t in tags]))