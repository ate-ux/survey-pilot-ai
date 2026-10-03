"""Endpoints profil utilisateur + gestion des comptes (Super Admin)."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import shutil
import uuid
from pathlib import Path

from database import get_db
from auth import require_user, hash_password, verify_password
from schemas import UserOut, UserUpdate, PasswordChange, AdminUserCreate
import models

router = APIRouter(prefix="/api/profile", tags=["profile"])

AVATAR_DIR = Path("/app/static/avatars")
AVATAR_DIR.mkdir(parents=True, exist_ok=True)


def _log_audit(db, user_id, action, entity_type=None, entity_id=None, details=None):
    db.add(models.AuditLog(
        user_id=user_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        details=details,
    ))
    db.commit()


# 1. Voir son profil
@router.get("/me", response_model=UserOut)
def get_my_profile(user: models.User = Depends(require_user)):
    return user


# 2. Modifier son profil
@router.patch("/me", response_model=UserOut)
def update_my_profile(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    if payload.email and payload.email != user.email:
        exists = db.query(models.User).filter(
            models.User.email == payload.email,
            models.User.id != user.id,
        ).first()
        if exists:
            raise HTTPException(status_code=400, detail="Email déjà utilisé")

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.email is not None:
        user.email = payload.email

    db.commit()
    db.refresh(user)
    _log_audit(db, user.id, "profile.update", "user", user.id, None)
    return user


# 3. Changer son mot de passe
@router.post("/change-password")
def change_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Minimum 6 caractères")

    user.password_hash = hash_password(payload.new_password)
    db.commit()
    _log_audit(db, user.id, "profile.change_password", "user", user.id, None)
    return {"status": "password_changed"}


# 4. Uploader sa photo de profil
@router.post("/avatar", response_model=UserOut)
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    if file.content_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        raise HTTPException(status_code=400, detail="Format non supporté (JPEG, PNG, GIF, WEBP)")

    ext = file.filename.split(".")[-1].lower()
    filename = f"user_{user.id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = AVATAR_DIR / filename

    with filepath.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    user.avatar_url = f"/static/avatars/{filename}"
    db.commit()
    db.refresh(user)
    _log_audit(db, user.id, "profile.avatar_upload", "user", user.id, {"filename": filename})
    return user


# 5. Supprimer sa photo
@router.delete("/avatar", response_model=UserOut)
def delete_avatar(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    if user.avatar_url:
        old_path = Path("/app" + user.avatar_url)
        if old_path.exists():
            old_path.unlink()
        user.avatar_url = None
        db.commit()
        db.refresh(user)
    return user


# 6. [SUPER ADMIN] Lister tous les utilisateurs
@router.get("/users")
def list_all_users(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    if user.role_id != 1:
        raise HTTPException(status_code=403, detail="Réservé au Super Admin")

    users = db.query(models.User).order_by(models.User.id).all()
    return {
        "count": len(users),
        "users": [
            {
                "id": u.id, "username": u.username, "email": u.email,
                "full_name": u.full_name, "avatar_url": u.avatar_url,
                "role_id": u.role_id, "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_login": u.last_login.isoformat() if u.last_login else None,
            }
            for u in users
        ],
    }


# 7. [SUPER ADMIN] Créer un utilisateur
@router.post("/users", response_model=UserOut)
def create_user(
    payload: AdminUserCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    if user.role_id != 1:
        raise HTTPException(status_code=403, detail="Réservé au Super Admin")

    if db.query(models.User).filter(models.User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Nom d'utilisateur déjà pris")
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    new_user = models.User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role_id=payload.role_id or 1,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    _log_audit(db, user.id, "admin.user_create", "user", new_user.id,
               {"username": new_user.username})
    return new_user


# 8. [SUPER ADMIN] Supprimer un utilisateur
@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    if user.role_id != 1:
        raise HTTPException(status_code=403, detail="Réservé au Super Admin")
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Impossible de se supprimer soi-même")

    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    _log_audit(db, user.id, "admin.user_delete", "user", target.id, None)
    db.delete(target)
    db.commit()
    return {"status": "deleted", "id": user_id}


# 9. [SUPER ADMIN] Activer / Désactiver un utilisateur
@router.patch("/users/{user_id}/toggle-active")
def toggle_user_active(
    user_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    if user.role_id != 1:
        raise HTTPException(status_code=403, detail="Réservé au Super Admin")

    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    target.is_active = not target.is_active
    db.commit()
    _log_audit(db, user.id, "admin.user_toggle", "user", target.id,
               {"is_active": target.is_active})
    return {"id": target.id, "is_active": target.is_active}