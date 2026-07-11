import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.config import Settings
from app.models import PushSubscription
from app.secret_provider import SecretConfigurationError, get_secret_provider


@dataclass(frozen=True)
class PushPayload:
    title: str
    body: str
    url: str
    tag: str
    type: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "title": self.title,
                "body": self.body,
                "url": self.url,
                "tag": self.tag,
                "type": self.type,
            },
            separators=(",", ":"),
        )


class PushSender(Protocol):
    def send(self, subscription: PushSubscription, payload: PushPayload) -> None:
        ...


class PushConfigurationError(Exception):
    pass


class PushSendError(Exception):
    pass


class InvalidPushSubscriptionError(PushSendError):
    pass


class PyWebPushSender:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, subscription: PushSubscription, payload: PushPayload) -> None:
        if not self.settings.push_notifications_configured:
            raise PushConfigurationError("Push notifications are not configured")
        try:
            vapid_private_key = get_secret_provider(self.settings).vapid_private_key()
        except SecretConfigurationError as exc:
            raise PushConfigurationError("Push notifications are not configured") from exc

        try:
            from pywebpush import WebPushException, webpush
        except ImportError as exc:
            raise PushConfigurationError("pywebpush is not installed") from exc

        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh,
                "auth": subscription.auth,
            },
        }

        try:
            webpush(
                subscription_info=subscription_info,
                data=payload.to_json(),
                vapid_private_key=vapid_private_key,
                vapid_claims={"sub": self.settings.vapid_subject},
            )
        except WebPushException as exc:
            status_code = get_response_status_code(exc)
            if status_code in {404, 410}:
                raise InvalidPushSubscriptionError("Push subscription is gone") from exc
            raise PushSendError("Push send failed") from exc


def get_response_status_code(exc: Any) -> int | None:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    return status_code if isinstance(status_code, int) else None
