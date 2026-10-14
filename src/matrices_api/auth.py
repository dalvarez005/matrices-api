from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import User, get_db

_bearer = HTTPBearer(auto_error=False)
_google_request = google_requests.Request()


def verify_google_token(token: str) -> dict:
    """Valida el idToken de Google (firma, vencimiento y client id)."""
    client_ids = get_settings().google_client_id_list
    if not client_ids:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Inicio con Google no configurado.")
    try:
        info = id_token.verify_oauth2_token(
            token, _google_request, audience=client_ids, clock_skew_in_seconds=10
        )
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token de Google inválido.") from None
    if not info.get("email_verified"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "El correo de Google no está verificado.")
    return info


def upsert_google_user(db: Session, info: dict) -> User:
    user = db.scalar(select(User).where(User.google_sub == info["sub"]))
    if user is None:
        user = User(google_sub=info["sub"], email=info["email"])
        db.add(user)
    user.email = info["email"]
    user.name = info.get("name") or info["email"].split("@")[0]
    user.picture = info.get("picture")
    user.last_login_at = datetime.now(UTC)
    db.commit()
    return user


def issue_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {"sub": str(user.id), "iat": now, "exp": now + timedelta(days=settings.jwt_days)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User | None:
    """Usuario de la sesión, o None si se usa la app sin cuenta."""
    if creds is None:
        return None
    try:
        payload = jwt.decode(creds.credentials, get_settings().jwt_secret, algorithms=["HS256"])
        user = db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        user = None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión vencida. Inicia sesión de nuevo.")
    return user


def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Inicia sesión para usar el historial.")
    return user
