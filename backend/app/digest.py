from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.alerts import get_alert_eligibility, sort_alerts
from app.models import Reminder


@dataclass(frozen=True)
class DailyDigestSummary:
    needs_attention: int
    due_today: int
    coming_up: int

    @property
    def has_items(self) -> bool:
        return self.needs_attention > 0 or self.due_today > 0 or self.coming_up > 0

    def to_push_body(self) -> str:
        return (
            f"{self.needs_attention} needs attention "
            f"\u2022 {self.due_today} due today "
            f"\u2022 {self.coming_up} coming up"
        )


def build_daily_digest_summary(
    reminders: list[Reminder],
    *,
    lookahead_days: int,
    now: datetime,
    current_day: date | None = None,
) -> DailyDigestSummary:
    resolved_current_day = current_day or now.date()
    used_reminder_ids: set[str] = set()
    active_reminders = [reminder for reminder in reminders if not reminder.completed]

    alert_reminders = []
    for reminder in reminders:
        eligibility = get_alert_eligibility(reminder, now=now, current_day=resolved_current_day)
        if eligibility is not None:
            alert_reminders.append((reminder, eligibility))
            used_reminder_ids.add(reminder.id)

    sorted_alerts = sort_alerts(alert_reminders)

    due_today = [
        reminder
        for reminder in active_reminders
        if reminder.id not in used_reminder_ids and reminder.due_date == resolved_current_day
    ]
    for reminder in due_today:
        used_reminder_ids.add(reminder.id)

    lookahead_end = resolved_current_day + timedelta(days=lookahead_days)
    coming_up = [
        reminder
        for reminder in active_reminders
        if reminder.id not in used_reminder_ids and resolved_current_day < reminder.due_date <= lookahead_end
    ]

    return DailyDigestSummary(
        needs_attention=len(sorted_alerts),
        due_today=len(due_today),
        coming_up=len(coming_up),
    )
