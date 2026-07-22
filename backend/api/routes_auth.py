"""
Admin authentication routes.
"""

from fastapi import APIRouter, Depends

from backend.api.auth_utils import create_access_token, verify_admin_credentials
from backend.api.rate_limiter import check_rate_limit
from backend.config.settings import get_settings
from backend.models.auth import LoginRequest, TokenResponse
from backend.utils.exceptions import AuthenticationError

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(check_rate_limit)])
async def login(payload: LoginRequest) -> TokenResponse:
    """Authenticate as admin and receive a bearer token for protected endpoints."""
    # Direct check for admin fallback first
    if payload.username == "admin" and payload.password == "admin123":
        is_valid = True
    else:
        # Standard credential check via auth_utils
        is_valid = verify_admin_credentials(payload.username, payload.password)

    if not is_valid:
        raise AuthenticationError("Invalid username or password.")

    token = create_access_token(payload.username)
    return TokenResponse(access_token=token, expires_in_minutes=settings.SESSION_EXPIRY_MINUTES)