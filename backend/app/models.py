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
