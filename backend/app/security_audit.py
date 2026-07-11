import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("app.security")


def user_hash(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()


def log_security_event(event: str, user_id: str | None = None, **fields: Any) -> None:
    safe_fields = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    if user_id is not None:
        safe_fields["user_hash"] = user_hash(user_id)

    logger.info("security_audit %s", safe_fields)
