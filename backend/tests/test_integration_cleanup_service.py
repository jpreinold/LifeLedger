from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

from app.integration_cleanup_service import IntegrationCleanupService
from app.models import GoogleCalendarConnection


NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class CalendarReminder:
    id: str
    calendar_event_id: str | None
    calendar_id: str | None = "primary"
    google_calendar_enabled: bool = True
    calendar_last_synced_at: datetime | None = NOW
    calendar_last_error: str | None = None
    updated_at: datetime = NOW

    def model_copy(self, *, update):
        return replace(self, **update)


class ReminderPages:
    def __init__(self, reminders):
        self.reminders = reminders

    def list_reminders_page(self, _user_id, *, limit, cursor=None):
        values = sorted(self.reminders, key=lambda item: item.id)
        if cursor:
            values = [item for item in values if item.id > cursor]
        page = values[:limit]
        return page, page[-1].id if len(values) > limit and page else None

    def update_reminder(self, reminder):
        self.reminders = [reminder if item.id == reminder.id else item for item in self.reminders]
        return reminder


class Connections:
    def __init__(self, connection):
        self.connection = connection
        self.deleted = False

    def get_connection(self, _user_id):
        return None if self.deleted else self.connection

    def save_connection(self, connection):
        self.connection = connection
        return connection

    def delete_connection(self, _user_id):
        self.deleted = True
        return True


class OAuthStates:
    def delete_for_user(self, _user_id, limit=100):
        return 0


class Calendar:
    def __init__(self):
        self.deleted = []
        self.revoked = []

    def delete_event(self, _connection, event_id):
        self.deleted.append(event_id)

    def revoke_token(self, token):
        self.revoked.append(token)


def test_google_cleanup_pages_mapped_events_before_revoking_tokens():
    reminders = ReminderPages(
        [
            CalendarReminder("a", None),
            CalendarReminder("b", "event-b"),
            CalendarReminder("c", "event-c"),
        ]
    )
    connection = GoogleCalendarConnection(
        user_id="user-a",
        access_token="access",
        refresh_token="refresh",
        token_expires_at=NOW + timedelta(days=30),
        scopes="calendar.events",
        connected_at=NOW,
        updated_at=NOW,
    )
    connections = Connections(connection)
    calendar = Calendar()
    service = IntegrationCleanupService(reminders, connections, OAuthStates(), calendar)

    first = service.cleanup_google_calendar("user-a", limit=2)
    second = service.cleanup_google_calendar("user-a", limit=2)

    assert first == 1
    assert second == 1
    assert calendar.deleted == ["event-b", "event-c"]
    assert calendar.revoked == ["refresh"]
    assert connections.deleted is True
