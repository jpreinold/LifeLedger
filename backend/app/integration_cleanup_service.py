from __future__ import annotations

from datetime import datetime, timezone

from app.google_calendar_service import GoogleCalendarNotFoundError


class IntegrationCleanupService:
    """Removes external effects before deleting local integration credentials."""

    def __init__(self, reminders, connections, oauth_states, calendar_service):
        self.reminders = reminders
        self.connections = connections
        self.oauth_states = oauth_states
        self.calendar_service = calendar_service

    def cleanup_google_calendar(self, user_id: str, limit: int = 100) -> int:
        connection = self.connections.get_connection(user_id)
        if connection is None:
            self.oauth_states.delete_for_user(user_id, limit=limit)
            return 0
        active_connection = connection
        if connection.token_expires_at <= datetime.now(timezone.utc) and connection.refresh_token:
            tokens = self.calendar_service.refresh_access_token(connection)
            active_connection = connection.model_copy(
                update={
                    "access_token": tokens.access_token,
                    "refresh_token": tokens.refresh_token or connection.refresh_token,
                    "token_expires_at": tokens.token_expires_at,
                    "scopes": tokens.scopes,
                }
            )
        page, next_cursor = self.reminders.list_reminders_page(
            user_id,
            limit=limit,
            cursor=connection.deletion_cleanup_cursor,
        )
        for reminder in page:
            if not reminder.calendar_event_id:
                continue
            target = active_connection.model_copy(
                update={"calendar_id": reminder.calendar_id or active_connection.calendar_id}
            )
            try:
                self.calendar_service.delete_event(target, reminder.calendar_event_id)
            except GoogleCalendarNotFoundError:
                pass
            self.reminders.update_reminder(
                reminder.model_copy(
                    update={
                        "google_calendar_enabled": False,
                        "calendar_event_id": None,
                        "calendar_id": None,
                        "calendar_last_synced_at": None,
                        "calendar_last_error": None,
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
            )
        if next_cursor:
            self.connections.save_connection(
                active_connection.model_copy(
                    update={"deletion_cleanup_cursor": next_cursor, "updated_at": datetime.now(timezone.utc)}
                )
            )
            return 1
        self.calendar_service.revoke_token(active_connection.refresh_token or active_connection.access_token)
        self.oauth_states.delete_for_user(user_id, limit=limit)
        return int(self.connections.delete_connection(user_id))
