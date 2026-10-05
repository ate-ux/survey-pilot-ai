"""Module Géolocalisation - zones, coordonnées GPS, cartes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from math import radians, cos, sin, asin, sqrt
from datetime import datetime
from pydantic import BaseModel

from database import get_db
from auth import require_user
import models

router = APIRouter(prefix="/api/geo", tags=["geo"])


# ============================================================
# Schémas Pydantic
# ============================================================
class GeoZoneCreate(BaseModel):
    name: str
    zone_type: str  # 'issea', 'quartier', 'region', 'stratum'
    center_lat: float
    center_lon: float
    geometry: Optional[dict] = None


class ResponseGeoUpdate(BaseModel):
    latitude: float
    longitude: float
    gps_accuracy: Optional[float] = None


class InterviewerLocationCreate(BaseModel):
    interviewer_id: int
    latitude: float
    longitude: float


# ============================================================
# Helpers
# ============================================================
def _log_audit(db, user_id, action, entity_type=None, entity_id=None, details=None):
    db.add(models.AuditLog(
        user_id=user_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        details=details,
    ))
    db.commit()


def _haversine(lat1, lon1, lat2, lon2):
    """Distance en km entre 2 points GPS (formule de Haversine)."""
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c


# ============================================================
# 1. Créer une zone géographique
# ============================================================
@router.post("/zones")
def create_zone(
    payload: GeoZoneCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    zone = models.GeoZone(
        name=payload.name,
        zone_type=payload.zone_type,
        center_lat=payload.center_lat,
        center_lon=payload.center_lon,
        geometry=payload.geometry,
        created_by=user.id,
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)

    _log_audit(db, user.id, "geo.zone.create", "geo_zone", zone.id,
               {"name": zone.name, "type": zone.zone_type})

    return {
        "status": "created",
        "id": zone.id,
        "name": zone.name,
        "zone_type": zone.zone_type,
        "center": {"lat": float(zone.center_lat), "lon": float(zone.center_lon)},
    }


# ============================================================
# 2. Lister les zones
# ============================================================
@router.get("/zones")
def list_zones(
    zone_type: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    q = db.query(models.GeoZone)
    if zone_type:
        q = q.filter(models.GeoZone.zone_type == zone_type)
    zones = q.all()
    return {
        "count": len(zones),
        "zones": [
            {
                "id": z.id,
                "name": z.name,
                "zone_type": z.zone_type,
                "center_lat": float(z.center_lat) if z.center_lat else None,
                "center_lon": float(z.center_lon) if z.center_lon else None,
                "geometry": z.geometry,
                "created_at": z.created_at.isoformat() if z.created_at else None,
            }
            for z in zones
        ],
    }


# ============================================================
# 3. Associer lat/lon à une réponse
# ============================================================
@router.post("/responses/{response_id}")
def set_response_geo(
    response_id: int,
    payload: ResponseGeoUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    response = db.query(models.Response).filter(models.Response.id == response_id).first()
    if not response:
        raise HTTPException(status_code=404, detail="Réponse introuvable")

    response.latitude = payload.latitude
    response.longitude = payload.longitude
    response.gps_accuracy = payload.gps_accuracy
    response.collected_at_gps = datetime.utcnow()
    db.commit()

    _log_audit(db, user.id, "geo.response.set", "response", response_id,
               {"lat": payload.latitude, "lon": payload.longitude})

    return {
        "status": "updated",
        "response_id": response_id,
        "latitude": float(response.latitude),
        "longitude": float(response.longitude),
    }


# ============================================================
# 4. Données pour la carte (réponses géolocalisées)
# ============================================================
@router.get("/map-data")
def get_map_data(
    survey_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    q = db.query(models.Response).filter(
        models.Response.latitude.isnot(None),
        models.Response.longitude.isnot(None),
    )
    if survey_id:
        q = q.filter(models.Response.survey_id == survey_id)

    responses = q.limit(1000).all()
    zones = db.query(models.GeoZone).all()

    # Marqueurs des réponses
    markers = [
        {
            "id": r.id,
            "lat": float(r.latitude),
            "lon": float(r.longitude),
            "respondent": r.respondent_code,
            "survey_id": r.survey_id,
            "collected_at": r.collected_at.isoformat() if r.collected_at else None,
        }
        for r in responses
    ]

    # Zones (ISSEA, quartiers)
    zone_markers = [
        {
            "id": z.id,
            "name": z.name,
            "type": z.zone_type,
            "lat": float(z.center_lat) if z.center_lat else None,
            "lon": float(z.center_lon) if z.center_lon else None,
        }
        for z in zones
    ]

    return {
        "count_responses": len(markers),
        "count_zones": len(zone_markers),
        "responses": markers,
        "zones": zone_markers,
        "center": {
            "lat": 3.8480,
            "lon": 11.5021,
            "name": "ISSEA Yaoundé",
        },
    }


# ============================================================
# 5. Enregistrer la position d'un enquêteur
# ============================================================
@router.post("/interviewer-location")
def record_interviewer_location(
    payload: InterviewerLocationCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    interviewer = db.query(models.Interviewer).filter(
        models.Interviewer.id == payload.interviewer_id).first()
    if not interviewer:
        raise HTTPException(status_code=404, detail="Enquêteur introuvable")

    loc = models.InterviewerLocation(
        interviewer_id=payload.interviewer_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)

    return {
        "status": "recorded",
        "id": loc.id,
        "interviewer_id": payload.interviewer_id,
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "recorded_at": loc.recorded_at.isoformat(),
    }


# ============================================================
# 6. Réponses dans un rayon autour d'un point
# ============================================================
@router.get("/nearby")
def nearby_responses(
    lat: float,
    lon: float,
    radius_km: float = 5.0,
    survey_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    q = db.query(models.Response).filter(
        models.Response.latitude.isnot(None),
        models.Response.longitude.isnot(None),
    )
    if survey_id:
        q = q.filter(models.Response.survey_id == survey_id)

    responses = q.all()

    nearby = []
    for r in responses:
        dist = _haversine(lat, lon, float(r.latitude), float(r.longitude))
        if dist <= radius_km:
            nearby.append({
                "id": r.id,
                "respondent": r.respondent_code,
                "survey_id": r.survey_id,
                "lat": float(r.latitude),
                "lon": float(r.longitude),
                "distance_km": round(dist, 3),
            })

    nearby.sort(key=lambda x: x["distance_km"])

    return {
        "center": {"lat": lat, "lon": lon},
        "radius_km": radius_km,
        "count": len(nearby),
        "responses": nearby,
    }


# ============================================================
# 7. Statistiques géographiques
# ============================================================
@router.get("/stats")
def geo_stats(
    survey_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    q = db.query(models.Response).filter(
        models.Response.latitude.isnot(None),
        models.Response.longitude.isnot(None),
    )
    if survey_id:
        q = q.filter(models.Response.survey_id == survey_id)

    responses = q.all()
    if not responses:
        return {
            "count": 0,
            "message": "Aucune réponse géolocalisée",
        }

    lats = [float(r.latitude) for r in responses]
    lons = [float(r.longitude) for r in responses]

    return {
        "count": len(responses),
        "bounds": {
            "lat_min": min(lats),
            "lat_max": max(lats),
            "lon_min": min(lons),
            "lon_max": max(lons),
        },
        "centroid": {
            "lat": sum(lats) / len(lats),
            "lon": sum(lons) / len(lons),
        },
        "survey_id": survey_id,
    }