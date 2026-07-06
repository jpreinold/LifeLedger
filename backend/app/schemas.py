import calendar
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ReminderCategory(str, Enum):
    CAR = "Car"
    HEALTH = "Health"
    FINANCE = "Finance"
    HOME = "Home"
    FAMILY = "Family"
    SUBSCRIPTIONS = "Subscriptions"
    OTHER = "Other"


class RepeatOption(str, Enum):
    NONE = "None"
    WEEKLY = "Weekly"
    MONTHLY = "Monthly"
    QUARTERLY = "Quarterly"
    YEARLY = "Yearly"


class PriorityOption(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class ReminderLeadUnit(str, Enum):
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"


class ReminderStatus(str, Enum):
    COMPLETED = "Completed"
    OVERDUE = "Overdue"
    DUE_TODAY = "Due today"
    DUE_THIS_WEEK = "Due this week"
    DUE_THIS_MONTH = "Due this month"
    UPCOMING = "Upcoming"


class ReminderAlertReason(str, Enum):
    OVERDUE = "Overdue"
    DUE_TODAY = "Due today"
    REMINDER_WINDOW = "Reminder window"


class ReminderType(str, Enum):
    GENERIC = "generic"
    BIRTHDAY = "birthday"
    RENEWAL = "renewal"
    MAINTENANCE = "maintenance"


class RenewalKind(str, Enum):
    RENEWAL = "renewal"
    EXPIRATION = "expiration"
    REVIEW = "review"


class MaintenanceArea(str, Enum):
    HOME = "home"
    VEHICLE = "vehicle"
    PET = "pet"
    HEALTH = "health"
    OTHER = "other"


class MaintenanceIntervalUnit(str, Enum):
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"
    YEARS = "years"


class BirthdayDetails(BaseModel):
    person_name: str = Field(..., min_length=1, max_length=120)
    birth_month: int = Field(..., ge=1, le=12)
    birth_day: int = Field(..., ge=1, le=31)
    birth_year: int | None = Field(default=None, ge=1, le=9999)
    age_turning_next_birthday: int | None = Field(default=None, ge=0, le=150)
    inferred_birth_year: bool = False
    relationship: str | None = Field(default=None, max_length=80)

    @field_validator("person_name", mode="before")
    @classmethod
    def normalize_person_name(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("relationship", mode="before")
    @classmethod
    def normalize_relationship(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @model_validator(mode="after")
    def validate_month_day(self) -> "BirthdayDetails":
        last_day = calendar.monthrange(2000, self.birth_month)[1]
        if self.birth_day > last_day:
            raise ValueError("Birth day is not valid for the selected month")

        return self


class RenewalDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_name: str = Field(..., min_length=1, max_length=120)
    renewal_kind: RenewalKind = RenewalKind.RENEWAL
    owner_name: str | None = Field(default=None, max_length=120)
    provider: str | None = Field(default=None, max_length=120)
    renewal_date: date | None = None
    expiration_date: date | None = None
    renewal_window_days: int | None = Field(default=None, ge=0, le=365)
    review_lead_days: int | None = Field(default=None, ge=0, le=365)
    frequency: str | None = Field(default=None, max_length=80)

    @field_validator("item_name", mode="before")
    @classmethod
    def normalize_item_name(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("owner_name", "provider", "frequency", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class MaintenanceDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_name: str = Field(..., min_length=1, max_length=120)
    maintenance_area: MaintenanceArea = MaintenanceArea.OTHER
    last_completed_date: date | None = None
    interval_value: int | None = Field(default=None, ge=1, le=365)
    interval_unit: MaintenanceIntervalUnit | None = None
    next_due_date: date | None = None
    instructions: str | None = Field(default=None, max_length=1000)

    @field_validator("item_name", mode="before")
    @classmethod
    def normalize_item_name(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("instructions", mode="before")
    @classmethod
    def normalize_instructions(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @model_validator(mode="after")
    def validate_schedule(self) -> "MaintenanceDetails":
        has_interval = self.interval_value is not None and self.interval_unit is not None
        has_partial_interval = (self.interval_value is None) != (self.interval_unit is None)
        if has_partial_interval:
            raise ValueError("Maintenance interval needs both a value and a unit")

        if self.next_due_date is None and not (self.last_completed_date is not None and has_interval):
            raise ValueError("Maintenance reminders need a next due date or a last completed date with an interval")

        return self


class ReminderBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    category: ReminderCategory
    due_date: date
    repeat: RepeatOption = RepeatOption.NONE
    priority: PriorityOption = PriorityOption.MEDIUM
    notes: str | None = Field(default=None, max_length=1000)
    reminder_lead_value: int | None = Field(default=None, ge=0, le=36)
    reminder_lead_unit: ReminderLeadUnit | None = None
    reminder_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    reminder_type: ReminderType = ReminderType.GENERIC
    birthday_details: BirthdayDetails | None = None
    renewal_details: RenewalDetails | None = None
    maintenance_details: MaintenanceDetails | None = None

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("reminder_time", mode="before")
    @classmethod
    def normalize_reminder_time(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            return stripped[:5] if len(stripped) >= 5 else stripped
        return value

    @model_validator(mode="after")
    def validate_smart_fields(self) -> "ReminderBase":
        if self.reminder_type == ReminderType.BIRTHDAY and self.birthday_details is None:
            raise ValueError("Birthday reminders require birthday details")

        if self.reminder_type == ReminderType.RENEWAL and self.renewal_details is None:
            raise ValueError("Renewal reminders require renewal details")

        if self.reminder_type == ReminderType.MAINTENANCE and self.maintenance_details is None:
            raise ValueError("Maintenance reminders require maintenance details")

        if self.reminder_type != ReminderType.BIRTHDAY and self.birthday_details is not None:
            raise ValueError("Only birthday reminders can include birthday details")

        if self.reminder_type != ReminderType.RENEWAL and self.renewal_details is not None:
            raise ValueError("Only renewal reminders can include renewal details")

        if self.reminder_type != ReminderType.MAINTENANCE and self.maintenance_details is not None:
            raise ValueError("Only maintenance reminders can include maintenance details")

        return self


class ReminderCreate(ReminderBase):
    pass


class ReminderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    category: ReminderCategory | None = None
    due_date: date | None = None
    repeat: RepeatOption | None = None
    priority: PriorityOption | None = None
    notes: str | None = Field(default=None, max_length=1000)
    reminder_lead_value: int | None = Field(default=None, ge=0, le=36)
    reminder_lead_unit: ReminderLeadUnit | None = None
    reminder_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    reminder_type: ReminderType | None = None
    birthday_details: BirthdayDetails | None = None
    renewal_details: RenewalDetails | None = None
    maintenance_details: MaintenanceDetails | None = None

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("reminder_time", mode="before")
    @classmethod
    def normalize_reminder_time(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            return stripped[:5] if len(stripped) >= 5 else stripped
        return value


class ReminderResponse(ReminderBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    completed: bool
    alert_dismissed_until: datetime | None = None
    alert_last_seen_at: datetime | None = None
    alert_last_action_at: datetime | None = None
    alert_snoozed_until: datetime | None = None
    status: ReminderStatus
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    next_due_date: date | None = None
    computed_label: str | None = None
    birthday_age_label: str | None = None
    renewal_status_label: str | None = None
    renewal_window_label: str | None = None
    maintenance_status_label: str | None = None


class ReminderAlertResponse(ReminderResponse):
    alert_reason: ReminderAlertReason
    alert_reminder_start_date: date | None = None


class AlertSnoozeRequest(BaseModel):
    snoozed_until: datetime | None = None
