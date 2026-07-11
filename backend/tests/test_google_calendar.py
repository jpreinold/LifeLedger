import json
import base64
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.auth import UserContext, get_current_user
from app.config import load_settings
from app.encryption_service import EncryptionService
from app.google_calendar_repository import (
    DynamoGoogleCalendarConnectionRepository,
    DynamoGoogleOAuthStateRepository,
    LocalGoogleCalendarConnectionRepository,
    LocalGoogleOAuthStateRepository,
)
from app.google_calendar_service import (
    GoogleCalendarApiError,
    GoogleCalendarAuthError,
    GoogleCalendarNotFoundError,
    GoogleCalendarOption,
    GoogleTokenSet,
)
from app.main import (
    app,
    get_app_settings,
    get_google_calendar_connection_repository,
    get_google_calendar_service,
    get_google_oauth_state_repository,
    get_repository,
)
from app.models import GoogleCalendarConnection, GoogleOAuthState
from app.repository import LocalReminderRepository
from app.schemas import GoogleCalendarConnectionStatus


@dataclass
class CalendarTestContext:
    client: TestClient
    reminder_repo: LocalReminderRepository
    connection_repo: LocalGoogleCalendarConnectionRepository
    state_repo: LocalGoogleOAuthStateRepository
    calendar_service: "FakeGoogleCalendarService"


class FakeGoogleCalendarService:
    def __init__(self):
        self.created_events: list[dict] = []
        self.updated_events: list[tuple[str, dict, GoogleCalendarConnection]] = []
        self.deleted_events: list[dict] = []
        self.deleted_event_ids: list[str] = []
        self.not_found_deletes: set[str] = set()
        self.delete_error_ids: set[str] = set()
        self.refresh_count = 0
        self.exchanged_codes: list[str] = []
        self.list_auth_error = False
        self.calendar_options = [
            GoogleCalendarOption(id="primary", label="Primary calendar", primary=True, access_role="owner"),
            GoogleCalendarOption(id="family-calendar", label="Family calendar", primary=False, access_role="writer"),
            GoogleCalendarOption(id="work-calendar", label="Work calendar", primary=False, access_role="writerWithoutPrivateAccess"),
        ]

    def build_authorization_url(self, state: str) -> str:
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

    def exchange_authorization_code(self, code: str) -> GoogleTokenSet:
        self.exchanged_codes.append(code)
        return GoogleTokenSet(
            access_token=f"access-{code}",
            refresh_token=f"refresh-{code}",
            token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scopes="https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.calendarlist.readonly",
            google_account_email="person@example.com",
        )

    def refresh_access_token(self, connection: GoogleCalendarConnection) -> GoogleTokenSet:
        self.refresh_count += 1
        return GoogleTokenSet(
            access_token="refreshed-token",
            refresh_token=None,
            token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scopes=connection.scopes,
        )

    def list_calendar_options(self, connection: GoogleCalendarConnection) -> list[GoogleCalendarOption]:
        if self.list_auth_error:
            raise GoogleCalendarAuthError()
        return self.calendar_options

    def create_event(self, connection: GoogleCalendarConnection, event: dict) -> str:
        event_id = f"gcal-{len(self.created_events) + 1}"
        self.created_events.append({"connection": connection, "event": event, "event_id": event_id})
        return event_id

    def update_event(self, connection: GoogleCalendarConnection, event_id: str, event: dict) -> None:
        self.updated_events.append((event_id, event, connection))

    def delete_event(self, connection: GoogleCalendarConnection, event_id: str) -> None:
        if event_id in self.not_found_deletes:
            raise GoogleCalendarNotFoundError()
        if event_id in self.delete_error_ids:
            raise GoogleCalendarApiError()
        self.deleted_events.append({"connection": connection, "event_id": event_id})
        self.deleted_event_ids.append(event_id)


@pytest.fixture()
def calendar_context(tmp_path):
    reminder_repo = LocalReminderRepository(tmp_path / "reminders.json")
    connection_repo = LocalGoogleCalendarConnectionRepository(tmp_path / "connections.json")
    state_repo = LocalGoogleOAuthStateRepository(tmp_path / "states.json")
    calendar_service = FakeGoogleCalendarService()
    settings = load_settings(
        {
            "GOOGLE_CLIENT_ID": "client-id",
            "GOOGLE_CLIENT_SECRET": "client-secret",
            "GOOGLE_OAUTH_REDIRECT_URI": "https://lifeledger.example.com/oauth/google-calendar",
            "GOOGLE_CALENDAR_SCOPES": "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.calendarlist.readonly",
        }
    )

    app.dependency_overrides[get_repository] = lambda: reminder_repo
    app.dependency_overrides[get_google_calendar_connection_repository] = lambda: connection_repo
    app.dependency_overrides[get_google_oauth_state_repository] = lambda: state_repo
    app.dependency_overrides[get_google_calendar_service] = lambda: calendar_service
    app.dependency_overrides[get_app_settings] = lambda: settings

    with TestClient(app) as test_client:
        yield CalendarTestContext(test_client, reminder_repo, connection_repo, state_repo, calendar_service)

    app.dependency_overrides.clear()


def set_auth_user(user_id: str):
    app.dependency_overrides[get_current_user] = lambda: UserContext(user_id=user_id)


def make_payload(**overrides):
    payload = {
        "title": "Renew car tag",
        "category": "Car",
        "due_date": date.today().isoformat(),
        "repeat": "None",
        "priority": "High",
        "notes": "Private notes should not sync.",
    }
    payload.update(overrides)
    return payload


def create_reminder(client: TestClient, **overrides):
    response = client.post("/reminders", json=make_payload(**overrides))
    assert response.status_code == 201
    return response.json()


def save_connection(repo, user_id="local-dev-user", *, expires_at=None, calendar_id="primary", calendar_label=None):
    now = datetime.now(timezone.utc)
    return repo.save_connection(
        GoogleCalendarConnection(
            user_id=user_id,
            google_account_email=f"{user_id}@example.com",
            calendar_id=calendar_id,
            calendar_label=calendar_label,
            access_token="access-token",
            refresh_token="refresh-token",
            token_expires_at=expires_at or now + timedelta(hours=1),
            scopes="https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.calendarlist.readonly",
            connected_at=now,
            updated_at=now,
            status=GoogleCalendarConnectionStatus.CONNECTED,
        )
    )


def test_reminder_create_update_reject_backend_owned_calendar_fields(calendar_context):
    create_response = calendar_context.client.post(
        "/reminders",
        json={**make_payload(), "user_id": "attacker", "calendar_event_id": "external-event"},
    )
    assert create_response.status_code == 422

    created = create_reminder(calendar_context.client)
    update_response = calendar_context.client.put(
        f"/reminders/{created['id']}",
        json={"calendar_event_id": "external-event", "calendar_sync_status": "synced"},
    )
    assert update_response.status_code == 422


def test_status_returns_safe_user_scoped_connection(calendar_context):
    save_connection(calendar_context.connection_repo, "user-a")
    save_connection(calendar_context.connection_repo, "user-b")
    set_auth_user("user-a")

    response = calendar_context.client.get("/integrations/google-calendar/status")

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert body["connected"] is True
    assert body["google_account_email"] == "user-a@example.com"
    assert body["calendar_label"] == "Primary calendar"
    assert "access_token" not in body
    assert "refresh_token" not in body


def test_connect_creates_user_scoped_oauth_state(calendar_context):
    set_auth_user("user-a")

    response = calendar_context.client.post("/integrations/google-calendar/connect")

    assert response.status_code == 200
    state = response.json()["authorization_url"].split("state=")[1]
    saved_state = calendar_context.state_repo.get_state(state)
    assert saved_state is not None
    assert saved_state.user_id == "user-a"
    assert saved_state.expires_at > saved_state.created_at


def test_callback_validates_state_and_stores_tokens_under_current_user(calendar_context):
    set_auth_user("user-a")
    connect_response = calendar_context.client.post("/integrations/google-calendar/connect")
    state = connect_response.json()["authorization_url"].split("state=")[1]

    callback_response = calendar_context.client.post(
        "/integrations/google-calendar/callback",
        json={"code": "auth-code", "state": state},
    )

    assert callback_response.status_code == 200
    body = callback_response.json()
    assert body["connected"] is True
    assert "access_token" not in body
    connection = calendar_context.connection_repo.get_connection("user-a")
    assert connection is not None
    assert connection.access_token == "access-auth-code"
    assert connection.refresh_token == "refresh-auth-code"
    assert calendar_context.state_repo.get_state(state).consumed_at is not None


def test_callback_cannot_attach_tokens_to_wrong_user(calendar_context):
    set_auth_user("user-a")
    connect_response = calendar_context.client.post("/integrations/google-calendar/connect")
    state = connect_response.json()["authorization_url"].split("state=")[1]

    set_auth_user("user-b")
    callback_response = calendar_context.client.post(
        "/integrations/google-calendar/callback",
        json={"code": "auth-code", "state": state},
    )

    assert callback_response.status_code == 400
    assert calendar_context.connection_repo.get_connection("user-a") is None
    assert calendar_context.connection_repo.get_connection("user-b") is None
    assert calendar_context.calendar_service.exchanged_codes == []


@pytest.mark.parametrize(
    ("state_status", "expected_reason"),
    [
        ("missing", "missing_state"),
        ("wrong_user", "wrong_user"),
        ("consumed", "already_consumed"),
        ("expired", "expired"),
    ],
)
def test_callback_logs_safe_invalid_state_reason(calendar_context, caplog, state_status, expected_reason):
    caplog.set_level("WARNING", logger="app.main")
    now = datetime.now(timezone.utc)
    state = f"sensitive-oauth-state-{state_status}"

    if state_status != "missing":
        calendar_context.state_repo.save_state(
            GoogleOAuthState(
                state=state,
                user_id="user-b" if state_status == "wrong_user" else "user-a",
                created_at=now - timedelta(minutes=15),
                expires_at=now - timedelta(minutes=1) if state_status == "expired" else now + timedelta(minutes=10),
                consumed_at=now - timedelta(minutes=1) if state_status == "consumed" else None,
            )
        )

    set_auth_user("user-a")
    response = calendar_context.client.post(
        "/integrations/google-calendar/callback",
        json={"code": "auth-code", "state": state},
    )

    assert response.status_code == 400
    assert expected_reason in caplog.text
    assert state not in caplog.text
    assert calendar_context.calendar_service.exchanged_codes == []


def test_callback_with_consumed_state_returns_current_status_without_reusing_code(calendar_context, caplog):
    caplog.set_level("WARNING", logger="app.main")
    now = datetime.now(timezone.utc)
    state = "sensitive-oauth-state-duplicate"
    save_connection(calendar_context.connection_repo, "user-a")
    calendar_context.state_repo.save_state(
        GoogleOAuthState(
            state=state,
            user_id="user-a",
            created_at=now - timedelta(minutes=5),
            expires_at=now + timedelta(minutes=5),
            consumed_at=now - timedelta(minutes=1),
        )
    )

    set_auth_user("user-a")
    response = calendar_context.client.post(
        "/integrations/google-calendar/callback",
        json={"code": "auth-code", "state": state},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is True
    assert body["google_account_email"] == "user-a@example.com"
    assert "access_token" not in body
    assert "refresh_token" not in body
    assert "already_consumed" in caplog.text
    assert state not in caplog.text
    assert calendar_context.calendar_service.exchanged_codes == []


def test_disconnect_only_disconnects_current_user(calendar_context):
    save_connection(calendar_context.connection_repo, "user-a")
    save_connection(calendar_context.connection_repo, "user-b")
    set_auth_user("user-a")

    response = calendar_context.client.delete("/integrations/google-calendar/disconnect")

    assert response.status_code == 204
    user_a = calendar_context.connection_repo.get_connection("user-a")
    user_b = calendar_context.connection_repo.get_connection("user-b")
    assert user_a.status == GoogleCalendarConnectionStatus.DISCONNECTED
    assert user_a.access_token == ""
    assert user_a.refresh_token == ""
    assert user_b.status == GoogleCalendarConnectionStatus.CONNECTED
    assert user_b.refresh_token == "refresh-token"


def test_calendar_list_returns_safe_user_scoped_writable_calendars(calendar_context):
    save_connection(calendar_context.connection_repo, "user-a", calendar_id="family-calendar", calendar_label="Family calendar")
    save_connection(calendar_context.connection_repo, "user-b")
    set_auth_user("user-a")

    response = calendar_context.client.get("/integrations/google-calendar/calendars")

    assert response.status_code == 200
    body = response.json()
    assert body == [
        {"id": "primary", "label": "Primary calendar", "primary": True, "access_role": "owner", "selected": False},
        {"id": "family-calendar", "label": "Family calendar", "primary": False, "access_role": "writer", "selected": True},
        {"id": "work-calendar", "label": "Work calendar", "primary": False, "access_role": "writerWithoutPrivateAccess", "selected": False},
    ]
    assert "access_token" not in str(body)
    assert "refresh_token" not in str(body)


def test_calendar_list_refreshes_expired_token(calendar_context):
    save_connection(calendar_context.connection_repo, expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))

    response = calendar_context.client.get("/integrations/google-calendar/calendars")

    assert response.status_code == 200
    assert calendar_context.calendar_service.refresh_count == 1
    saved_connection = calendar_context.connection_repo.get_connection("local-dev-user")
    assert saved_connection.access_token == "refreshed-token"


def test_calendar_list_marks_reconnect_when_scope_missing(calendar_context):
    save_connection(calendar_context.connection_repo)
    calendar_context.calendar_service.list_auth_error = True

    response = calendar_context.client.get("/integrations/google-calendar/calendars")

    assert response.status_code == 409
    assert response.json()["detail"] == "Reconnect Google Calendar to choose calendars."
    connection = calendar_context.connection_repo.get_connection("local-dev-user")
    assert connection.status == GoogleCalendarConnectionStatus.NEEDS_RECONNECT


def test_calendar_selection_validates_and_updates_current_user(calendar_context):
    save_connection(calendar_context.connection_repo, "user-a")
    save_connection(calendar_context.connection_repo, "user-b")
    set_auth_user("user-a")

    response = calendar_context.client.put(
        "/integrations/google-calendar/calendar",
        json={"calendar_id": "family-calendar"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["calendar_id"] == "family-calendar"
    assert body["calendar_label"] == "Family calendar"
    user_a = calendar_context.connection_repo.get_connection("user-a")
    user_b = calendar_context.connection_repo.get_connection("user-b")
    assert user_a.calendar_id == "family-calendar"
    assert user_a.calendar_label == "Family calendar"
    assert user_b.calendar_id == "primary"


def test_calendar_selection_rejects_unknown_or_unwritable_calendar(calendar_context):
    save_connection(calendar_context.connection_repo)
    calendar_context.calendar_service.calendar_options.append(
        GoogleCalendarOption(id="readonly-calendar", label="Read-only calendar", primary=False, access_role="reader")
    )

    response = calendar_context.client.put(
        "/integrations/google-calendar/calendar",
        json={"calendar_id": "readonly-calendar"},
    )

    assert response.status_code == 422
    connection = calendar_context.connection_repo.get_connection("local-dev-user")
    assert connection.calendar_id == "primary"


def test_enable_sync_requires_google_connection(calendar_context):
    created = create_reminder(calendar_context.client)

    response = calendar_context.client.post(f"/reminders/{created['id']}/calendar-sync/enable")

    assert response.status_code == 409
    assert calendar_context.calendar_service.created_events == []


def test_enable_sync_creates_event_and_stores_metadata(calendar_context):
    save_connection(calendar_context.connection_repo)
    created = create_reminder(calendar_context.client)

    response = calendar_context.client.post(f"/reminders/{created['id']}/calendar-sync/enable")

    assert response.status_code == 200
    body = response.json()
    assert body["calendar_sync_enabled"] is True
    assert body["calendar_sync_status"] == "synced"
    assert "calendar_event_id" not in body
    saved = calendar_context.reminder_repo.get_reminder("local-dev-user", created["id"])
    assert saved.calendar_event_id == "gcal-1"
    assert len(calendar_context.calendar_service.created_events) == 1
    event = calendar_context.calendar_service.created_events[0]["event"]
    assert event["summary"] == "Renew car tag"
    assert event["start"] == {"date": created["due_date"]}
    assert "Private notes" not in event["description"]


def test_enable_sync_uses_selected_default_calendar(calendar_context):
    save_connection(calendar_context.connection_repo, calendar_id="family-calendar", calendar_label="Family calendar")
    created = create_reminder(calendar_context.client)

    response = calendar_context.client.post(f"/reminders/{created['id']}/calendar-sync/enable")

    assert response.status_code == 200
    saved = calendar_context.reminder_repo.get_reminder("local-dev-user", created["id"])
    assert saved.calendar_id == "family-calendar"
    assert calendar_context.calendar_service.created_events[0]["connection"].calendar_id == "family-calendar"


def test_enable_sync_cannot_sync_another_users_reminder(calendar_context):
    set_auth_user("user-a")
    created = create_reminder(calendar_context.client)
    save_connection(calendar_context.connection_repo, "user-b")

    set_auth_user("user-b")
    response = calendar_context.client.post(f"/reminders/{created['id']}/calendar-sync/enable")

    assert response.status_code == 404
    assert calendar_context.calendar_service.created_events == []


def test_update_synced_reminder_updates_existing_event_without_duplicate(calendar_context):
    save_connection(calendar_context.connection_repo)
    created = create_reminder(calendar_context.client)
    enable_response = calendar_context.client.post(f"/reminders/{created['id']}/calendar-sync/enable")
    event_id = calendar_context.reminder_repo.get_reminder("local-dev-user", created["id"]).calendar_event_id

    update_response = calendar_context.client.put(
        f"/reminders/{created['id']}",
        json={"title": "Renew vehicle registration"},
    )

    assert enable_response.status_code == 200
    assert update_response.status_code == 200
    assert len(calendar_context.calendar_service.created_events) == 1
    assert len(calendar_context.calendar_service.updated_events) == 1
    assert calendar_context.calendar_service.updated_events[0][0] == event_id
    assert calendar_context.calendar_service.updated_events[0][1]["summary"] == "Renew vehicle registration"


def test_update_synced_reminder_uses_stored_calendar_after_default_changes(calendar_context):
    save_connection(calendar_context.connection_repo, calendar_id="primary", calendar_label="Primary calendar")
    created = create_reminder(calendar_context.client)
    calendar_context.client.post(f"/reminders/{created['id']}/calendar-sync/enable")
    connection = calendar_context.connection_repo.get_connection("local-dev-user")
    calendar_context.connection_repo.save_connection(
        connection.model_copy(update={"calendar_id": "family-calendar", "calendar_label": "Family calendar"})
    )

    response = calendar_context.client.put(
        f"/reminders/{created['id']}",
        json={"title": "Renew vehicle registration"},
    )

    assert response.status_code == 200
    assert len(calendar_context.calendar_service.updated_events) == 1
    assert calendar_context.calendar_service.updated_events[0][2].calendar_id == "primary"
    saved = calendar_context.reminder_repo.get_reminder("local-dev-user", created["id"])
    assert saved.calendar_id == "primary"


def test_complete_recurring_synced_reminder_updates_calendar_event_date(calendar_context):
    save_connection(calendar_context.connection_repo)
    yesterday = date.today() - timedelta(days=1)
    created = create_reminder(calendar_context.client, due_date=yesterday.isoformat(), repeat="Weekly")
    calendar_context.client.post(f"/reminders/{created['id']}/calendar-sync/enable")

    complete_response = calendar_context.client.post(f"/reminders/{created['id']}/complete")

    assert complete_response.status_code == 200
    body = complete_response.json()
    assert body["completed"] is False
    assert len(calendar_context.calendar_service.updated_events) == 1
    updated_event = calendar_context.calendar_service.updated_events[0][1]
    assert updated_event["start"] == {"date": body["due_date"]}


def test_disable_sync_deletes_event_and_clears_metadata(calendar_context):
    save_connection(calendar_context.connection_repo)
    created = create_reminder(calendar_context.client)
    calendar_context.client.post(f"/reminders/{created['id']}/calendar-sync/enable")
    event_id = calendar_context.reminder_repo.get_reminder("local-dev-user", created["id"]).calendar_event_id

    response = calendar_context.client.post(f"/reminders/{created['id']}/calendar-sync/disable")

    assert response.status_code == 200
    body = response.json()
    assert body["calendar_sync_enabled"] is False
    assert body["calendar_sync_status"] == "not_synced"
    assert calendar_context.calendar_service.deleted_event_ids == [event_id]
    saved = calendar_context.reminder_repo.get_reminder("local-dev-user", created["id"])
    assert saved.calendar_event_id is None


def test_disable_sync_uses_stored_calendar_after_default_changes(calendar_context):
    save_connection(calendar_context.connection_repo, calendar_id="primary", calendar_label="Primary calendar")
    created = create_reminder(calendar_context.client)
    calendar_context.client.post(f"/reminders/{created['id']}/calendar-sync/enable")
    connection = calendar_context.connection_repo.get_connection("local-dev-user")
    calendar_context.connection_repo.save_connection(
        connection.model_copy(update={"calendar_id": "family-calendar", "calendar_label": "Family calendar"})
    )

    response = calendar_context.client.post(f"/reminders/{created['id']}/calendar-sync/disable")

    assert response.status_code == 200
    assert calendar_context.calendar_service.deleted_events[0]["connection"].calendar_id == "primary"


def test_delete_synced_reminder_cleans_up_calendar_event(calendar_context):
    save_connection(calendar_context.connection_repo)
    created = create_reminder(calendar_context.client)
    calendar_context.client.post(f"/reminders/{created['id']}/calendar-sync/enable")
    event_id = calendar_context.reminder_repo.get_reminder("local-dev-user", created["id"]).calendar_event_id

    response = calendar_context.client.delete(f"/reminders/{created['id']}")

    assert response.status_code == 204
    assert calendar_context.calendar_service.deleted_event_ids == [event_id]
    assert calendar_context.reminder_repo.get_reminder("local-dev-user", created["id"]) is None


def test_delete_synced_reminder_uses_stored_calendar_after_default_changes(calendar_context):
    save_connection(calendar_context.connection_repo, calendar_id="primary", calendar_label="Primary calendar")
    created = create_reminder(calendar_context.client)
    calendar_context.client.post(f"/reminders/{created['id']}/calendar-sync/enable")
    connection = calendar_context.connection_repo.get_connection("local-dev-user")
    calendar_context.connection_repo.save_connection(
        connection.model_copy(update={"calendar_id": "family-calendar", "calendar_label": "Family calendar"})
    )

    response = calendar_context.client.delete(f"/reminders/{created['id']}")

    assert response.status_code == 204
    assert calendar_context.calendar_service.deleted_events[0]["connection"].calendar_id == "primary"


def test_missing_google_event_is_treated_as_cleanup_success(calendar_context):
    save_connection(calendar_context.connection_repo)
    created = create_reminder(calendar_context.client)
    calendar_context.client.post(f"/reminders/{created['id']}/calendar-sync/enable")
    event_id = calendar_context.reminder_repo.get_reminder("local-dev-user", created["id"]).calendar_event_id
    calendar_context.calendar_service.not_found_deletes.add(event_id)

    disable_response = calendar_context.client.post(f"/reminders/{created['id']}/calendar-sync/disable")

    assert disable_response.status_code == 200
    assert disable_response.json()["calendar_sync_status"] == "not_synced"


def test_token_refresh_path_is_used_before_sync(calendar_context):
    save_connection(calendar_context.connection_repo, expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
    created = create_reminder(calendar_context.client)

    response = calendar_context.client.post(f"/reminders/{created['id']}/calendar-sync/enable")

    assert response.status_code == 200
    assert calendar_context.calendar_service.refresh_count == 1
    saved_connection = calendar_context.connection_repo.get_connection("local-dev-user")
    assert saved_connection.access_token == "refreshed-token"


def test_local_json_persistence_for_google_connection_and_state(tmp_path):
    connection_file = tmp_path / "connections.json"
    state_file = tmp_path / "states.json"
    now = datetime.now(timezone.utc)
    first_connection_repo = LocalGoogleCalendarConnectionRepository(connection_file)
    first_state_repo = LocalGoogleOAuthStateRepository(state_file)
    save_connection(first_connection_repo, "user-a", calendar_id="family-calendar", calendar_label="Family calendar")
    first_state_repo.save_state(GoogleOAuthState(state="state-a", user_id="user-a", created_at=now, expires_at=now + timedelta(minutes=10)))

    second_connection_repo = LocalGoogleCalendarConnectionRepository(connection_file)
    second_state_repo = LocalGoogleOAuthStateRepository(state_file)

    saved_connection = second_connection_repo.get_connection("user-a")
    assert saved_connection.google_account_email == "user-a@example.com"
    assert saved_connection.calendar_id == "family-calendar"
    assert saved_connection.calendar_label == "Family calendar"
    assert second_state_repo.get_state("state-a").user_id == "user-a"


class FakeConditionalCheckFailed(Exception):
    response = {"Error": {"Code": "ConditionalCheckFailedException"}}


class FakeDynamoTable:
    def __init__(self, key_name: str):
        self.key_name = key_name
        self.items = {}

    def put_item(self, Item):
        self.items[Item[self.key_name]] = dict(Item)
        return {}

    def get_item(self, Key):
        item = self.items.get(Key[self.key_name])
        return {"Item": item} if item else {}

    def update_item(
        self,
        Key,
        UpdateExpression,
        ConditionExpression,
        ExpressionAttributeNames,
        ExpressionAttributeValues,
        ReturnValues,
    ):
        item = self.items.get(Key[self.key_name])
        if item is None or item.get("consumed_at") is not None:
            raise FakeConditionalCheckFailed()

        item["consumed_at"] = ExpressionAttributeValues[":consumed_at"]
        self.items[Key[self.key_name]] = item
        return {"Attributes": item}

def test_dynamo_google_repositories_store_user_scoped_connection_and_state():
    connection_table = FakeDynamoTable("user_id")
    state_table = FakeDynamoTable("state")
    connection_repo = DynamoGoogleCalendarConnectionRepository("connections", "us-east-1", table=connection_table)
    state_repo = DynamoGoogleOAuthStateRepository("states", "us-east-1", table=state_table)
    now = datetime.now(timezone.utc)

    save_connection(connection_repo, "user-a", calendar_id="family-calendar", calendar_label="Family calendar")
    state_repo.save_state(GoogleOAuthState(state="state-a", user_id="user-a", created_at=now, expires_at=now + timedelta(minutes=10)))

    saved_connection = connection_repo.get_connection("user-a")
    assert saved_connection.google_account_email == "user-a@example.com"
    assert saved_connection.calendar_id == "family-calendar"
    assert saved_connection.calendar_label == "Family calendar"
    assert connection_repo.get_connection("user-b") is None
    assert "consumed_at" not in state_table.items["state-a"]
    consumed = state_repo.consume_state("state-a", now + timedelta(minutes=1))
    assert consumed.user_id == "user-a"
    assert consumed.consumed_at is not None
    assert state_repo.consume_state("state-a", now + timedelta(minutes=2)) is None


def test_dynamo_google_oauth_state_consumes_legacy_null_consumed_at():
    state_table = FakeDynamoTable("state")
    state_repo = DynamoGoogleOAuthStateRepository("states", "us-east-1", table=state_table)
    now = datetime.now(timezone.utc)
    state_table.put_item(
        {
            "state": "state-a",
            "user_id": "user-a",
            "created_at": (now - timedelta(minutes=1)).isoformat(),
            "expires_at": (now + timedelta(minutes=10)).isoformat(),
            "consumed_at": None,
        }
    )

    consumed = state_repo.consume_state("state-a", now)

    assert consumed is not None
    assert consumed.consumed_at == now


def encrypted_settings():
    return load_settings(
        {
            "RECORD_ENCRYPTION_MODE": "local",
            "LOCAL_RECORDS_ENCRYPTION_KEY": base64.b64encode(b"2" * 32).decode("ascii"),
        }
    )


def test_google_connection_repository_encrypts_new_token_bundle(tmp_path):
    connection_file = tmp_path / "connections.json"
    repo = LocalGoogleCalendarConnectionRepository(
        connection_file,
        encryption_service=EncryptionService(encrypted_settings()),
    )

    saved = save_connection(repo, "user-a")

    raw_items = json.loads(connection_file.read_text(encoding="utf-8"))
    raw_item = raw_items[0]
    assert "access_token" not in raw_item
    assert "refresh_token" not in raw_item
    assert raw_item["token_ciphertext"]
    assert raw_item["token_encrypted_data_key"]
    assert "access-token" not in str(raw_item)
    assert "refresh-token" not in str(raw_item)

    loaded = repo.get_connection("user-a")
    assert loaded.access_token == saved.access_token
    assert loaded.refresh_token == saved.refresh_token


def test_legacy_google_token_migration_removes_plaintext_after_success(tmp_path):
    connection_file = tmp_path / "connections.json"
    legacy_repo = LocalGoogleCalendarConnectionRepository(connection_file)
    save_connection(legacy_repo, "user-a")

    repo = LocalGoogleCalendarConnectionRepository(
        connection_file,
        encryption_service=EncryptionService(encrypted_settings()),
    )
    loaded = repo.get_connection("user-a")

    assert loaded.access_token == "access-token"
    assert loaded.refresh_token == "refresh-token"
    raw_item = json.loads(connection_file.read_text(encoding="utf-8"))[0]
    assert "access_token" not in raw_item
    assert "refresh_token" not in raw_item
    assert raw_item["token_ciphertext"]


def test_failed_google_token_migration_keeps_legacy_plaintext_copy(tmp_path, monkeypatch):
    connection_file = tmp_path / "connections.json"
    legacy_repo = LocalGoogleCalendarConnectionRepository(connection_file)
    save_connection(legacy_repo, "user-a")
    repo = LocalGoogleCalendarConnectionRepository(
        connection_file,
        encryption_service=EncryptionService(encrypted_settings()),
    )

    def fail_save(_connection):
        raise RuntimeError("write failed")

    monkeypatch.setattr(repo, "save_connection", fail_save)
    loaded = repo.get_connection("user-a")

    assert loaded.access_token == "access-token"
    raw_item = json.loads(connection_file.read_text(encoding="utf-8"))[0]
    assert raw_item["access_token"] == "access-token"
    assert raw_item["refresh_token"] == "refresh-token"
