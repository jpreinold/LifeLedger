from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas import (
    BirthdayDetails,
    MaintenanceDetails,
    PriorityOption,
    ReminderCategory,
    ReminderLeadUnit,
    ReminderType,
    RenewalDetails,
    RepeatOption,
)


class Reminder(BaseModel):
    id: str
    user_id: str = "local-dev-user"
    title: str
    category: ReminderCategory
    due_date: date
    repeat: RepeatOption = RepeatOption.NONE
    priority: PriorityOption = PriorityOption.MEDIUM
    notes: str | None = None
    reminder_lead_value: int | None = None
    reminder_lead_unit: ReminderLeadUnit | None = None
    reminder_time: str | None = None
    reminder_type: ReminderType = ReminderType.GENERIC
    birthday_details: BirthdayDetails | None = None
    renewal_details: RenewalDetails | None = None
    maintenance_details: MaintenanceDetails | None = None
    completed: bool = False
    created_at: datetime
    alert_dismissed_until: datetime | None = None
    alert_last_seen_at: datetime | None = None
    alert_last_action_at: datetime | None = None
    alert_snoozed_until: datetime | None = None
    updated_at: datetime
    completed_at: datetime | None = None


class ReminderPatch(BaseModel):
    title: str | None = None
    category: ReminderCategory | None = None
    due_date: date | None = None
    repeat: RepeatOption | None = None
    priority: PriorityOption | None = None
    notes: str | None = Field(default=None)
    reminder_lead_value: int | None = None
    reminder_lead_unit: ReminderLeadUnit | None = None
    reminder_time: str | None = None
    reminder_type: ReminderType | None = None
    birthday_details: BirthdayDetails | None = None
    renewal_details: RenewalDetails | None = None
    maintenance_details: MaintenanceDetails | None = None


class UserPreferences(BaseModel):
    user_id: str
    digest_enabled: bool = True
    digest_time: str = "09:00"
    digest_lookahead_days: int = 30
    timezone: str | None = None
    digest_last_seen_at: datetime | None = None
    digest_last_pushed_at: datetime | None = None
    updated_at: datetime


class PushSubscription(BaseModel):
    user_id: str
    subscription_id: str
    endpoint: str
    p256dh: str
    auth: str
    user_agent: str | None = None
    created_at: datetime
    updated_at: datetime
    disabled_at: datetime | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    failure_count: int = 0
