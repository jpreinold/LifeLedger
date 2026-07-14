from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas import (
    AttachmentScanResult,
    AttachmentStatus,
    BirthdayDetails,
    CalendarSyncStatus,
    DynamicFieldType,
    GoogleCalendarConnectionStatus,
    LinkedEntityType,
    MaintenanceDetails,
    PriorityOption,
    RelationshipType,
    ReminderCategory,
    ReminderLeadUnit,
    ReminderLifecycleEvent,
    RecordStatus,
    RecordType,
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
    snoozed_until: datetime | None = None
    archived_at: datetime | None = None
    lifecycle_events: list[ReminderLifecycleEvent] = Field(default_factory=list)
    calendar_sync_enabled: bool = False
    calendar_provider: str | None = None
    calendar_id: str | None = None
    calendar_event_id: str | None = None
    calendar_last_synced_at: datetime | None = None
    calendar_sync_status: CalendarSyncStatus = CalendarSyncStatus.NOT_SYNCED
    calendar_sync_error: str | None = None
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


class DynamicRecordField(BaseModel):
    field_id: str
    key: str
    label: str
    field_type: DynamicFieldType
    value: str | float | bool | None = None
    is_sensitive: bool = False
    has_value: bool = False
    display_order: int = 0
    select_options: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class Record(BaseModel):
    id: str
    user_id: str = "local-dev-user"
    record_type: RecordType
    title: str
    subtitle: str | None = None
    category: str = "General"
    owner_name: str | None = None
    provider_or_brand: str | None = None
    start_date: date | None = None
    issue_date: date | None = None
    expiration_date: date | None = None
    purchase_date: date | None = None
    renewal_date: date | None = None
    location_hint: str | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    status: RecordStatus = RecordStatus.ACTIVE
    dynamic_fields: list[DynamicRecordField] = Field(default_factory=list)
    protected_ciphertext: str | None = None
    protected_encrypted_data_key: str | None = None
    protected_nonce: str | None = None
    protected_encryption_version: int | None = None
    protected_key_arn: str | None = None
    protected_updated_at: datetime | None = None
    protected_field_names: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class LinkedItem(BaseModel):
    user_id: str
    link_id: str
    source_type: LinkedEntityType
    source_id: str
    target_type: LinkedEntityType
    target_id: str
    relationship_type: RelationshipType = RelationshipType.RELATED
    label: str | None = None
    source_link_key: str
    target_link_key: str
    created_at: datetime
    updated_at: datetime
    created_by: str = "user"


class RecordAttachment(BaseModel):
    attachment_id: str
    user_id: str
    owner_hash: str
    record_id: str
    record_attachment_key: str
    display_name: str
    content_type: str
    size_bytes: int
    status: AttachmentStatus
    scan_result: AttachmentScanResult | None = None
    quarantine_object_key: str | None = None
    clean_object_key: str | None = None
    upload_expires_at: datetime | None = None
    created_at: datetime
    uploaded_at: datetime | None = None
    scan_completed_at: datetime | None = None
    available_at: datetime | None = None
    deleted_at: datetime | None = None
    etag: str | None = None
    encryption_key_arn: str | None = None


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


class GoogleCalendarConnection(BaseModel):
    user_id: str
    provider: str = "google_calendar"
    google_account_email: str | None = None
    calendar_id: str = "primary"
    calendar_label: str | None = None
    access_token: str = ""
    refresh_token: str = ""
    token_expires_at: datetime
    scopes: str
    connected_at: datetime
    updated_at: datetime
    disconnected_at: datetime | None = None
    status: GoogleCalendarConnectionStatus = GoogleCalendarConnectionStatus.CONNECTED
    last_error: str | None = None
    token_ciphertext: str | None = None
    token_encrypted_data_key: str | None = None
    token_nonce: str | None = None
    token_encryption_version: int | None = None
    token_key_arn: str | None = None
    token_updated_at: datetime | None = None


class GoogleOAuthState(BaseModel):
    state: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    consumed_at: datetime | None = None
