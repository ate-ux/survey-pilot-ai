"""Initialise le Super Admin au démarrage si inexistant."""
from sqlalchemy.orm import Session
from auth import hash_password
import models

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_EMAIL = "admin@surveypilot.ai"
DEFAULT_ADMIN_PASSWORD = "admin123"


def ensure_super_admin(db: Session) -> None:
    existing = db.query(models.User).filter(
        models.User.username == DEFAULT_ADMIN_USERNAME
    ).first()
    if existing:
        return

    admin = models.User(
        username=DEFAULT_ADMIN_USERNAME,
        email=DEFAULT_ADMIN_EMAIL,
        password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
        full_name="Super Administrateur",
        role_id=1,  # super_admin
        is_active=True,
    )
    db.add(admin)
    db.commit()
    print(f"[init] Super Admin créé : {DEFAULT_ADMIN_USERNAME} / {DEFAULT_ADMIN_PASSWORD}")