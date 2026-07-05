import calendar
from datetime import date, timedelta

from app.schemas import RenewalDetails, RenewalKind


def get_renewal_due_date(details: RenewalDetails) -> date | None:
    return details.renewal_date or details.expiration_date


def get_renewal_target_date(details: RenewalDetails) -> date | None:
    if details.renewal_kind == RenewalKind.EXPIRATION:
        return details.expiration_date or details.renewal_date

    return details.renewal_date or details.expiration_date


def get_renewal_status_label(details: RenewalDetails | None, today: date | None = None) -> str | None:
    if details is None:
        return None

    target_date = get_renewal_target_date(details)
    if target_date is None:
        return "Renewal date unknown"

    current_day = today or date.today()
    days_until_due = (target_date - current_day).days

    if details.renewal_kind == RenewalKind.EXPIRATION:
        return format_expiration_label(days_until_due)

    return format_renewal_label(days_until_due)


def get_renewal_window_label(details: RenewalDetails | None) -> str | None:
    if details is None or details.renewal_window_days is None:
        return None

    target_date = get_renewal_target_date(details)
    if target_date is None:
        return None

    window_start = target_date - timedelta(days=details.renewal_window_days)
    return f"Renewal window starts {format_month_day(window_start)}"


def get_renewal_computed_label(details: RenewalDetails | None, today: date | None = None) -> str | None:
    if details is None:
        return None

    if details.renewal_kind == RenewalKind.REVIEW and details.review_lead_days is not None:
        day_label = "day" if details.review_lead_days == 1 else "days"
        return f"Review {details.review_lead_days} {day_label} before renewal"

    return get_renewal_status_label(details, today=today)


def advance_renewal_details(
    details: RenewalDetails | None,
    previous_due_date: date,
    next_due_date: date,
) -> RenewalDetails | None:
    if details is None:
        return None

    data = details.model_dump()

    if details.renewal_date == previous_due_date:
        data["renewal_date"] = next_due_date

    if details.expiration_date == previous_due_date:
        data["expiration_date"] = next_due_date

    return RenewalDetails.model_validate(data)


def format_renewal_label(days_until_due: int) -> str:
    if days_until_due == 0:
        return "Renews today"

    if days_until_due > 0:
        day_label = "day" if days_until_due == 1 else "days"
        return f"Renews in {days_until_due} {day_label}"

    days_overdue = abs(days_until_due)
    day_label = "day" if days_overdue == 1 else "days"
    return f"Renewal overdue by {days_overdue} {day_label}"


def format_expiration_label(days_until_due: int) -> str:
    if days_until_due == 0:
        return "Expires today"

    if days_until_due > 0:
        day_label = "day" if days_until_due == 1 else "days"
        return f"Expires in {days_until_due} {day_label}"

    days_expired = abs(days_until_due)
    day_label = "day" if days_expired == 1 else "days"
    return f"Expired {days_expired} {day_label} ago"


def format_month_day(value: date) -> str:
    return f"{calendar.month_abbr[value.month]} {value.day}"
