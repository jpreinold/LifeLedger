import calendar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from app.models import Reminder
from app.schemas import ReminderAlertReason, ReminderLeadUnit


@dataclass(frozen=True)
class ReminderAlertEligibility:
    reason: ReminderAlertReason
    rank: int
    reminder_start_date: date | None


def get_alert_eligibility(
    reminder: Reminder,
    now: datetime | None = None,
    current_day: date | None = None,
) -> ReminderAlertEligibility | None:
    current_time = normalize_alert_datetime(now or datetime.now(timezone.utc))
    resolved_current_day = current_day or (current_time.date() if now is not None else date.today())

    if reminder.completed or reminder.archived_at is not None:
        return None

    if is_alert_muted(reminder, current_time):
        return None

    if reminder.due_date < resolved_current_day:
        return ReminderAlertEligibility(ReminderAlertReason.OVERDUE, 0, None)

    if reminder.due_date == resolved_current_day:
        return ReminderAlertEligibility(ReminderAlertReason.DUE_TODAY, 1, resolved_current_day)

    reminder_start_date = get_reminder_window_start_date(reminder)
    if reminder_start_date is not None and reminder_start_date <= resolved_current_day <= reminder.due_date:
        return ReminderAlertEligibility(ReminderAlertReason.REMINDER_WINDOW, 2, reminder_start_date)

    return None


def sort_alerts(
    reminders: list[tuple[Reminder, ReminderAlertEligibility]],
) -> list[tuple[Reminder, ReminderAlertEligibility]]:
    return sorted(
        reminders,
        key=lambda item: (
            item[1].rank,
            item[0].due_date,
            item[0].title.casefold(),
        ),
    )


def get_default_alert_until(now: datetime | None = None) -> datetime:
    current_time = normalize_alert_datetime(now or datetime.now(timezone.utc))
    next_day = current_time.date() + timedelta(days=1)
    return datetime.combine(next_day, time(hour=9), tzinfo=timezone.utc)


def normalize_alert_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def is_alert_muted(reminder: Reminder, now: datetime) -> bool:
    current_time = normalize_alert_datetime(now)
    return (
        is_future_datetime(reminder.alert_dismissed_until, current_time)
        or is_future_datetime(reminder.alert_snoozed_until, current_time)
        or is_future_datetime(reminder.snoozed_until, current_time)
    )


def is_future_datetime(value: datetime | None, now: datetime) -> bool:
    if value is None:
        return False

    return normalize_alert_datetime(value) > now


def get_reminder_window_start_date(reminder: Reminder) -> date | None:
    if reminder.reminder_lead_value is None or reminder.reminder_lead_unit is None:
        return None

    lead_value = reminder.reminder_lead_value
    lead_unit = reminder.reminder_lead_unit

    if lead_unit == ReminderLeadUnit.WEEKS:
        return reminder.due_date - timedelta(days=lead_value * 7)

    if lead_unit == ReminderLeadUnit.MONTHS:
        return add_months(reminder.due_date, -lead_value)

    return reminder.due_date - timedelta(days=lead_value)


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(value.day, last_day))


def clear_alert_action_state(now: datetime) -> dict[str, datetime | None]:
    return {
        "alert_dismissed_until": None,
        "alert_snoozed_until": None,
        "snoozed_until": None,
        "alert_last_action_at": now,
    }


def dismiss_alert_state(now: datetime) -> dict[str, datetime | None]:
    return {
        "alert_dismissed_until": get_default_alert_until(now),
        "alert_snoozed_until": None,
        "alert_last_action_at": now,
    }


def snooze_alert_state(now: datetime, snoozed_until: datetime | None = None) -> dict[str, datetime | None]:
    resolved_until = (
        normalize_alert_datetime(snoozed_until) if snoozed_until is not None else get_default_alert_until(now)
    )
    return {
        "alert_snoozed_until": resolved_until,
        "snoozed_until": resolved_until,
        "alert_dismissed_until": None,
        "alert_last_action_at": now,
    }

