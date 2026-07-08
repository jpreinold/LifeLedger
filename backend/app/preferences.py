from datetime import datetime, timezone

from app.models import UserPreferences

DEFAULT_DIGEST_ENABLED = True
DEFAULT_DIGEST_TIME = "09:00"
DEFAULT_DIGEST_LOOKAHEAD_DAYS = 30


def default_digest_preferences(user_id: str, now: datetime | None = None) -> UserPreferences:
    resolved_now = now or datetime.now(timezone.utc)
    return UserPreferences(
        user_id=user_id,
        digest_enabled=DEFAULT_DIGEST_ENABLED,
        digest_time=DEFAULT_DIGEST_TIME,
        digest_lookahead_days=DEFAULT_DIGEST_LOOKAHEAD_DAYS,
        timezone=None,
        digest_last_seen_at=None,
        digest_last_pushed_at=None,
        updated_at=resolved_now,
    )
