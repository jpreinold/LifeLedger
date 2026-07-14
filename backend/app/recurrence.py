import calendar
from datetime import date, datetime, timedelta, timezone

from app.models import Reminder
from app.schemas import ReminderStatus, RepeatOption

URGENT_WINDOW_DAYS = 7
UPCOMING_WINDOW_DAYS = 30


def calculate_status(
    reminder: Reminder,
    today: date | None = None,
    now: datetime | None = None,
) -> ReminderStatus:
    current_day = today or local_today(now)

    if reminder.completed:
        return ReminderStatus.COMPLETED

    effective_attention_date = get_effective_attention_date(reminder, now=now, today=current_day)

    if effective_attention_date < current_day:
        return ReminderStatus.OVERDUE

    if effective_attention_date == current_day:
        return ReminderStatus.DUE_TODAY

    days_until_due = (effective_attention_date - current_day).days
    if days_until_due <= URGENT_WINDOW_DAYS:
        return ReminderStatus.URGENT

    if days_until_due <= UPCOMING_WINDOW_DAYS:
        return ReminderStatus.UPCOMING

    return ReminderStatus.SCHEDULED


def get_effective_attention_date(
    reminder: Reminder,
    *,
    now: datetime | None = None,
    today: date | None = None,
) -> date:
    """Return the date used for attention grouping.

    ``due_date`` is the meaningful renewal, expiration, review, or task date.
    ``snoozed_until`` is a temporary attention deferral. While the snooze is
    still in the future, the reminder is grouped by the snooze date without
    changing the underlying due date.
    """

    current_time = normalize_datetime(now or datetime.now(timezone.utc))
    current_day = today or local_today(current_time)
    snoozed_until = reminder.snoozed_until or reminder.alert_snoozed_until

    if snoozed_until is None:
        return reminder.due_date

    normalized_snooze = normalize_datetime(snoozed_until)
    if normalized_snooze <= current_time:
        return reminder.due_date

    snooze_date = normalized_snooze.date()
    return snooze_date if snooze_date >= current_day else reminder.due_date


def normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def local_today(now: datetime | None = None) -> date:
    if now is None:
        return date.today()

    if now.tzinfo is None:
        return now.date()

    return now.astimezone().date()


def get_next_due_date(due_date: date, repeat: RepeatOption) -> date | None:
    if repeat == RepeatOption.NONE:
        return None

    if repeat == RepeatOption.WEEKLY:
        return due_date + timedelta(weeks=1)

    if repeat == RepeatOption.MONTHLY:
        return _add_months(due_date, 1)

    if repeat == RepeatOption.QUARTERLY:
        return _add_months(due_date, 3)

    if repeat == RepeatOption.YEARLY:
        return _add_months(due_date, 12)

    return None


def advance_due_date(due_date: date, repeat: RepeatOption, today: date | None = None) -> date:
    if repeat == RepeatOption.NONE:
        return due_date

    current_day = today or date.today()
    next_due_date = get_next_due_date(due_date, repeat)

    while next_due_date is not None and next_due_date <= current_day:
        next_due_date = get_next_due_date(next_due_date, repeat)

    if next_due_date is None:
        return due_date

    return next_due_date


def _add_months(start_date: date, months: int) -> date:
    month_index = start_date.month - 1 + months
    year = start_date.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(start_date.day, last_day)
    return date(year, month, day)