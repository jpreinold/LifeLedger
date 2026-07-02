import calendar
from datetime import date, timedelta

from app.models import Reminder
from app.schemas import ReminderStatus, RepeatOption


def calculate_status(reminder: Reminder, today: date | None = None) -> ReminderStatus:
    current_day = today or date.today()

    if reminder.completed and reminder.repeat == RepeatOption.NONE:
        return ReminderStatus.COMPLETED

    if reminder.due_date < current_day:
        return ReminderStatus.OVERDUE

    if reminder.due_date == current_day:
        return ReminderStatus.DUE_TODAY

    days_until_due = (reminder.due_date - current_day).days
    if days_until_due <= 7:
        return ReminderStatus.DUE_THIS_WEEK

    if reminder.due_date.year == current_day.year and reminder.due_date.month == current_day.month:
        return ReminderStatus.DUE_THIS_MONTH

    return ReminderStatus.UPCOMING


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
