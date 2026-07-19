from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Request, status

from app.config import COGNITO_AUTH_MODE, get_settings


@dataclass(frozen=True)
class UserContext:
    user_id: str
    authenticated_at: datetime | None = None

    def is_recently_authenticated(self, *, now: datetime | None = None, max_age_minutes: int = 10) -> bool:
        if self.authenticated_at is None:
            return False
        current = now or datetime.now(timezone.utc)
        authenticated_at = self.authenticated_at
        if authenticated_at.tzinfo is None:
            authenticated_at = authenticated_at.replace(tzinfo=timezone.utc)
        return current - authenticated_at <= timedelta(minutes=max_age_minutes)


def get_current_user(request: Request) -> UserContext:
    settings = get_settings()

    if settings.auth_mode != COGNITO_AUTH_MODE:
        return UserContext(user_id=settings.local_dev_user_id)

    claims = extract_cognito_claims(request)
    user_id = claims.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    auth_time = claims.get("auth_time")
    try:
        authenticated_at = datetime.fromtimestamp(int(auth_time), tz=timezone.utc) if auth_time is not None else None
    except (TypeError, ValueError, OSError):
        authenticated_at = None
    return UserContext(user_id=user_id.strip(), authenticated_at=authenticated_at)


def extract_cognito_user_id(request: Request) -> str | None:
    user_id = extract_cognito_claims(request).get("sub")
    return user_id.strip() if isinstance(user_id, str) and user_id.strip() else None


def extract_cognito_claims(request: Request) -> dict[str, Any]:
    event = request.scope.get("aws.event") or {}
    request_context = event.get("requestContext") or {}
    authorizer = request_context.get("authorizer") or {}

    claims = _get_nested(authorizer, "jwt", "claims") or authorizer.get("claims") or {}
    return claims if isinstance(claims, dict) else {}


def _get_nested(source: dict[str, Any], *keys: str) -> dict[str, Any] | None:
    current: Any = source
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)

    return current if isinstance(current, dict) else None
