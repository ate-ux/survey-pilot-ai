"""Page 6 : Supervision Enquêteurs."""
import streamlit as st
from api_client import get_client


def render():
    st.subheader("👥 Supervision Enquêteurs")
    st.caption("Suivi des enquêteurs de terrain et de leur activité.")

    client = get_client()

    # Info générale
    st.info(
        "📌 **Module en cours de finalisation** — le backend expose les endpoints "
        "nécessaires, l'interface sera enrichie prochainement.\n\n"
        "En attendant, vous pouvez consulter le **journal d'audit** pour suivre "
        "l'activité de collecte."
    )

    st.markdown("---")
    st.markdown("### 📊 Indicateurs de collecte")

    kpis, err = client.kpis()
    if err:
        st.error(f"Erreur : {err}")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Enquêteurs déployés", kpis["enqueteurs_deployes"])
    col2.metric("Données collectées", f"{kpis['donnees_collectees']:,}")
    col3.metric("Enquêtes en cours", kpis["enquetes_en_cours"])

    st.markdown("---")
    st.markdown("### 📋 Activité récente (audit)")

    audit, err = client.list_audit(limit=30)
    if err:
        st.warning(f"Audit indisponible : {err}")
        return

    entries = audit.get("entries", [])
    if not entries:
        st.info("Aucune activité enregistrée.")
        return

    import pandas as pd
    rows = [
        {
            "Date": (e.get("created_at") or "")[:19].replace("T", " "),
            "Action": e.get("action", ""),
            "Entité": f"{e.get('entity_type', '')}#{e.get('entity_id', '')}",
            "Utilisateur": e.get("user_id", ""),
        }
        for e in entries
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)