import base64
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from app.config import Settings
from app.models import GoogleCalendarConnection, Reminder

GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API_BASE_URL = "https://www.googleapis.com/calendar/v3"
DEFAULT_TIMEOUT_SECONDS = 10


class GoogleCalendarError(Exception):
    safe_message = "Google Calendar sync failed."

    def __init__(self, safe_message: str | None = None):
        if safe_message is not None:
            self.safe_message = safe_message
        super().__init__(self.safe_message)


class GoogleCalendarConfigurationError(GoogleCalendarError):
    safe_message = "Calendar sync is not configured for this environment."


class GoogleCalendarAuthError(GoogleCalendarError):
    safe_message = "Google Calendar needs reconnect."


class GoogleCalendarNotFoundError(GoogleCalendarError):
    safe_message = "Google Calendar event was not found."


class GoogleCalendarApiError(GoogleCalendarError):
    safe_message = "Unable to sync with Google Calendar."


@dataclass(frozen=True)
class GoogleTokenSet:
    access_token: str
    refresh_token: str | None
    token_expires_at: datetime
    scopes: str
    google_account_email: str | None = None


class GoogleCalendarService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def build_authorization_url(self, state: str) -> str:
        self._require_configured()
        params = {
            "client_id": self.settings.google_client_id,
            "redirect_uri": self.settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": self.settings.google_calendar_scopes,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
        return f"{GOOGLE_AUTHORIZATION_URL}?{urlencode(params)}"

    def exchange_authorization_code(self, code: str) -> GoogleTokenSet:
        self._require_configured()
        response = self._post_form(
            GOOGLE_TOKEN_URL,
            {
                "code": code,
                "client_id": self.settings.google_client_id,
                "client_secret": self.settings.google_client_secret,
                "redirect_uri": self.settings.google_oauth_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_set = self._token_set_from_response(response)
        if not token_set.refresh_token:
            raise GoogleCalendarAuthError(
                "Google did not return offline access. Disconnect and connect Google Calendar again."
            )
        return token_set

    def refresh_access_token(self, connection: GoogleCalendarConnection) -> GoogleTokenSet:
        self._require_configured()
        if not connection.refresh_token:
            raise GoogleCalendarAuthError()

        response = self._post_form(
            GOOGLE_TOKEN_URL,
            {
                "client_id": self.settings.google_client_id,
                "client_secret": self.settings.google_client_secret,
                "refresh_token": connection.refresh_token,
                "grant_type": "refresh_token",
            },
        )
        return self._token_set_from_response(response)

    def create_event(self, connection: GoogleCalendarConnection, event: dict[str, Any]) -> str:
        calendar_id = quote(connection.calendar_id, safe="")
        response = self._request_json(
            "POST",
            f"{GOOGLE_CALENDAR_API_BASE_URL}/calendars/{calendar_id}/events",
            connection.access_token,
            json_body=event,
        )
        event_id = response.get("id")
        if not isinstance(event_id, str) or not event_id:
            raise GoogleCalendarApiError()
        return event_id

    def update_event(self, connection: GoogleCalendarConnection, event_id: str, event: dict[str, Any]) -> None:
        calendar_id = quote(connection.calendar_id, safe="")
        encoded_event_id = quote(event_id, safe="")
        self._request_json(
            "PATCH",
            f"{GOOGLE_CALENDAR_API_BASE_URL}/calendars/{calendar_id}/events/{encoded_event_id}",
            connection.access_token,
            json_body=event,
        )

    def delete_event(self, connection: GoogleCalendarConnection, event_id: str) -> None:
        calendar_id = quote(connection.calendar_id, safe="")
        encoded_event_id = quote(event_id, safe="")
        self._request_json(
            "DELETE",
            f"{GOOGLE_CALENDAR_API_BASE_URL}/calendars/{calendar_id}/events/{encoded_event_id}",
            connection.access_token,
        )

    def _require_configured(self) -> None:
        if not self.settings.google_calendar_configured:
            raise GoogleCalendarConfigurationError()

    def _post_form(self, url: str, data: dict[str, str]) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
                response = client.post(url, data=data)
        except httpx.HTTPError as exc:
            raise GoogleCalendarApiError() from exc

        if not response.is_success:
            raise_google_error(response)

        return response.json()

    def _request_json(
        self,
        method: str,
        url: str,
        access_token: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
                response = client.request(
                    method,
                    url,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json=json_body,
                )
        except httpx.HTTPError as exc:
            raise GoogleCalendarApiError() from exc

        if response.status_code in {404, 410}:
            raise GoogleCalendarNotFoundError()
        if not response.is_success:
            raise_google_error(response)
        if response.status_code == 204 or not response.content:
            return {}

        return response.json()

    def _token_set_from_response(self, response: dict[str, Any]) -> GoogleTokenSet:
        access_token = response.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise GoogleCalendarAuthError()

        expires_in = response.get("expires_in")
        expires_seconds = int(expires_in) if isinstance(expires_in, int | float | str) and str(expires_in).isdigit() else 3600
        scope = response.get("scope")
        refresh_token = response.get("refresh_token")

        return GoogleTokenSet(
            access_token=access_token,
            refresh_token=refresh_token if isinstance(refresh_token, str) and refresh_token else None,
            token_expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_seconds),
            scopes=scope if isinstance(scope, str) and scope else self.settings.google_calendar_scopes,
            google_account_email=get_email_from_id_token(response.get("id_token")),
        )


def raise_google_error(response: httpx.Response) -> None:
    if response.status_code in {401, 403}:
        raise GoogleCalendarAuthError()
    if response.status_code in {404, 410}:
        raise GoogleCalendarNotFoundError()
    raise GoogleCalendarApiError()


def get_email_from_id_token(id_token: Any) -> str | None:
    if not isinstance(id_token, str) or id_token.count(".") < 2:
        return None

    try:
        payload = id_token.split(".")[1]
        padding = "=" * ((4 - len(payload) % 4) % 4)
        decoded = base64.urlsafe_b64decode(f"{payload}{padding}".encode("ascii"))
        claims = json.loads(decoded.decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None

    email = claims.get("email")
    return email if isinstance(email, str) and email else None


def build_google_calendar_event(reminder: Reminder, computed_label: str | None = None) -> dict[str, Any]:
    end_date = reminder.due_date + timedelta(days=1)
    description_lines = ["Synced from LifeLedger."]
    if computed_label:
        description_lines.append(f"Label: {computed_label}")

    return {
        "summary": reminder.title,
        "description": "\n".join(description_lines),
        "start": {"date": reminder.due_date.isoformat()},
        "end": {"date": end_date.isoformat()},
        "extendedProperties": {
            "private": {
                "lifeledger_reminder_id": reminder.id,
                "synced_by": "LifeLedger",
            }
        },
    }