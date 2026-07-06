import calendar
from datetime import date, timedelta

from app.schemas import MaintenanceDetails, MaintenanceIntervalUnit


def get_maintenance_due_date(details: MaintenanceDetails | None) -> date | None:
    if details is None:
        return None

    if details.next_due_date is not None:
        return details.next_due_date

    if details.last_completed_date is not None and details.interval_value is not None and details.interval_unit is not None:
        return add_maintenance_interval(details.last_completed_date, details.interval_value, details.interval_unit)

    return None


def prepare_maintenance_details(details: MaintenanceDetails) -> MaintenanceDetails:
    next_due_date = get_maintenance_due_date(details)
    if next_due_date is None:
        return details

    return details.model_copy(update={"next_due_date": next_due_date})


def advance_maintenance_details(details: MaintenanceDetails, completed_on: date) -> MaintenanceDetails:
    updates = {"last_completed_date": completed_on}
    if details.interval_value is not None and details.interval_unit is not None:
        updates["next_due_date"] = add_maintenance_interval(completed_on, details.interval_value, details.interval_unit)

    return details.model_copy(update=updates)


def get_maintenance_status_label(details: MaintenanceDetails | None, today: date | None = None) -> str | None:
    due_date = get_maintenance_due_date(details)
    if details is None or due_date is None:
        return "Maintenance schedule unknown"

    current_day = today or date.today()
    days_until_due = (due_date - current_day).days

    if days_until_due == 0:
        return "Due today"

    if days_until_due == 1:
        return "Due tomorrow"

    if days_until_due < 0:
        days_past = abs(days_until_due)
        return f"Overdue by {format_count(days_past, 'day')}"

    if days_until_due >= 14 and days_until_due % 7 == 0:
        return f"Due in {format_count(days_until_due // 7, 'week')}"

    return f"Due in {format_count(days_until_due, 'day')}"


def get_maintenance_schedule_label(details: MaintenanceDetails | None) -> str | None:
    if details is None or details.interval_value is None or details.interval_unit is None:
        return None

    if details.interval_value == 1:
        return f"Every {details.interval_unit.value[:-1]}"

    return f"Every {details.interval_value} {details.interval_unit.value}"


def get_maintenance_last_done_label(details: MaintenanceDetails | None) -> str | None:
    if details is None or details.last_completed_date is None:
        return None

    return f"Last done {format_month_day(details.last_completed_date)}"


def get_maintenance_next_due_label(details: MaintenanceDetails | None) -> str | None:
    due_date = get_maintenance_due_date(details)
    if due_date is None:
        return None

    return f"Next due {format_month_day(due_date)}"


def get_maintenance_computed_label(details: MaintenanceDetails | None, today: date | None = None) -> str | None:
    if details is None:
        return "Maintenance schedule unknown"

    schedule_label = get_maintenance_schedule_label(details)
    status_label = get_maintenance_status_label(details, today=today)

    if schedule_label and status_label and status_label != "Maintenance schedule unknown":
        return f"{schedule_label} \u2022 {status_label}"

    return schedule_label or status_label


def add_maintenance_interval(start_date: date, value: int, unit: MaintenanceIntervalUnit) -> date:
    if unit == MaintenanceIntervalUnit.DAYS:
        return start_date + timedelta(days=value)

    if unit == MaintenanceIntervalUnit.WEEKS:
        return start_date + timedelta(weeks=value)

    if unit == MaintenanceIntervalUnit.MONTHS:
        return add_months(start_date, value)

    if unit == MaintenanceIntervalUnit.YEARS:
        return add_months(start_date, value * 12)

    return start_date


def add_months(start_date: date, months: int) -> date:
    month_index = start_date.month - 1 + months
    year = start_date.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(start_date.day, last_day)
    return date(year, month, day)


def format_count(value: int, noun: str) -> str:
    return f"{value} {noun if value == 1 else noun + 's'}"


def format_month_day(value: date) -> str:
    return f"{value.strftime('%b')} {value.day}"