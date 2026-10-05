"""Page Carte interactive — géolocalisation des zones et enquêtés."""
import streamlit as st
import folium
from streamlit_folium import st_folium
from api_client import get_client


# Coordonnées par défaut (ISSEA Yaoundé)
DEFAULT_LAT = 3.8480
DEFAULT_LON = 11.5021


def render():
    st.subheader("🗺️ Carte interactive")
    st.caption("Visualisation géographique de l'ISSEA, des zones d'enquête et des réponses géolocalisées.")

    client = get_client()

    # --- Filtres ---
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("### 📍 Filtres")
    with col2:
        show_zones = st.checkbox("Afficher les zones", value=True)
        show_responses = st.checkbox("Afficher les réponses", value=True)

    # --- Récupérer les données cartographiques ---
    data, err = client.get_map_data()
    if err:
        st.error(f"Erreur : {err}")
        return

    responses = data.get("responses", [])
    zones = data.get("zones", [])
    center = data.get("center", {"lat": DEFAULT_LAT, "lon": DEFAULT_LON, "name": "ISSEA"})

    # --- KPIs ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Zones cartographiées", len(zones))
    col2.metric("Réponses géolocalisées", len(responses))
    col3.metric("Centre", center.get("name", "ISSEA"))

    st.markdown("---")

    # --- Création de la carte Folium ---
    m = folium.Map(
        location=[center.get("lat", DEFAULT_LAT), center.get("lon", DEFAULT_LON)],
        zoom_start=13,
        tiles="OpenStreetMap",
    )

    # Marqueur du centre ISSEA
    folium.Marker(
        [center.get("lat", DEFAULT_LAT), center.get("lon", DEFAULT_LON)],
        popup=f"<b>{center.get('name', 'Centre')}</b>",
        tooltip="Centre de référence",
        icon=folium.Icon(color="red", icon="university", prefix="fa"),
    ).add_to(m)

    # --- Zones (ISSEA, quartiers) ---
    if show_zones:
        for z in zones:
            lat = z.get("lat") or z.get("center_lat")
            lon = z.get("lon") or z.get("center_lon")
            if lat is None or lon is None:
                continue

            zone_type = z.get("type") or z.get("zone_type", "zone")
            color = {
                "issea": "red",
                "quartier": "blue",
                "region": "green",
                "stratum": "orange",
            }.get(zone_type, "gray")

            folium.CircleMarker(
                [lat, lon],
                radius=15,
                popup=f"<b>{z.get('name')}</b><br>Type: {zone_type}",
                tooltip=z.get("name"),
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.4,
            ).add_to(m)

    # --- Réponses géolocalisées ---
    if show_responses and responses:
        for r in responses:
            lat = r.get("lat")
            lon = r.get("lon")
            if lat is None or lon is None:
                continue

            folium.CircleMarker(
                [lat, lon],
                radius=5,
                popup=f"<b>Réponse #{r.get('id')}</b><br>Répondant : {r.get('respondent', 'N/A')}",
                tooltip=f"Réponse #{r.get('id')}",
                color="green",
                fill=True,
                fillColor="lightgreen",
                fillOpacity=0.7,
            ).add_to(m)

    # --- Affichage de la carte ---
    st_folium(m, width=None, height=550, returned_objects=[])

    st.markdown("---")

    # --- Légende ---
    st.markdown("### 🗝️ Légende")
    col1, col2, col3, col4 = st.columns(4)
    col1.markdown("🔴 **ISSEA** (centre)")
    col2.markdown("🔵 **Quartier**")
    col3.markdown("🟢 **Réponses** géolocalisées")
    col4.markdown("🟠 **Strates**")

    # --- Ajouter une zone ---
    with st.expander("➕ Ajouter une nouvelle zone géographique"):
        with st.form("add_zone_form"):
            col1, col2 = st.columns(2)
            with col1:
                zone_name = st.text_input("Nom de la zone", placeholder="Ex: Quartier Mvog-Ada")
                zone_type = st.selectbox(
                    "Type",
                    options=["issea", "quartier", "region", "stratum"],
                )
            with col2:
                zone_lat = st.number_input("Latitude", value=3.8480, format="%.4f")
                zone_lon = st.number_input("Longitude", value=11.5021, format="%.4f")

            submitted = st.form_submit_button("Créer la zone", use_container_width=True)

        if submitted:
            if not zone_name:
                st.warning("Le nom est obligatoire.")
            else:
                data, err = client.create_geo_zone(
                    name=zone_name,
                    zone_type=zone_type,
                    center_lat=zone_lat,
                    center_lon=zone_lon,
                )
                if err:
                    st.error(f"❌ {err}")
                else:
                    st.success(f"✅ Zone '{zone_name}' créée")
                    st.rerun()

    # --- Statistiques géographiques ---
    st.markdown("---")
    st.markdown("### 📊 Statistiques géographiques")

    stats, err = client.get_geo_stats()
    if err:
        st.warning(f"Stats indisponibles : {err}")
    else:
        if stats.get("count", 0) == 0:
            st.info("Aucune réponse géolocalisée pour l'instant. Les réponses apparaîtront ici une fois collectées avec GPS.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Réponses géolocalisées", stats.get("count"))
            with col2:
                centroid = stats.get("centroid", {})
                st.caption(f"Centroïde : {centroid.get('lat', 0):.4f}, {centroid.get('lon', 0):.4f}")

            bounds = stats.get("bounds", {})
            if bounds:
                st.markdown("**Étendue géographique :**")
                st.caption(
                    f"Latitudes : {bounds.get('lat_min', 0):.4f} → {bounds.get('lat_max', 0):.4f}"
                )
                st.caption(
                    f"Longitudes : {bounds.get('lon_min', 0):.4f} → {bounds.get('lon_max', 0):.4f}"
                )