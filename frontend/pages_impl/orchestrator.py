"""Page 3 : Orchestrateur IA — déclencher les agents, voir les propositions."""
import streamlit as st
import pandas as pd
from api_client import get_client


def render():
    st.subheader("🤖 Orchestrateur IA")
    st.caption("Supervisez les agents autonomes (Méthodologue, Échantillonneur) et validez leurs propositions (Human-in-the-Loop).")

    client = get_client()

    # --- Liste des agents ---
    agents_data, err = client.list_agents()
    if err:
        st.error(f"Erreur agents : {err}")
        return

    st.markdown("### 👥 Agents disponibles")
    agents = agents_data.get("agents", [])
    if agents:
        cols = st.columns(len(agents))
        for i, a in enumerate(agents):
            with cols[i]:
                st.markdown(f"**{a['name']}**")
                st.caption(f"`{a['code']}` — {a['agent_type']}")
                st.caption(f"Autonomie : **{a['autonomy_level']}**")
                st.caption(f"Actif : {'✅' if a['is_enabled'] else '❌'}")
    else:
        st.info("Aucun agent configuré.")

    st.markdown("---")

    # --- Sélection d'une enquête pour déclencher un agent ---
    st.markdown("### 🎯 Déclencher un agent sur une enquête")

    surveys_data, err = client.list_surveys()
    if err:
        st.error(f"Erreur enquêtes : {err}")
        return

    surveys = surveys_data.get("surveys", [])
    if not surveys:
        st.warning("Aucune enquête disponible. Créez-en une d'abord (page Projets + enquêtes).")
        return

    survey_options = {f"#{s['id']} — {s['code']} : {s['title']}": s["id"] for s in surveys}
    selected = st.selectbox("Enquête cible", list(survey_options.keys()))
    survey_id = survey_options[selected]

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🧠 Agent Méthodologue")
        st.caption("Propose un plan de sondage adapté à la population.")
        if st.button("Déclencher le Méthodologue", use_container_width=True):
            data, err = client.methodologue_propose(survey_id)
            if err:
                st.error(f"❌ {err}")
            else:
                st.success(f"✅ Proposition #{data['proposal_id']} créée")
                st.json(data["proposal"])

    with col2:
        st.markdown("#### 📏 Agent Échantillonneur")
        st.caption("Calcule la taille d'échantillon optimale.")
        with st.expander("Paramètres avancés", expanded=False):
            confidence = st.slider("Niveau de confiance", 0.90, 0.99, 0.95, 0.01)
            margin = st.slider("Marge d'erreur", 0.01, 0.10, 0.05, 0.01)
        if st.button("Déclencher l'Échantillonneur", use_container_width=True):
            data, err = client.echantillonneur_propose(survey_id, confidence, margin)
            if err:
                st.error(f"❌ {err}")
            else:
                st.success(f"✅ Proposition #{data['proposal_id']} créée")
                st.json(data["proposal"])

    st.markdown("---")

    # --- Propositions en attente ---
    st.markdown("### ⏳ Propositions en attente de validation")
    props_data, err = client.list_proposals(status="pending")
    if err:
        st.error(f"Erreur propositions : {err}")
        return

    proposals = props_data.get("proposals", [])
    if not proposals:
        st.info("Aucune proposition en attente.")
        return

    for p in proposals:
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**#{p['id']} — {p['proposal_type']}**")
                st.caption(f"Enquête : #{p.get('survey_id')} — Proposé par IA : {p.get('proposed_by_ai')}")
                with st.expander("Voir la proposition"):
                    st.json(p.get("payload", {}))
            with col2:
                st.caption(f"Statut : **{p['status']}**")
                st.caption(f"Le {p.get('created_at', '')[:19].replace('T', ' ')}")
                if st.button("✅ Approuver", key=f"appr_{p['id']}", use_container_width=True):
                    _, err = client.decide_proposal(p["id"], "approved")
                    if err:
                        st.error(err)
                    else:
                        st.success("Approuvée")
                        st.rerun()
                if st.button("❌ Refuser", key=f"rej_{p['id']}", use_container_width=True):
                    _, err = client.decide_proposal(p["id"], "rejected")
                    if err:
                        st.error(err)
                    else:
                        st.success("Refusée")
                        st.rerun()

    st.markdown("---")

    # --- Journal des actions IA ---
    st.markdown("### 📜 Journal des actions IA")
    actions_data, err = client.list_ai_actions(limit=20)
    if err:
        st.warning(f"Erreur journal : {err}")
    else:
        actions = actions_data.get("actions", [])
        if not actions:
            st.info("Aucune action IA enregistrée.")
        else:
            rows = []
            for a in actions:
                rows.append({
                    "ID": a["id"],
                    "Agent": a.get("agent_id"),
                    "Proposition": a.get("proposal_id"),
                    "Type": a.get("action_type"),
                    "Date": (a.get("created_at") or "")[:19].replace("T", " "),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)