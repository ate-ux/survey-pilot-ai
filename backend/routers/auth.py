from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from auth import (
    hash_password, verify_password, create_access_token,
    require_user, get_current_user
)
from schemas import UserCreate, UserOut, Token
import models

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _log_audit(db: Session, user_id, action, entity_type=None, entity_id=None, details=None):
    db.add(models.AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    ))
    db.commit()


@router.post("/register", response_model=UserOut)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    # Vérifier doublons
    if db.query(models.User).filter(models.User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Nom d'utilisateur déjà pris")
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    user = models.User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role_id=payload.role_id or 1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    _log_audit(db, user.id, "user.register", "user", user.id,
               {"username": user.username})

    return user


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides",
        )
    user.last_login = datetime.utcnow()
    db.commit()

    _log_audit(db, user.id, "user.login", "user", user.id, None)

    token = create_access_token({"sub": user.username, "role_id": user.role_id})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
def me(user: models.User = Depends(require_user)):
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), user: models.User = Depends(require_user)):
    return db.query(models.User).all()