from datetime import date

from app.birthdays import (
    birthday_date_for_year,
    get_birthday_computed_label,
    get_next_birthday_due_date,
)
from app.schemas import BirthdayDetails


def test_next_birthday_uses_this_year_when_later():
    assert get_next_birthday_due_date(8, 12, today=date(2026, 7, 5)) == date(2026, 8, 12)


def test_next_birthday_uses_next_year_when_already_passed():
    assert get_next_birthday_due_date(3, 4, today=date(2026, 7, 5)) == date(2027, 3, 4)


def test_next_birthday_uses_today_when_birthday_is_today():
    assert get_next_birthday_due_date(7, 5, today=date(2026, 7, 5)) == date(2026, 7, 5)


def test_feb_29_birthday_uses_feb_28_on_non_leap_years():
    assert birthday_date_for_year(2027, 2, 29) == date(2027, 2, 28)
    assert birthday_date_for_year(2028, 2, 29) == date(2028, 2, 29)


def test_birthday_computed_label_handles_relative_days():
    details = BirthdayDetails(
        person_name="Max",
        birth_month=7,
        birth_day=11,
        birth_year=1999,
        age_turning_next_birthday=27,
    )

    assert get_birthday_computed_label(details, date(2026, 7, 5), today=date(2026, 7, 5)) == "Turns 27 today"
    assert get_birthday_computed_label(details, date(2026, 7, 6), today=date(2026, 7, 5)) == "Turns 27 tomorrow"
    assert get_birthday_computed_label(details, date(2026, 7, 11), today=date(2026, 7, 5)) == "Turns 27 in 6 days"
