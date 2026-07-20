from __future__ import annotations

import calendar
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.birthday_value import BirthdayValueError, parse_birthday_value


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
    URGENT = "Urgent"
    UPCOMING = "Upcoming"
    SCHEDULED = "Scheduled"


class ReminderLifecycleEventType(str, Enum):
    CREATED = "created"
    EDITED = "edited"
    DATE_CHANGED = "date_changed"
    SNOOZED = "snoozed"
    SNOOZE_CLEARED = "snooze_cleared"
    COMPLETED = "completed"
    RENEWED = "renewed"
    ARCHIVED = "archived"
    RESTORED = "restored"


class ResponsibilityWorkflowId(str, Enum):
    PASSPORT_EXPIRATION = "passport_expiration"
    VEHICLE_REGISTRATION = "vehicle_registration"
    PET_VACCINATION = "pet_vaccination"
    SUBSCRIPTION_RENEWAL = "subscription_renewal"
    PERSON_BIRTHDAY = "person_birthday"


class ResponsibilityEventType(str, Enum):
    RESPONSIBILITY_CREATED = "responsibility_created"
    COMPLETED = "completed"
    RENEWED = "renewed"
    SNOOZED = "snoozed"
    SNOOZE_CLEARED = "snooze_cleared"
    REOPENED = "reopened"
    DUE_DATE_CHANGED = "due_date_changed"
    SUPPORTING_DOCUMENT_ADDED = "supporting_document_added"
    HISTORY_TRACKING_STARTED = "history_tracking_started"


class ResponsibilityEventSource(str, Enum):
    USER = "user"
    GUIDED_WORKFLOW = "guided_workflow"
    RECONCILIATION = "reconciliation"
    ASSISTANT_CAPTURE = "assistant_capture"
    SYSTEM = "system"


class LifecycleReconciliationStatus(str, Enum):
    PENDING = "pending"
    CONSISTENT = "consistent"
    NEEDS_ATTENTION = "needs_attention"


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
    PERSON = "person"


class RecordStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class DynamicFieldType(str, Enum):
    SHORT_TEXT = "short_text"
    LONG_TEXT = "long_text"
    DATE = "date"
    NUMBER = "number"
    MONEY = "money"
    PHONE = "phone"
    EMAIL = "email"
    URL = "url"
    BOOLEAN = "boolean"
    SELECT = "select"


class LinkedEntityType(str, Enum):
    RECORD = "record"
    REMINDER = "reminder"
    DOCUMENT = "document"


class RelationshipType(str, Enum):
    RELATED_TO = "related_to"
    RELATED = "related"
    BELONGS_TO = "belongs_to"
    OWNED_BY = "owned_by"
    COVERS = "covers"
    PROVIDED_BY = "provided_by"
    REMINDER_FOR = "reminder_for"
    RENEWS = "renews"
    MAINTAINS = "maintains"
    INSURES = "insures"
    WARRANTY_FOR = "warranty_for"
    DOCUMENT_FOR = "document_for"
    APPOINTMENT_FOR = "appointment_for"
    ASSOCIATED_WITH = "associated_with"
    CUSTOM = "custom"


class LinkDirection(str, Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class AttachmentStatus(str, Enum):
    PENDING_UPLOAD = "pending_upload"
    UPLOADED = "uploaded"
    SCANNING = "scanning"
    AVAILABLE = "available"
    REJECTED = "rejected"
    SCAN_FAILED = "scan_failed"
    DELETING = "deleting"
    DELETED = "deleted"


class AttachmentScanResult(str, Enum):
    PENDING = "pending"
    NO_THREATS_FOUND = "no_threats_found"
    THREATS_FOUND = "threats_found"
    UNSUPPORTED = "unsupported"
    ACCESS_DENIED = "access_denied"
    FAILED = "failed"


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
    subject_type: RecordType = RecordType.PERSON
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
        if self.subject_type not in {RecordType.PERSON, RecordType.PET}:
            raise ValueError("Birthday reminders can be linked only to a person or pet")
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
    workflow_id: ResponsibilityWorkflowId | None = None

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


class ReminderLifecycleEvent(BaseModel):
    event_id: str
    event_type: ReminderLifecycleEventType
    occurred_at: datetime
    summary: str = Field(..., min_length=1, max_length=240)
    actor: str = Field(default="user", max_length=40)
    previous_due_date: date | None = None
    new_due_date: date | None = None
    snoozed_until: datetime | None = None


class ReminderLinkedRecordSummary(BaseModel):
    id: str
    title: str
    subtitle: str | None = None
    record_type: RecordType
    status: RecordStatus


class ReminderSnoozeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snoozed_until: datetime


class ReminderRenewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_due_date: date
    renewed_on: date | None = None
    occurrence_id: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ReminderCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed_on: date | None = None
    occurrence_id: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ResponsibilityEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str = Field(..., min_length=1, max_length=120)
    document_id: str = Field(..., min_length=1, max_length=120)
    occurrence_id: str | None = Field(default=None, max_length=120)
    related_event_id: str | None = Field(default=None, max_length=120)


class ReminderResponse(ReminderBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    completed: bool
    alert_dismissed_until: datetime | None = None
    alert_last_seen_at: datetime | None = None
    alert_last_action_at: datetime | None = None
    alert_snoozed_until: datetime | None = None
    snoozed_until: datetime | None = None
    archived_at: datetime | None = None
    status: ReminderStatus
    effective_attention_date: date
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    current_occurrence_id: str | None = None
    lifecycle_reconciliation_status: LifecycleReconciliationStatus | None = None
    last_lifecycle_event_id: str | None = None
    lifecycle_events: list[ReminderLifecycleEvent] = Field(default_factory=list)
    linked_records: list[ReminderLinkedRecordSummary] = Field(default_factory=list)
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


class ResponsibilityDocumentEvidence(BaseModel):
    document_id: str
    record_id: str | None = None
    display_name: str
    status: str
    available: bool = False


class ResponsibilityEventResponse(BaseModel):
    event_id: str
    reminder_id: str
    item_id: str | None = None
    occurrence_id: str | None = None
    event_type: ResponsibilityEventType
    occurred_at: datetime
    effective_date: date | None = None
    previous_due_date: date | None = None
    next_due_date: date | None = None
    completed_at: datetime | None = None
    note: str | None = None
    source: ResponsibilityEventSource
    schema_version: int
    created_at: datetime
    responsibility_title_snapshot: str | None = None
    item_title_snapshot: str | None = None
    item_type_snapshot: RecordType | None = None
    related_event_id: str | None = None
    reconciliation_status: LifecycleReconciliationStatus
    search_sync_status: LifecycleReconciliationStatus
    document_reference_status: LifecycleReconciliationStatus
    documents: list[ResponsibilityDocumentEvidence] = Field(default_factory=list)


class ResponsibilityHistoryPage(BaseModel):
    items: list[ResponsibilityEventResponse] = Field(default_factory=list)
    next_cursor: str | None = None


class LifecycleReconciliationResult(BaseModel):
    reminder_id: str
    dry_run: bool = False
    inspected: int = 0
    repaired: int = 0
    remaining: int = 0
    results: list[str] = Field(default_factory=list)


class LifecycleReconciliationPage(BaseModel):
    items: list[LifecycleReconciliationResult] = Field(default_factory=list)
    next_cursor: str | None = None


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
    birthday: str | None = Field(default=None, max_length=10)
    birthday_inferred_birth_year: int | None = Field(default=None, ge=1, le=9999)
    relationship_context: str | None = Field(default=None, max_length=80)
    location_hint: str | None = Field(default=None, max_length=240)
    notes: str | None = Field(default=None, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=12)
    status: RecordStatus = RecordStatus.ACTIVE

    @field_validator(
        "title",
        "subtitle",
        "owner_name",
        "provider_or_brand",
        "relationship_context",
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

    @field_validator("birthday", mode="before")
    @classmethod
    def normalize_birthday(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return parse_birthday_value(value).stored_value
        except BirthdayValueError as exc:
            raise ValueError(str(exc)) from exc

    @model_validator(mode="after")
    def validate_birthday_subject(self) -> "RecordBase":
        if self.birthday is not None and self.record_type not in {RecordType.PERSON, RecordType.PET}:
            raise ValueError("Birthday is available only for Person and Pet items.")
        if self.birthday_inferred_birth_year is not None:
            if self.record_type not in {RecordType.PERSON, RecordType.PET}:
                raise ValueError("A calculated birth year is available only for Person and Pet items.")
            if self.birthday is None or not self.birthday.startswith("--"):
                raise ValueError("A calculated birth year requires a birthday with an unknown year.")
            try:
                parse_birthday_value(f"{self.birthday_inferred_birth_year:04d}{self.birthday[1:]}")
            except BirthdayValueError as exc:
                raise ValueError(str(exc)) from exc
        if self.relationship_context is not None and self.record_type != RecordType.PERSON:
            raise ValueError("Relationship is available only for Person items.")
        return self


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
    birthday: str | None = Field(default=None, max_length=10)
    birthday_inferred_birth_year: int | None = Field(default=None, ge=1, le=9999)
    relationship_context: str | None = Field(default=None, max_length=80)
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
        "relationship_context",
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

    @field_validator("birthday", mode="before")
    @classmethod
    def normalize_birthday(cls, value: str | None) -> str | None:
        return RecordBase.normalize_birthday(value)


DynamicFieldValue = str | int | float | bool | None


class DynamicRecordFieldBase(BaseModel):
    label: str = Field(..., min_length=1, max_length=80)
    field_type: DynamicFieldType
    value: DynamicFieldValue = None
    is_sensitive: bool = False
    select_options: list[str] = Field(default_factory=list, max_length=20)
    display_order: int | None = Field(default=None, ge=0, le=10_000)

    @field_validator("label", mode="before")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("select_options", mode="before")
    @classmethod
    def normalize_select_options(cls, value) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Select options must be a list")

        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                raise ValueError("Select options must be text")
            option = item.strip()
            if not option:
                continue
            option = option[:60]
            key = option.casefold()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(option)
            if len(normalized) >= 20:
                break
        return normalized

    @model_validator(mode="after")
    def validate_value_for_type(self) -> "DynamicRecordFieldBase":
        self.value = normalize_dynamic_field_value(self.field_type, self.value, self.select_options)
        return self


class DynamicRecordFieldCreate(DynamicRecordFieldBase):
    model_config = ConfigDict(extra="forbid")

    key: str | None = Field(default=None, max_length=80)

    @field_validator("key", mode="before")
    @classmethod
    def normalize_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class DynamicRecordFieldUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, min_length=1, max_length=80)
    value: DynamicFieldValue = None
    field_type: DynamicFieldType | None = None
    is_sensitive: bool | None = None
    select_options: list[str] | None = Field(default=None, max_length=20)
    display_order: int | None = Field(default=None, ge=0, le=10_000)

    @field_validator("label", mode="before")
    @classmethod
    def normalize_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("select_options", mode="before")
    @classmethod
    def normalize_select_options(cls, value) -> list[str] | None:
        if value is None:
            return None
        return DynamicRecordFieldBase.normalize_select_options(value)


class DynamicRecordFieldResponse(BaseModel):
    field_id: str
    key: str
    label: str
    field_type: DynamicFieldType
    value: DynamicFieldValue = None
    is_sensitive: bool = False
    has_value: bool = False
    display_order: int = 0
    select_options: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DynamicRecordFieldRevealResponse(BaseModel):
    field_id: str
    value: DynamicFieldValue


def normalize_dynamic_field_value(
    field_type: DynamicFieldType,
    value: DynamicFieldValue,
    select_options: list[str] | None = None,
) -> DynamicFieldValue:
    if value is None:
        return None

    if isinstance(value, bool):
        if field_type == DynamicFieldType.BOOLEAN:
            return value
        if field_type in {DynamicFieldType.SHORT_TEXT, DynamicFieldType.LONG_TEXT, DynamicFieldType.SELECT}:
            value = "Yes" if value else "No"
        else:
            raise ValueError("Value type is not valid for this field")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if field_type in {DynamicFieldType.NUMBER, DynamicFieldType.MONEY}:
            numeric_value = float(value)
            if not -1_000_000_000_000 <= numeric_value <= 1_000_000_000_000:
                raise ValueError("Number is outside the supported range")
            return numeric_value
        value = str(value)

    if not isinstance(value, str):
        raise ValueError("Dynamic field values must be text, number, boolean, or blank")

    stripped = value.strip()
    if not stripped:
        return None

    if field_type == DynamicFieldType.LONG_TEXT:
        if len(stripped) > 1000:
            raise ValueError("Long text fields are limited to 1000 characters")
        return stripped

    if field_type == DynamicFieldType.SHORT_TEXT:
        if len(stripped) > 160:
            raise ValueError("Text fields are limited to 160 characters")
        return stripped

    if field_type == DynamicFieldType.DATE:
        try:
            date.fromisoformat(stripped)
        except ValueError as exc:
            raise ValueError("Date fields must use YYYY-MM-DD") from exc
        return stripped

    if field_type in {DynamicFieldType.NUMBER, DynamicFieldType.MONEY}:
        try:
            numeric_value = float(stripped)
        except ValueError as exc:
            raise ValueError("Number fields must contain a valid number") from exc
        if not -1_000_000_000_000 <= numeric_value <= 1_000_000_000_000:
            raise ValueError("Number is outside the supported range")
        return numeric_value

    if field_type == DynamicFieldType.PHONE:
        if len(stripped) > 40:
            raise ValueError("Phone fields are limited to 40 characters")
        return stripped

    if field_type == DynamicFieldType.EMAIL:
        if len(stripped) > 254 or "@" not in stripped or any(character.isspace() for character in stripped):
            raise ValueError("Email fields must contain a valid email address")
        return stripped

    if field_type == DynamicFieldType.URL:
        if len(stripped) > 500 or not stripped.lower().startswith(("http://", "https://")):
            raise ValueError("URL fields must start with http:// or https://")
        return stripped

    if field_type == DynamicFieldType.BOOLEAN:
        normalized = stripped.casefold()
        if normalized in {"true", "yes", "1", "on"}:
            return True
        if normalized in {"false", "no", "0", "off"}:
            return False
        raise ValueError("Boolean fields must be true or false")

    if field_type == DynamicFieldType.SELECT:
        options = select_options or []
        if not options:
            raise ValueError("Select fields require options")
        if stripped not in options:
            raise ValueError("Select value must match one of the configured options")
        return stripped

    raise ValueError("Unsupported field type")


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
    dynamic_fields: list[DynamicRecordFieldResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class LinkCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: LinkedEntityType
    target_id: str = Field(..., min_length=1, max_length=120)
    relationship_type: RelationshipType = RelationshipType.RELATED
    label: str | None = Field(default=None, max_length=40)

    @field_validator("target_id", mode="before")
    @classmethod
    def normalize_target_id(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("label", mode="before")
    @classmethod
    def normalize_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str | None) -> str | None:
        if value is not None and any(character in value for character in "\r\n\t"):
            raise ValueError("Link label can only be a short single-line label")
        return value


class RelationshipCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_item_type: LinkedEntityType
    source_item_id: str = Field(..., min_length=1, max_length=240)
    target_item_type: LinkedEntityType
    target_item_id: str = Field(..., min_length=1, max_length=240)
    relationship_type: RelationshipType = RelationshipType.RELATED
    custom_label: str | None = Field(default=None, max_length=40)

    @field_validator("source_item_id", "target_item_id", mode="before")
    @classmethod
    def normalize_item_id(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("custom_label", mode="before")
    @classmethod
    def normalize_custom_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("custom_label")
    @classmethod
    def validate_custom_label(cls, value: str | None) -> str | None:
        if value is not None and any(character in value for character in "\r\n\t"):
            raise ValueError("Relationship label can only be a short single-line label")
        return value


class RelationshipUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationship_type: RelationshipType | None = None
    custom_label: str | None = Field(default=None, max_length=40)

    @field_validator("custom_label", mode="before")
    @classmethod
    def normalize_custom_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("custom_label")
    @classmethod
    def validate_custom_label(cls, value: str | None) -> str | None:
        if value is not None and any(character in value for character in "\r\n\t"):
            raise ValueError("Relationship label can only be a short single-line label")
        return value


class LinkedEntitySummary(BaseModel):
    entity_type: LinkedEntityType
    id: str
    title: str
    subtitle: str | None = None
    record_type: RecordType | None = None
    reminder_type: ReminderType | None = None
    status: str | None = None
    due_date: date | None = None
    item_date: date | None = Field(default=None, alias="date")
    document_record_id: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None


class LinkedItemResponse(BaseModel):
    link_id: str
    relationship_type: RelationshipType
    label: str | None = None
    direction: LinkDirection
    linked_entity: LinkedEntitySummary
    created_at: datetime


class LinkedItemsResponse(BaseModel):
    records: list[LinkedItemResponse] = Field(default_factory=list)
    reminders: list[LinkedItemResponse] = Field(default_factory=list)
    documents: list[LinkedItemResponse] = Field(default_factory=list)


class RelationshipResponse(BaseModel):
    relationship_id: str
    relationship_type: RelationshipType
    custom_label: str | None = None
    source_item: LinkedEntitySummary
    target_item: LinkedEntitySummary
    created_at: datetime
    updated_at: datetime


class RelationshipCandidate(BaseModel):
    item_type: LinkedEntityType
    item_id: str
    title: str
    subtitle: str | None = None
    status: str | None = None
    item_date: date | None = Field(default=None, alias="date")
    record_type: RecordType | None = None
    reminder_type: ReminderType | None = None
    document_record_id: str | None = None
    disabled_reason: str | None = None


class RelationshipCandidatesResponse(BaseModel):
    items: list[RelationshipCandidate] = Field(default_factory=list)


class RecordAttachmentUploadIntentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=120)
    size_bytes: int = Field(..., ge=1)

    @field_validator("filename", "content_type", mode="before")
    @classmethod
    def normalize_attachment_text(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class PresignedPostResponse(BaseModel):
    url: str
    fields: dict[str, str]


class RecordAttachmentUploadIntentResponse(BaseModel):
    attachment_id: str
    upload: PresignedPostResponse
    expires_at: datetime
    max_size_bytes: int


class RecordAttachmentResponse(BaseModel):
    attachment_id: str
    record_id: str
    display_name: str
    content_type: str
    size_bytes: int
    status: AttachmentStatus
    scan_result: AttachmentScanResult | None = None
    created_at: datetime
    uploaded_at: datetime | None = None
    scan_completed_at: datetime | None = None
    available_at: datetime | None = None
    deleted_at: datetime | None = None


class RecordAttachmentDownloadUrlResponse(BaseModel):
    url: str
    expires_at: datetime


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


class SearchSort(str, Enum):
    RELEVANCE = "relevance"
    UPDATED_DESC = "updated_desc"
    CREATED_DESC = "created_desc"
    RELEVANT_DATE_ASC = "relevant_date_asc"
    RELEVANT_DATE_DESC = "relevant_date_desc"
    TITLE_ASC = "title_asc"


class SearchResultItem(BaseModel):
    source_item_id: str
    source_item_type: LinkedEntityType
    title: str
    subtitle: str | None = None
    status: str | None = None
    category: str | None = None
    relevant_date: date | None = None
    archived: bool = False
    match_context: list[str] = Field(default_factory=list)
    linked_context: list[str] = Field(default_factory=list)
    navigation_metadata: dict[str, str] = Field(default_factory=dict)
    updated_at: datetime


class SearchResponse(BaseModel):
    items: list[SearchResultItem] = Field(default_factory=list)
    next_cursor: str | None = None
    applied_filters: dict[str, object] = Field(default_factory=dict)
    result_count: int


class SavedSearchViewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=80)
    query: str = Field(default="", max_length=120)
    filters: dict[str, object] = Field(default_factory=dict)
    sort: SearchSort = SearchSort.RELEVANCE
    icon: str | None = Field(default=None, max_length=40)
    is_pinned: bool = False

    @field_validator("name", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class SavedSearchViewUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=80)
    query: str | None = Field(default=None, max_length=120)
    filters: dict[str, object] | None = None
    sort: SearchSort | None = None
    icon: str | None = Field(default=None, max_length=40)
    is_pinned: bool | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class SavedSearchViewResponse(BaseModel):
    saved_view_id: str
    name: str
    query: str
    filters: dict[str, object] = Field(default_factory=dict)
    sort: SearchSort
    icon: str | None = None
    is_pinned: bool = False
    created_at: datetime
    updated_at: datetime

