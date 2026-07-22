"""
Admin authentication utilities.

Simple username/bcrypt-hashed-password login issuing a short-lived JWT,
used to protect admin-only endpoints (ticket deletion, KB management,
analytics, etc.).
"""

from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from backend.config.settings import get_settings
from backend.utils.exceptions import AuthenticationError
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

_ALGORITHM = "HS256"
_security_scheme = HTTPBearer(auto_error=False)


def verify_admin_credentials(username: str, password: str) -> bool:
    """Check a login attempt against the configured admin username/password hash."""
    if username != settings.ADMIN_USERNAME:
        return False
    if not settings.ADMIN_PASSWORD_HASH:
        logger.warning("ADMIN_PASSWORD_HASH is not set — admin login is disabled until configured.")
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), settings.ADMIN_PASSWORD_HASH.encode("utf-8"))
    except ValueError as exc:
        logger.error("ADMIN_PASSWORD_HASH is malformed: %s", exc)
        return False


def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.SESSION_EXPIRY_MINUTES)
    payload = {"sub": username, "exp": expire, "role": "admin"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=_ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[_ALGORITHM])
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired session token. Please log in again.") from exc


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security_scheme),
) -> str:
    """
    FastAPI dependency protecting admin-only routes. Expects an
    `Authorization: Bearer <token>` header. Raises AuthenticationError
    (mapped to HTTP 401) if missing/invalid/expired.
    """
    if credentials is None:
        raise AuthenticationError("Missing authentication token. Please log in.")

    payload = _decode_token(credentials.credentials)
    if payload.get("role") != "admin":
        raise AuthenticationError("Insufficient privileges for this action.")
    return payload["sub"]
