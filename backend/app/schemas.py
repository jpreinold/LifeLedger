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


class CalendarSyncStatus(str, Enum):
    NOT_SYNCED = "not_synced"
    SYNCED = "synced"
    NEEDS_ATTENTION = "needs_attention"
    ERROR = "error"


class GoogleCalendarConnectionStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    NEEDS_RECONNECT = "needs_reconnect"


class RecordType(str, Enum):
    GENERAL = "general"
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"
    VEHICLE = "vehicle"
    INSURANCE = "insurance"
    APPLIANCE = "appliance"
    PET = "pet"
    HOME = "home"
    SUBSCRIPTION = "subscription"
    WARRANTY = "warranty"


class RecordStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"

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
    model_config = ConfigDict(extra="forbid")


class ReminderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

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


    calendar_sync_enabled: bool = False
    calendar_provider: str | None = None
    calendar_id: str | None = None
    calendar_last_synced_at: datetime | None = None
    calendar_sync_status: CalendarSyncStatus = CalendarSyncStatus.NOT_SYNCED
    calendar_sync_error: str | None = None
class ReminderAlertResponse(ReminderResponse):
    alert_reason: ReminderAlertReason
    alert_reminder_start_date: date | None = None


class RecordBase(BaseModel):
    record_type: RecordType
    title: str = Field(..., min_length=1, max_length=120)
    subtitle: str | None = Field(default=None, max_length=160)
    category: str = Field(default="General", min_length=1, max_length=80)
    owner_name: str | None = Field(default=None, max_length=120)
    provider_or_brand: str | None = Field(default=None, max_length=120)
    start_date: date | None = None
    issue_date: date | None = None
    expiration_date: date | None = None
    purchase_date: date | None = None
    renewal_date: date | None = None
    location_hint: str | None = Field(default=None, max_length=240)
    notes: str | None = Field(default=None, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=12)
    status: RecordStatus = RecordStatus.ACTIVE

    @field_validator(
        "title",
        "subtitle",
        "owner_name",
        "provider_or_brand",
        "location_hint",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value: str | None) -> str:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or "General"

        return value or "General"

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            raw_tags = value.split(",")
        else:
            raw_tags = value

        normalized: list[str] = []
        seen: set[str] = set()
        for item in raw_tags:
            if not isinstance(item, str):
                continue

            tag = item.strip()
            if not tag:
                continue

            dedupe_key = tag.casefold()
            if dedupe_key in seen:
                continue

            seen.add(dedupe_key)
            normalized.append(tag[:40])

            if len(normalized) >= 12:
                break

        return normalized


class RecordCreate(RecordBase):
    model_config = ConfigDict(extra="forbid")

    status: RecordStatus = RecordStatus.ACTIVE


class RecordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_type: RecordType | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)
    subtitle: str | None = Field(default=None, max_length=160)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    owner_name: str | None = Field(default=None, max_length=120)
    provider_or_brand: str | None = Field(default=None, max_length=120)
    start_date: date | None = None
    issue_date: date | None = None
    expiration_date: date | None = None
    purchase_date: date | None = None
    renewal_date: date | None = None
    location_hint: str | None = Field(default=None, max_length=240)
    notes: str | None = Field(default=None, max_length=1000)
    tags: list[str] | None = Field(default=None, max_length=12)
    status: RecordStatus | None = None

    @field_validator(
        "title",
        "subtitle",
        "category",
        "owner_name",
        "provider_or_brand",
        "location_hint",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return RecordBase.normalize_text(value)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value) -> list[str] | None:
        if value is None:
            return None
        return RecordBase.normalize_tags(value)


class ProtectedRecordPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_number: str | None = Field(default=None, max_length=120)
    license_number: str | None = Field(default=None, max_length=120)
    vin: str | None = Field(default=None, max_length=17)
    policy_number: str | None = Field(default=None, max_length=120)
    member_number: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=120)
    account_reference: str | None = Field(default=None, max_length=120)
    sensitive_notes: str | None = Field(default=None, max_length=1000)

    @field_validator("*", mode="before")
    @classmethod
    def normalize_protected_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("vin")
    @classmethod
    def normalize_vin(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.upper()
        if len(normalized) != 17 or any(character in "IOQ" for character in normalized):
            raise ValueError("VIN must be 17 characters and cannot contain I, O, or Q")
        if not all(character.isdigit() or "A" <= character <= "Z" for character in normalized):
            raise ValueError("VIN can contain only letters and numbers")
        return normalized

    def safe_values(self) -> dict[str, str]:
        data = self.model_dump(exclude_none=True)
        return {key: value for key, value in data.items() if isinstance(value, str) and value}


class ProtectedRecordStatusResponse(BaseModel):
    has_protected_data: bool
    protected_field_names: list[str] = Field(default_factory=list)
    protected_encryption_version: int | None = None
    protected_updated_at: datetime | None = None


class RecordResponse(RecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    has_protected_data: bool = False
    protected_field_names: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AlertSnoozeRequest(BaseModel):
    snoozed_until: datetime | None = None


class DigestPreferencesBase(BaseModel):
    digest_enabled: bool = True
    digest_time: str = Field(default="09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    digest_lookahead_days: int = Field(default=30)
    timezone: str | None = Field(default=None, max_length=120)
    digest_last_seen_at: datetime | None = None

    @field_validator("digest_lookahead_days")
    @classmethod
    def validate_lookahead(cls, value: int) -> int:
        if value not in {7, 14, 30}:
            raise ValueError("Digest lookahead must be 7, 14, or 30 days")

        return value

    @field_validator("timezone", mode="before")
    @classmethod
    def normalize_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class DigestPreferences(DigestPreferencesBase):
    model_config = ConfigDict(from_attributes=True)

    updated_at: datetime


class DigestPreferencesUpdate(BaseModel):
    digest_enabled: bool | None = None
    digest_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    digest_lookahead_days: int | None = None
    timezone: str | None = Field(default=None, max_length=120)
    digest_last_seen_at: datetime | None = None

    @field_validator("digest_lookahead_days")
    @classmethod
    def validate_lookahead(cls, value: int | None) -> int | None:
        if value is not None and value not in {7, 14, 30}:
            raise ValueError("Digest lookahead must be 7, 14, or 30 days")

        return value

    @field_validator("timezone", mode="before")
    @classmethod
    def normalize_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

class GoogleCalendarStatusResponse(BaseModel):
    configured: bool
    connected: bool
    status: GoogleCalendarConnectionStatus
    google_account_email: str | None = None
    calendar_id: str | None = None
    calendar_label: str | None = None
    last_error: str | None = None


class GoogleCalendarOptionResponse(BaseModel):
    id: str
    label: str
    primary: bool = False
    access_role: str
    selected: bool = False


class GoogleCalendarSelectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calendar_id: str = Field(..., min_length=1, max_length=512)


class GoogleCalendarConnectResponse(BaseModel):
    authorization_url: str


class GoogleCalendarCallbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)

class PushSubscriptionKeys(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p256dh: str = Field(..., min_length=1, max_length=512)
    auth: str = Field(..., min_length=1, max_length=256)


class PushSubscriptionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: str = Field(..., min_length=1, max_length=2048)
    keys: PushSubscriptionKeys
    user_agent: str | None = Field(default=None, max_length=512)


class PushSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subscription_id: str
    endpoint: str
    user_agent: str | None = None
    created_at: datetime
    updated_at: datetime
    disabled_at: datetime | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    failure_count: int = 0


class PushConfigurationResponse(BaseModel):
    configured: bool


class PushStatusResponse(BaseModel):
    configured: bool
    active_subscription_count: int
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    failure_count: int = 0
    digest_enabled: bool
    digest_time: str
    timezone: str | None = None


class PushTestResponse(BaseModel):
    sent: int
