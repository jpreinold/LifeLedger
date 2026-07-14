from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from app.models import Reminder
from app.schemas import ReminderLifecycleEvent, ReminderLifecycleEventType

MAX_LIFECYCLE_EVENTS = 50
RECENT_ACTION_WINDOW_SECONDS = 3


def append_lifecycle_event(
    reminder: Reminder,
    *,
    event_type: ReminderLifecycleEventType,
    occurred_at: datetime,
    summary: str,
    previous_due_date: date | None = None,
    new_due_date: date | None = None,
    snoozed_until: datetime | None = None,
) -> list[ReminderLifecycleEvent]:
    event = ReminderLifecycleEvent(
        event_id=str(uuid4()),
        event_type=event_type,
        occurred_at=occurred_at,
        summary=summary,
        previous_due_date=previous_due_date,
        new_due_date=new_due_date,
        snoozed_until=snoozed_until,
    )
    return [*reminder.lifecycle_events, event][-MAX_LIFECYCLE_EVENTS:]


def has_recent_lifecycle_action(
    reminder: Reminder,
    event_type: ReminderLifecycleEventType,
    now: datetime,
    *,
    seconds: int = RECENT_ACTION_WINDOW_SECONDS,
) -> bool:
    if not reminder.lifecycle_events:
        return False

    latest = reminder.lifecycle_events[-1]
    if latest.event_type != event_type:
        return False

    occurred_at = normalize_datetime(latest.occurred_at)
    return now - occurred_at <= timedelta(seconds=seconds)


def normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)
