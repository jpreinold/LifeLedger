from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class ReminderStatus(str, Enum):
    COMPLETED = "Completed"
    OVERDUE = "Overdue"
    DUE_TODAY = "Due today"
    DUE_THIS_WEEK = "Due this week"
    DUE_THIS_MONTH = "Due this month"
    UPCOMING = "Upcoming"


class ReminderBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    category: ReminderCategory
    due_date: date
    repeat: RepeatOption = RepeatOption.NONE
    priority: PriorityOption = PriorityOption.MEDIUM
    notes: str | None = Field(default=None, max_length=1000)

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


class ReminderCreate(ReminderBase):
    pass


class ReminderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    category: ReminderCategory | None = None
    due_date: date | None = None
    repeat: RepeatOption | None = None
    priority: PriorityOption | None = None
    notes: str | None = Field(default=None, max_length=1000)

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


class ReminderResponse(ReminderBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    completed: bool
    status: ReminderStatus
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    next_due_date: date | None = None
