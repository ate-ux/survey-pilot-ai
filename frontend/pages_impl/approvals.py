"""Page 10 : Approbations — workflow de validation."""
import streamlit as st
import pandas as pd
from api_client import get_client


def render():
    st.subheader("✅ Approbations")
    st.caption("Validez ou refusez les propositions soumises par les agents IA ou les utilisateurs.")

    client = get_client()

    # --- Filtre ---
    status_filter = st.radio(
        "Filtrer par statut",
        ["Toutes", "pending", "approved", "rejected"],
        horizontal=True,
    )

    status = None if status_filter == "Toutes" else status_filter
    data, err = client.list_proposals(status=status)
    if err:
        st.error(f"Erreur : {err}")
        return

    proposals = data.get("proposals", [])
    if not proposals:
        st.info(f"Aucune proposition ({status_filter.lower()}).")
        return

    # --- Métriques ---
    total = len(proposals)
    pending = sum(1 for p in proposals if p["status"] == "pending")
    approved = sum(1 for p in proposals if p["status"] == "approved")
    rejected = sum(1 for p in proposals if p["status"] == "rejected")

    cols = st.columns(4)
    cols[0].metric("Total", total)
    cols[1].metric("En attente", pending)
    cols[2].metric("Approuvées", approved)
    cols[3].metric("Refusées", rejected)

    st.markdown("---")

    # --- Liste ---
    for p in proposals:
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**#{p['id']} — {p['proposal_type']}**")
                st.caption(
                    f"Statut : **{p['status']}** · "
                    f"Par IA : {p.get('proposed_by_ai')} · "
                    f"Enquête #{p.get('survey_id')} · "
                    f"{p.get('created_at', '')[:19].replace('T', ' ')}"
                )
                with st.expander("📋 Voir la proposition complète"):
                    st.json(p.get("payload", {}))

            with col2:
                if p["status"] == "pending":
                    if st.button("✅ Approuver", key=f"appr_{p['id']}", use_container_width=True):
                        _, err = client.decide_proposal(p["id"], "approved", "Validé")
                        if err:
                            st.error(err)
                        else:
                            st.success("Approuvée")
                            st.rerun()
                    if st.button("❌ Refuser", key=f"rej_{p['id']}", use_container_width=True):
                        _, err = client.decide_proposal(p["id"], "rejected", "Refusé")
                        if err:
                            st.error(err)
                        else:
                            st.success("Refusée")
                            st.rerun()
                else:
                    st.markdown(f"**{p['status'].upper()}**")