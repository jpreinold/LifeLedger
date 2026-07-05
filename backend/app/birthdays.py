import calendar
from datetime import date

from app.schemas import BirthdayDetails


def get_next_birthday_due_date(birth_month: int, birth_day: int, today: date | None = None) -> date:
    current_day = today or date.today()
    candidate = birthday_date_for_year(current_day.year, birth_month, birth_day)

    if candidate < current_day:
        return birthday_date_for_year(current_day.year + 1, birth_month, birth_day)

    return candidate


def birthday_date_for_year(year: int, birth_month: int, birth_day: int) -> date:
    if birth_month == 2 and birth_day == 29 and not calendar.isleap(year):
        return date(year, 2, 28)

    return date(year, birth_month, birth_day)


def enrich_birthday_details(details: BirthdayDetails, due_date: date) -> BirthdayDetails:
    data = details.model_dump()

    if details.birth_year is not None:
        age_turning = due_date.year - details.birth_year
        if age_turning < 0 or age_turning > 150:
            raise ValueError("Birth year must produce an age between 0 and 150")

        data["age_turning_next_birthday"] = age_turning
        return BirthdayDetails.model_validate(data)

    if details.age_turning_next_birthday is not None:
        data["birth_year"] = due_date.year - details.age_turning_next_birthday
        data["inferred_birth_year"] = True
        return BirthdayDetails.model_validate(data)

    data["age_turning_next_birthday"] = None
    data["inferred_birth_year"] = False
    return BirthdayDetails.model_validate(data)


def get_birthday_age_label(details: BirthdayDetails | None) -> str | None:
    if details is None:
        return None

    if details.age_turning_next_birthday is None:
        return "Age unknown"

    return f"Turning {details.age_turning_next_birthday}"


def get_birthday_computed_label(
    details: BirthdayDetails | None,
    due_date: date,
    today: date | None = None,
) -> str | None:
    if details is None:
        return None

    age_turning = details.age_turning_next_birthday
    if age_turning is None:
        return "Age unknown"

    current_day = today or date.today()
    days_until_due = (due_date - current_day).days

    if days_until_due == 0:
        return f"Turns {age_turning} today"

    if days_until_due == 1:
        return f"Turns {age_turning} tomorrow"

    if days_until_due == 7:
        return f"Turns {age_turning} in 1 week"

    if 1 < days_until_due <= 14:
        return f"Turns {age_turning} in {days_until_due} days"

    if days_until_due < 0:
        return f"Turned {age_turning} on {format_month_day(due_date)}"

    return f"Turns {age_turning} on {format_month_day(due_date)}"


def format_month_day(value: date) -> str:
    return f"{calendar.month_abbr[value.month]} {value.day}"
