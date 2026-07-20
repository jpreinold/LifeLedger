from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import calendar
import re


class BirthdayValueError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedBirthday:
    month: int
    day: int
    year: int | None = None

    @property
    def stored_value(self) -> str:
        if self.year is None:
            return f"--{self.month:02d}-{self.day:02d}"
        return f"{self.year:04d}-{self.month:02d}-{self.day:02d}"


def parse_birthday_value(value: object, *, today: date | None = None) -> ParsedBirthday:
    text = str(value).strip()
    month_day = re.fullmatch(r"--(\d{2})-(\d{2})", text)
    full_date = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if not month_day and not full_date:
        raise BirthdayValueError("Birthdays must include a month and day; the year is optional.")

    year = int(full_date.group(1)) if full_date else None
    month = int((full_date or month_day).group(2 if full_date else 1))
    day = int((full_date or month_day).group(3 if full_date else 2))
    try:
        date(year or 2000, month, day)
    except ValueError as exc:
        raise BirthdayValueError("Choose a valid birthday.") from exc

    parsed = ParsedBirthday(month=month, day=day, year=year)
    if year is not None:
        current_day = today or date.today()
        candidate_day = min(day, calendar.monthrange(current_day.year, month)[1])
        candidate = date(current_day.year, month, candidate_day)
        due_year = current_day.year + 1 if candidate < current_day else current_day.year
        due_date = date(due_year, month, min(day, calendar.monthrange(due_year, month)[1]))
        age = due_date.year - year
        if age < 0 or age > 150:
            raise BirthdayValueError("Birth year must produce an age between 0 and 150.")
    return parsed
