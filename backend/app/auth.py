from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request, status

from app.config import COGNITO_AUTH_MODE, get_settings


@dataclass(frozen=True)
class UserContext:
    user_id: str


def get_current_user(request: Request) -> UserContext:
    settings = get_settings()

    if settings.auth_mode != COGNITO_AUTH_MODE:
        return UserContext(user_id=settings.local_dev_user_id)

    user_id = extract_cognito_user_id(request)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return UserContext(user_id=user_id)


def extract_cognito_user_id(request: Request) -> str | None:
    event = request.scope.get("aws.event") or {}
    request_context = event.get("requestContext") or {}
    authorizer = request_context.get("authorizer") or {}

    claims = _get_nested(authorizer, "jwt", "claims") or authorizer.get("claims") or {}
    user_id = claims.get("sub")

    if isinstance(user_id, str) and user_id.strip():
        return user_id.strip()

    return None


def _get_nested(source: dict[str, Any], *keys: str) -> dict[str, Any] | None:
    current: Any = source
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)

    return current if isinstance(current, dict) else None
