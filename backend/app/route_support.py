import hashlib
import logging
import time
from datetime import date, datetime, timedelta, timezone
from secrets import token_urlsafe
from uuid import NAMESPACE_URL, uuid4, uuid5

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.alerts import (
    clear_alert_action_state,
    dismiss_alert_state,
    get_alert_eligibility,
    normalize_alert_datetime,
    snooze_alert_state,
    sort_alerts,
)
from app.attachments import (
    ATTACHMENT_NOT_AVAILABLE,
    DOWNLOAD_URL_EXPIRATION_SECONDS,
    DocumentStorageConfigurationError,
    DocumentStorageOperationError,
    UPLOAD_INTENT_EXPIRATION_SECONDS,
    AttachmentValidationError,
    active_attachment_count,
    attachment_content_disposition,
    complete_attachment_upload,
    create_document_storage_service,
    new_record_attachment,
    reconcile_attachment_scan_status,
    sort_attachments,
)
from app.attachments_repository import RecordAttachmentRepository
from app.auth import UserContext, get_current_user
from app.account_models import AccountState
from app.account_runtime import get_account_operations_repository, get_reconciliation_service
from app.birthdays import (
    enrich_birthday_details,
    get_birthday_age_label,
    get_birthday_computed_label,
    get_next_birthday_due_date,
)
from app.config import Settings, get_settings
from app.encryption_service import (
    EncryptedPayload,
    EncryptionConfigurationError,
    EncryptionOperationError,
    EncryptionService,
    record_encryption_context,
)
from app.google_calendar_repository import GoogleCalendarConnectionRepository, GoogleOAuthStateRepository
from app.google_calendar_service import (
    GoogleCalendarAuthError,
    GoogleCalendarConfigurationError,
    GoogleCalendarError,
    GoogleCalendarOption,
    GoogleCalendarNotFoundError,
    GoogleCalendarService,
    WRITABLE_CALENDAR_ACCESS_ROLES,
    build_google_calendar_event,
)
from app.linked_items_repository import LinkedItemRepository
from app.search_repository import SavedSearchViewRepository, SearchIndexRepository
from app.maintenance import (
    advance_maintenance_details,
    get_maintenance_computed_label,
    get_maintenance_due_date,
    get_maintenance_status_label,
    prepare_maintenance_details,
)
from app.models import DynamicRecordField, GoogleCalendarConnection, GoogleOAuthState, LinkedItem, PushSubscription, Record, RecordAttachment, Reminder, ResponsibilityEvent
from app.preferences import default_digest_preferences
from app.preferences_repository import PreferencesRepository
from app.push_repository import PushSubscriptionRepository, push_subscription_id_for_endpoint
from app.recurrence import advance_due_date, calculate_status, get_effective_attention_date, get_next_due_date
from app.renewals import (
    advance_renewal_details,
    get_renewal_computed_label,
    get_renewal_due_date,
    get_renewal_status_label,
    get_renewal_window_label,
)
from app.repository import ReminderRepository
from app.repository_factory import (
    create_google_calendar_connection_repository,
    create_google_oauth_state_repository,
    create_encryption_service,
    create_linked_item_repository,
    create_preferences_repository,
    create_push_subscription_repository,
    create_record_attachment_repository,
    create_record_repository,
    create_repository,
    create_responsibility_history_repository,
    create_saved_search_view_repository,
    create_search_index_repository,
)
from app.records_repository import RecordRepository
from app.responsibility_history_repository import (
    LifecycleWriteConflict,
    LocalResponsibilityHistoryRepository,
    ResponsibilityHistoryRepository,
    decode_cursor,
    encode_cursor,
)
from app.responsibility_lifecycle_service import ResponsibilityLifecycleService, current_occurrence_id
from app.relationship_service import (
    ItemResolver,
    assert_supported_record_link,
    create_record_link,
    create_relationship,
    delete_relationship,
    document_item_id,
    get_entity_neighborhood,
    read_relationship,
    require_link_for_entity,
    update_relationship,
)
from app.schemas import (
    AlertSnoozeRequest,
    AttachmentScanResult,
    AttachmentStatus,
    CalendarSyncStatus,
    DigestPreferences,
    DigestPreferencesUpdate,
    DynamicFieldType,
    DynamicRecordFieldCreate,
    DynamicRecordFieldRevealResponse,
    DynamicRecordFieldUpdate,
    GoogleCalendarCallbackRequest,
    GoogleCalendarConnectResponse,
    GoogleCalendarConnectionStatus,
    GoogleCalendarOptionResponse,
    GoogleCalendarSelectRequest,
    GoogleCalendarStatusResponse,
    LinkCreateRequest,
    LinkedEntityType,
    LinkedItemResponse,
    LinkedItemsResponse,
    RelationshipCandidatesResponse,
    RelationshipCreateRequest,
    RelationshipResponse,
    RelationshipUpdateRequest,
    MaintenanceDetails,
    PushConfigurationResponse,
    PushStatusResponse,
    PushSubscriptionCreate,
    PushSubscriptionResponse,
    PushTestResponse,
    SavedSearchViewCreate,
    SavedSearchViewResponse,
    SavedSearchViewUpdate,
    SearchResponse,
    SearchSort,
    ProtectedRecordPayload,
    ProtectedRecordStatusResponse,
    ReminderCreate,
    ReminderCompleteRequest,
    ReminderAlertResponse,
    ReminderLeadUnit,
    ReminderLinkedRecordSummary,
    ReminderRenewRequest,
    ReminderSnoozeRequest,
    RecordAttachmentDownloadUrlResponse,
    RecordAttachmentResponse,
    RecordAttachmentUploadIntentRequest,
    RecordAttachmentUploadIntentResponse,
    RecordCreate,
    RecordResponse,
    RecordStatus,
    RecordType,
    RecordUpdate,
    ReminderResponse,
    ReminderType,
    ReminderUpdate,
    ResponsibilityEvidenceRequest,
    ResponsibilityEventResponse,
    ResponsibilityHistoryPage,
    ResponsibilityDocumentEvidence,
    LifecycleReconciliationPage,
    LifecycleReconciliationResult,
    LifecycleReconciliationStatus,
    RenewalDetails,
    RepeatOption,
    normalize_dynamic_field_value,
)
from app.search_service import (
    SavedSearchViewService,
    SearchProjectionService,
    SearchQueryService,
    SearchValidationError,
    to_saved_view_response,
    validate_search_request,
)
from app.security_audit import log_security_event, user_hash

from app.push_sender import (
    InvalidPushSubscriptionError,
    PushConfigurationError,
    PushPayload,
    PushSendError,
    PushSender,
    PyWebPushSender,
)

settings = get_settings()

logger = logging.getLogger(__name__)

PUSH_CONFIG_MISSING_DETAIL = "Push notifications are not configured for this environment."
NO_ACTIVE_PUSH_SUBSCRIPTION_DETAIL = "No active push subscription found. Enable push notifications first."
TEST_PUSH_PAYLOAD = PushPayload(
    title="LifeLedger Test",
    body="Push notifications are working.",
    url="/?openDigest=1",
    tag="test-push",
    type="test_push",
)
PROTECTED_RECORD_FIELDS_BY_TYPE: dict[RecordType, set[str]] = {
    RecordType.GENERAL: {"sensitive_notes"},
    RecordType.PASSPORT: {"document_number"},
    RecordType.DRIVER_LICENSE: {"license_number"},
    RecordType.VEHICLE: {"vin"},
    RecordType.INSURANCE: {"policy_number", "member_number"},
    RecordType.APPLIANCE: {"serial_number"},
    RecordType.PET: set(),
    RecordType.HOME: set(),
    RecordType.SUBSCRIPTION: {"account_reference"},
    RecordType.WARRANTY: {"serial_number"},
}

repository = create_repository()
record_repository = create_record_repository()
preferences_repository = create_preferences_repository()
push_subscription_repository = create_push_subscription_repository()
google_calendar_connection_repository = create_google_calendar_connection_repository()
google_oauth_state_repository = create_google_oauth_state_repository()
record_attachment_repository = create_record_attachment_repository()
linked_item_repository = create_linked_item_repository()
search_index_repository = create_search_index_repository()
saved_search_view_repository = create_saved_search_view_repository()
responsibility_history_repository = create_responsibility_history_repository()

def get_app_settings() -> Settings:
    return get_settings()

def get_repository() -> ReminderRepository:
    return repository

def get_responsibility_history_repository(
    repo: ReminderRepository = Depends(get_repository),
) -> ResponsibilityHistoryRepository:
    if hasattr(repo, "file_path"):
        reminder_path = getattr(repo, "file_path")
        return LocalResponsibilityHistoryRepository(reminder_path.with_name("responsibility-history.json"))
    return responsibility_history_repository

def get_record_repository() -> RecordRepository:
    return record_repository

def get_record_attachment_repository() -> RecordAttachmentRepository:
    return record_attachment_repository

def get_linked_item_repository() -> LinkedItemRepository:
    return linked_item_repository

def get_search_index_repository() -> SearchIndexRepository:
    return search_index_repository

def get_saved_search_view_repository() -> SavedSearchViewRepository:
    return saved_search_view_repository

def get_preferences_repository() -> PreferencesRepository:
    return preferences_repository

def get_push_subscription_repository() -> PushSubscriptionRepository:
    return push_subscription_repository

def get_google_calendar_connection_repository() -> GoogleCalendarConnectionRepository:
    return google_calendar_connection_repository

def get_google_oauth_state_repository() -> GoogleOAuthStateRepository:
    return google_oauth_state_repository

def get_search_projection_service(
    search_repo: SearchIndexRepository = Depends(get_search_index_repository),
    record_repo: RecordRepository = Depends(get_record_repository),
    reminder_repo: ReminderRepository = Depends(get_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
) -> SearchProjectionService:
    return SearchProjectionService(
        search_repo,
        record_repo,
        reminder_repo,
        attachment_repo,
        linked_repo,
        get_reconciliation_service(),
    )

def get_responsibility_lifecycle_service(
    reminder_repo: ReminderRepository = Depends(get_repository),
    history_repo: ResponsibilityHistoryRepository = Depends(get_responsibility_history_repository),
    record_repo: RecordRepository = Depends(get_record_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> ResponsibilityLifecycleService:
    return ResponsibilityLifecycleService(
        reminder_repo,
        history_repo,
        record_repo,
        linked_repo,
        attachment_repo,
        search_service,
    )

def get_search_query_service(
    search_repo: SearchIndexRepository = Depends(get_search_index_repository),
) -> SearchQueryService:
    return SearchQueryService(search_repo)

def get_saved_search_view_service(
    saved_repo: SavedSearchViewRepository = Depends(get_saved_search_view_repository),
) -> SavedSearchViewService:
    return SavedSearchViewService(saved_repo)
def get_google_calendar_service(app_settings: Settings = Depends(get_app_settings)) -> GoogleCalendarService:
    return GoogleCalendarService(app_settings)

def get_push_sender(app_settings: Settings = Depends(get_app_settings)) -> PushSender:
    return PyWebPushSender(app_settings)

def get_encryption_service(app_settings: Settings = Depends(get_app_settings)) -> EncryptionService:
    return create_encryption_service(app_settings)

def get_document_storage_service(app_settings: Settings = Depends(get_app_settings)):
    return create_document_storage_service(app_settings)

def is_renewable_reminder(reminder: Reminder) -> bool:
    return reminder.reminder_type in {ReminderType.RENEWAL, ReminderType.MAINTENANCE} or reminder.repeat != RepeatOption.NONE

def to_google_calendar_status_response(
    settings: Settings,
    connection: GoogleCalendarConnection | None,
) -> GoogleCalendarStatusResponse:
    if not settings.google_calendar_configured:
        return GoogleCalendarStatusResponse(
            configured=False,
            connected=False,
            status=GoogleCalendarConnectionStatus.DISCONNECTED,
            calendar_id=None,
            calendar_label=None,
        )

    if connection is None:
        return GoogleCalendarStatusResponse(
            configured=True,
            connected=False,
            status=GoogleCalendarConnectionStatus.DISCONNECTED,
            calendar_id=None,
            calendar_label=None,
        )

    connected = connection.status == GoogleCalendarConnectionStatus.CONNECTED
    calendar_id = connection.calendar_id if connected else None
    return GoogleCalendarStatusResponse(
        configured=True,
        connected=connected,
        status=connection.status,
        google_account_email=connection.google_account_email,
        calendar_id=calendar_id,
        calendar_label=selected_calendar_label(connection) if connected else None,
        last_error=connection.last_error,
    )

def selected_calendar_label(connection: GoogleCalendarConnection | None) -> str | None:
    if connection is None:
        return None
    if connection.calendar_label:
        return connection.calendar_label
    return "Primary calendar" if connection.calendar_id == "primary" else connection.calendar_id

def to_google_calendar_option_response(
    option: GoogleCalendarOption,
    selected_calendar_id: str,
) -> GoogleCalendarOptionResponse:
    return GoogleCalendarOptionResponse(
        id=option.id,
        label=option.label,
        primary=option.primary,
        access_role=option.access_role,
        selected=option.id == selected_calendar_id,
    )

def list_google_calendar_options_or_raise(
    repo: GoogleCalendarConnectionRepository,
    calendar_service: GoogleCalendarService,
    connection: GoogleCalendarConnection,
    now: datetime,
) -> list[GoogleCalendarOption]:
    try:
        return calendar_service.list_calendar_options(connection)
    except GoogleCalendarAuthError as exc:
        mark_google_connection_needs_reconnect(
            repo,
            connection,
            now,
            "Reconnect Google Calendar to choose calendars.",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reconnect Google Calendar to choose calendars.",
        ) from exc
    except GoogleCalendarConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.safe_message) from exc
    except GoogleCalendarError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.safe_message) from exc

def with_google_calendar_id(connection: GoogleCalendarConnection, calendar_id: str | None) -> GoogleCalendarConnection:
    if not calendar_id or calendar_id == connection.calendar_id:
        return connection
    return connection.model_copy(update={"calendar_id": calendar_id})

def get_google_oauth_invalid_state_reason(
    saved_state: GoogleOAuthState | None,
    current_user_id: str,
    now: datetime,
) -> str | None:
    if saved_state is None:
        return "missing_state"
    if saved_state.user_id != current_user_id:
        return "wrong_user"
    if saved_state.consumed_at is not None:
        return "already_consumed"
    if saved_state.expires_at <= now:
        return "expired"
    return None

def log_invalid_google_oauth_state(reason: str, state: str) -> None:
    logger.warning(
        "Google Calendar OAuth state rejected: %s state_hash=%s",
        reason,
        google_oauth_state_log_id(state),
    )

def google_oauth_state_log_id(state: str) -> str:
    return hashlib.sha256(state.encode("utf-8")).hexdigest()[:12]

def require_ready_google_connection(
    repo: GoogleCalendarConnectionRepository,
    user_id: str,
    settings: Settings,
    calendar_service: GoogleCalendarService,
    now: datetime,
) -> GoogleCalendarConnection:
    if not settings.google_calendar_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Calendar sync is not configured for this environment.",
        )

    connection = repo.get_connection(user_id)
    if connection is None or connection.status == GoogleCalendarConnectionStatus.DISCONNECTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Connect Google Calendar in Settings to sync reminders.",
        )
    if connection.status == GoogleCalendarConnectionStatus.NEEDS_RECONNECT or not connection.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reconnect Google Calendar in Settings to continue syncing.",
        )

    return ensure_google_connection_access_token(repo, connection, calendar_service, now)

def ensure_google_connection_access_token(
    repo: GoogleCalendarConnectionRepository,
    connection: GoogleCalendarConnection,
    calendar_service: GoogleCalendarService,
    now: datetime,
) -> GoogleCalendarConnection:
    expires_at = connection.token_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at > now + timedelta(minutes=2) and connection.access_token:
        return connection

    try:
        token_set = calendar_service.refresh_access_token(connection)
    except GoogleCalendarAuthError as exc:
        mark_google_connection_needs_reconnect(repo, connection, now, exc.safe_message)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.safe_message) from exc
    except GoogleCalendarConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.safe_message) from exc
    except GoogleCalendarError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.safe_message) from exc

    updated = connection.model_copy(
        update={
            "access_token": token_set.access_token,
            "refresh_token": token_set.refresh_token or connection.refresh_token,
            "token_expires_at": token_set.token_expires_at,
            "scopes": token_set.scopes,
            "updated_at": now,
            "status": GoogleCalendarConnectionStatus.CONNECTED,
            "last_error": None,
        }
    )
    return repo.save_connection(updated)

def mark_google_connection_needs_reconnect(
    repo: GoogleCalendarConnectionRepository,
    connection: GoogleCalendarConnection,
    now: datetime,
    safe_message: str,
) -> GoogleCalendarConnection:
    updated = connection.model_copy(
        update={
            "status": GoogleCalendarConnectionStatus.NEEDS_RECONNECT,
            "updated_at": now,
            "last_error": safe_message,
        }
    )
    return repo.save_connection(updated)

def sync_existing_calendar_event_after_change(
    reminder_repo: ReminderRepository,
    connection_repo: GoogleCalendarConnectionRepository,
    settings: Settings,
    calendar_service: GoogleCalendarService,
    reminder: Reminder,
    now: datetime,
) -> Reminder:
    if (
        not reminder.calendar_sync_enabled
        or reminder.calendar_provider != "google_calendar"
        or not reminder.calendar_event_id
    ):
        return reminder

    if not settings.google_calendar_configured:
        return save_calendar_sync_error(
            reminder_repo,
            reminder,
            now,
            "Calendar sync is not configured for this environment.",
            CalendarSyncStatus.NEEDS_ATTENTION,
        )

    connection = connection_repo.get_connection(reminder.user_id)
    if connection is None or connection.status != GoogleCalendarConnectionStatus.CONNECTED:
        return save_calendar_sync_error(
            reminder_repo,
            reminder,
            now,
            "Connect Google Calendar in Settings to continue syncing.",
            CalendarSyncStatus.NEEDS_ATTENTION,
        )

    try:
        ready_connection = ensure_google_connection_access_token(connection_repo, connection, calendar_service, now)
        target_connection = with_google_calendar_id(ready_connection, reminder.calendar_id)
        calendar_service.update_event(
            target_connection,
            reminder.calendar_event_id,
            build_google_calendar_event(reminder, get_computed_label(reminder)),
        )
    except HTTPException as exc:
        return save_calendar_sync_error(
            reminder_repo,
            reminder,
            now,
            str(exc.detail),
            CalendarSyncStatus.NEEDS_ATTENTION,
        )
    except GoogleCalendarNotFoundError as exc:
        return save_calendar_sync_error(
            reminder_repo,
            reminder,
            now,
            exc.safe_message,
            CalendarSyncStatus.NEEDS_ATTENTION,
        )
    except GoogleCalendarAuthError as exc:
        mark_google_connection_needs_reconnect(connection_repo, connection, now, exc.safe_message)
        return save_calendar_sync_error(
            reminder_repo,
            reminder,
            now,
            exc.safe_message,
            CalendarSyncStatus.NEEDS_ATTENTION,
        )
    except GoogleCalendarError as exc:
        return save_calendar_sync_error(
            reminder_repo,
            reminder,
            now,
            exc.safe_message,
            CalendarSyncStatus.ERROR,
        )

    synced = reminder.model_copy(
        update={
            "calendar_sync_enabled": True,
            "calendar_provider": "google_calendar",
            "calendar_id": target_connection.calendar_id,
            "calendar_last_synced_at": now,
            "calendar_sync_status": CalendarSyncStatus.SYNCED,
            "calendar_sync_error": None,
            "updated_at": now,
        }
    )
    return reminder_repo.update_reminder(synced)

def cleanup_calendar_event_before_delete(
    reminder_repo: ReminderRepository,
    connection_repo: GoogleCalendarConnectionRepository,
    settings: Settings,
    calendar_service: GoogleCalendarService,
    reminder: Reminder,
    now: datetime,
) -> None:
    if not reminder.calendar_sync_enabled or not reminder.calendar_event_id:
        return

    try:
        connection = require_ready_google_connection(connection_repo, reminder.user_id, settings, calendar_service, now)
        target_connection = with_google_calendar_id(connection, reminder.calendar_id)
        calendar_service.delete_event(target_connection, reminder.calendar_event_id)
    except GoogleCalendarNotFoundError:
        return
    except HTTPException as exc:
        save_calendar_sync_error(
            reminder_repo,
            reminder,
            now,
            str(exc.detail),
            CalendarSyncStatus.NEEDS_ATTENTION,
        )
        raise
    except GoogleCalendarAuthError as exc:
        save_calendar_sync_error(reminder_repo, reminder, now, exc.safe_message, CalendarSyncStatus.NEEDS_ATTENTION)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.safe_message) from exc
    except GoogleCalendarError as exc:
        save_calendar_sync_error(reminder_repo, reminder, now, exc.safe_message, CalendarSyncStatus.ERROR)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.safe_message) from exc

def clear_calendar_sync_metadata(reminder: Reminder, now: datetime) -> Reminder:
    return reminder.model_copy(
        update={
            "calendar_sync_enabled": False,
            "calendar_provider": None,
            "calendar_id": None,
            "calendar_event_id": None,
            "calendar_last_synced_at": None,
            "calendar_sync_status": CalendarSyncStatus.NOT_SYNCED,
            "calendar_sync_error": None,
            "updated_at": now,
        }
    )

def save_calendar_sync_error(
    repo: ReminderRepository,
    reminder: Reminder,
    now: datetime,
    safe_message: str,
    sync_status: CalendarSyncStatus,
) -> Reminder:
    updated = reminder.model_copy(
        update={
            "calendar_sync_status": sync_status,
            "calendar_sync_error": safe_message,
            "updated_at": now,
        }
    )
    return repo.update_reminder(updated)

def mark_user_google_reminders_needs_attention(repo: ReminderRepository, user_id: str, now: datetime) -> None:
    for reminder in repo.list_reminders(user_id):
        if reminder.calendar_provider == "google_calendar" or reminder.calendar_sync_enabled:
            repo.update_reminder(
                reminder.model_copy(
                    update={
                        "calendar_sync_status": CalendarSyncStatus.NEEDS_ATTENTION,
                        "calendar_sync_error": "Google Calendar disconnected.",
                        "updated_at": now,
                    }
                )
            )

def require_reminder(repo: ReminderRepository, user_id: str, reminder_id: str) -> Reminder:
    reminder = repo.get_reminder(user_id, reminder_id)
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")

    return reminder

def require_record(repo: RecordRepository, user_id: str, record_id: str) -> Record:
    record = repo.get_record(user_id, record_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    return record

def require_attachment(
    repo: RecordAttachmentRepository,
    user_id: str,
    record_id: str,
    attachment_id: str,
) -> RecordAttachment:
    attachment = repo.get_attachment(user_id, record_id, attachment_id)
    if attachment is None:
        raise attachment_http_exception(status.HTTP_404_NOT_FOUND, "Attachment not found")

    return attachment

def require_document_storage_configured(document_storage) -> None:
    if not getattr(document_storage, "configured", False):
        raise attachment_http_exception(status.HTTP_503_SERVICE_UNAVAILABLE, DocumentStorageConfigurationError.safe_message)

def maybe_reconcile_attachment(
    attachment: RecordAttachment,
    repo: RecordAttachmentRepository,
    document_storage,
    settings: Settings,
) -> RecordAttachment:
    if not getattr(document_storage, "configured", False):
        return attachment
    try:
        return reconcile_attachment_scan_status(
            attachment=attachment,
            repo=repo,
            storage=document_storage,
            settings=settings,
            now=utc_now(),
        )
    except (DocumentStorageConfigurationError, DocumentStorageOperationError):
        return attachment

def reject_failed_upload(
    attachment: RecordAttachment,
    repo: RecordAttachmentRepository,
    document_storage,
) -> None:
    if attachment.quarantine_object_key and getattr(document_storage, "configured", False):
        try:
            document_storage.delete_quarantine_object(attachment.quarantine_object_key)
        except DocumentStorageOperationError:
            log_security_event(
                "attachment_cleanup_failed",
                user_id=attachment.user_id,
                record_id=attachment.record_id,
                attachment_id=attachment.attachment_id,
                content_type=attachment.content_type,
                size=attachment.size_bytes,
                result="quarantine_delete_failed",
            )

    repo.update_attachment(
        attachment.model_copy(
            update={
                "status": AttachmentStatus.REJECTED,
                "scan_result": AttachmentScanResult.FAILED,
                "quarantine_object_key": None,
                "clean_object_key": None,
            }
        )
    )

def cleanup_record_attachments_before_delete(
    user_id: str,
    record_id: str,
    repo: RecordAttachmentRepository,
    document_storage,
    linked_repo: LinkedItemRepository | None = None,
) -> None:
    for attachment in repo.list_for_record(user_id, record_id):
        cleanup_attachment_or_raise(attachment, repo, document_storage)
        if linked_repo is not None:
            linked_repo.delete_links_for_entity(
                user_id,
                LinkedEntityType.DOCUMENT,
                document_item_id(attachment.record_id, attachment.attachment_id),
            )

def cleanup_attachment_or_raise(
    attachment: RecordAttachment,
    repo: RecordAttachmentRepository,
    document_storage,
) -> None:
    try:
        if attachment.quarantine_object_key:
            require_document_storage_configured(document_storage)
            document_storage.delete_quarantine_object(attachment.quarantine_object_key)
        if attachment.clean_object_key:
            require_document_storage_configured(document_storage)
            document_storage.delete_clean_object(attachment.clean_object_key)
        repo.delete_attachment_metadata(attachment.user_id, attachment.record_id, attachment.attachment_id)
    except HTTPException:
        log_attachment_cleanup_failed(attachment, "storage_not_configured")
        raise
    except DocumentStorageOperationError as exc:
        log_attachment_cleanup_failed(attachment, "object_delete_failed")
        raise attachment_http_exception(status.HTTP_503_SERVICE_UNAVAILABLE, exc.safe_message) from exc

def log_attachment_cleanup_failed(attachment: RecordAttachment, result: str) -> None:
    log_security_event(
        "attachment_cleanup_failed",
        user_id=attachment.user_id,
        record_id=attachment.record_id,
        attachment_id=attachment.attachment_id,
        content_type=attachment.content_type,
        size=attachment.size_bytes,
        result=result,
    )

def to_attachment_response(attachment: RecordAttachment) -> RecordAttachmentResponse:
    return RecordAttachmentResponse(
        attachment_id=attachment.attachment_id,
        record_id=attachment.record_id,
        display_name=attachment.display_name,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
        status=attachment.status,
        scan_result=attachment.scan_result,
        created_at=attachment.created_at,
        uploaded_at=attachment.uploaded_at,
        scan_completed_at=attachment.scan_completed_at,
        available_at=attachment.available_at,
        deleted_at=attachment.deleted_at,
    )

def no_store_headers() -> dict[str, str]:
    return {"Cache-Control": "no-store, private", "Pragma": "no-cache"}

def set_attachment_no_store(response: Response) -> None:
    for header, value in no_store_headers().items():
        response.headers[header] = value

def attachment_http_exception(status_code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail, headers=no_store_headers())

DYNAMIC_PROTECTED_VALUES_KEY = "dynamic_fields"

def dynamic_value_has_content(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return len(value.strip()) > 0
    return True

def next_dynamic_field_order(record: Record) -> int:
    if not record.dynamic_fields:
        return 100
    return max(field.display_order for field in record.dynamic_fields) + 10

def sorted_dynamic_fields(fields: list[DynamicRecordField]) -> list[DynamicRecordField]:
    return sorted(fields, key=lambda field: (field.display_order, field.created_at, field.label.casefold()))

def replace_dynamic_field(fields: list[DynamicRecordField], updated: DynamicRecordField) -> list[DynamicRecordField]:
    return [updated if field.field_id == updated.field_id else field for field in fields]

def find_dynamic_field(record: Record, field_id: str) -> DynamicRecordField:
    for field in record.dynamic_fields:
        if field.field_id == field_id:
            return field
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record field not found")

def normalize_dynamic_field_key(label_or_key: str, fallback_id: str) -> str:
    normalized = []
    previous_was_separator = False
    for character in label_or_key.strip().lower():
        if character.isalnum():
            normalized.append(character)
            previous_was_separator = False
        elif not previous_was_separator:
            normalized.append("_")
            previous_was_separator = True

    key = "".join(normalized).strip("_")[:60]
    return key or f"field_{fallback_id[:8]}"

def decrypt_record_private_payload(record: Record, encryption_service: EncryptionService) -> dict:
    if not record_has_protected_data(record):
        return {}

    try:
        return encryption_service.decrypt_json(record_encrypted_payload(record), record_encryption_context(record.user_id, record.id))
    except EncryptionConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.safe_message) from exc
    except EncryptionOperationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.safe_message) from exc

def protected_dynamic_values(payload: dict) -> dict[str, object]:
    values = payload.get(DYNAMIC_PROTECTED_VALUES_KEY, {})
    return values if isinstance(values, dict) else {}

def protected_legacy_values(payload: dict) -> dict[str, object]:
    return {key: value for key, value in payload.items() if key != DYNAMIC_PROTECTED_VALUES_KEY}

def encrypt_record_private_payload(
    record: Record,
    payload: dict,
    protected_field_names: list[str],
    encryption_service: EncryptionService,
    now: datetime,
) -> Record:
    legacy_values = protected_legacy_values(payload)
    dynamic_values = protected_dynamic_values(payload)
    if not legacy_values and not dynamic_values:
        return clear_record_protected_fields(record, now)

    compact_payload = {**legacy_values}
    if dynamic_values:
        compact_payload[DYNAMIC_PROTECTED_VALUES_KEY] = dynamic_values

    try:
        encrypted = encryption_service.encrypt_json(compact_payload, record_encryption_context(record.user_id, record.id))
    except EncryptionConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.safe_message) from exc
    except EncryptionOperationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.safe_message) from exc

    return record.model_copy(
        update={
            "protected_ciphertext": encrypted.ciphertext,
            "protected_encrypted_data_key": encrypted.encrypted_data_key,
            "protected_nonce": encrypted.nonce,
            "protected_encryption_version": encrypted.encryption_version,
            "protected_key_arn": encrypted.key_arn,
            "protected_updated_at": now,
            "protected_field_names": sorted(protected_field_names),
            "updated_at": now,
        }
    )

def set_dynamic_sensitive_value(
    previous_record: Record,
    updated_record: Record,
    field_id: str,
    value,
    encryption_service: EncryptionService,
    now: datetime,
) -> Record:
    payload = decrypt_record_private_payload(previous_record, encryption_service)
    dynamic_values = dict(protected_dynamic_values(payload))
    if dynamic_value_has_content(value):
        dynamic_values[field_id] = value
    else:
        dynamic_values.pop(field_id, None)

    next_payload = {**protected_legacy_values(payload)}
    if dynamic_values:
        next_payload[DYNAMIC_PROTECTED_VALUES_KEY] = dynamic_values
    return encrypt_record_private_payload(updated_record, next_payload, previous_record.protected_field_names, encryption_service, now)

def remove_dynamic_sensitive_value(
    previous_record: Record,
    updated_record: Record,
    field_id: str,
    encryption_service: EncryptionService,
    now: datetime,
) -> Record:
    payload = decrypt_record_private_payload(previous_record, encryption_service)
    dynamic_values = dict(protected_dynamic_values(payload))
    dynamic_values.pop(field_id, None)

    next_payload = {**protected_legacy_values(payload)}
    if dynamic_values:
        next_payload[DYNAMIC_PROTECTED_VALUES_KEY] = dynamic_values
    return encrypt_record_private_payload(updated_record, next_payload, previous_record.protected_field_names, encryption_service, now)

def to_record_response(record: Record) -> RecordResponse:
    return RecordResponse.model_validate(
        {
            **record.model_dump(),
            "has_protected_data": record_has_protected_data(record),
            "protected_field_names": safe_protected_field_names(record),
        }
    )

def to_protected_record_status(record: Record) -> ProtectedRecordStatusResponse:
    return ProtectedRecordStatusResponse(
        has_protected_data=record_has_protected_data(record),
        protected_field_names=safe_protected_field_names(record),
        protected_encryption_version=record.protected_encryption_version if record_has_protected_data(record) else None,
        protected_updated_at=record.protected_updated_at if record_has_protected_data(record) else None,
    )

def record_has_protected_data(record: Record) -> bool:
    return bool(record.protected_ciphertext and record.protected_encrypted_data_key and record.protected_nonce)

def safe_protected_field_names(record: Record) -> list[str]:
    if not record_has_protected_data(record):
        return []
    allowed = protected_fields_for_record(record)
    return sorted(field for field in record.protected_field_names if field in allowed)

def protected_fields_for_record(record: Record) -> set[str]:
    return PROTECTED_RECORD_FIELDS_BY_TYPE.get(record.record_type, set())

def validate_protected_record_fields(record: Record, values: dict[str, str]) -> None:
    allowed = protected_fields_for_record(record)
    unsupported_fields = set(values) - allowed
    if unsupported_fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="One or more protected fields are not supported for this record type.",
        )

def record_encrypted_payload(record: Record) -> EncryptedPayload:
    if not record_has_protected_data(record):
        raise EncryptionOperationError()
    return EncryptedPayload(
        ciphertext=record.protected_ciphertext or "",
        encrypted_data_key=record.protected_encrypted_data_key or "",
        nonce=record.protected_nonce or "",
        encryption_version=record.protected_encryption_version or 0,
        key_arn=record.protected_key_arn,
    )

def clear_record_protected_fields(record: Record, now: datetime) -> Record:
    return record.model_copy(
        update={
            "protected_ciphertext": None,
            "protected_encrypted_data_key": None,
            "protected_nonce": None,
            "protected_encryption_version": None,
            "protected_key_arn": None,
            "protected_updated_at": None,
            "protected_field_names": [],
            "updated_at": now,
        }
    )

def get_reminder_linked_record_summaries(
    user_id: str,
    reminder_id: str,
    linked_repo: LinkedItemRepository,
    record_repo: RecordRepository,
) -> list[ReminderLinkedRecordSummary]:
    summaries: list[ReminderLinkedRecordSummary] = []
    seen_record_ids: set[str] = set()
    links = linked_repo.list_links_for_entity(user_id, LinkedEntityType.REMINDER, reminder_id)

    for link in sorted(links, key=lambda item: item.created_at):
        record_id: str | None = None
        if link.source_type == LinkedEntityType.RECORD and link.target_type == LinkedEntityType.REMINDER and link.target_id == reminder_id:
            record_id = link.source_id
        elif link.target_type == LinkedEntityType.RECORD and link.source_type == LinkedEntityType.REMINDER and link.source_id == reminder_id:
            record_id = link.target_id

        if record_id is None or record_id in seen_record_ids:
            continue

        record = record_repo.get_record(user_id, record_id)
        if record is None:
            continue

        seen_record_ids.add(record.id)
        summaries.append(
            ReminderLinkedRecordSummary(
                id=record.id,
                title=record.title,
                subtitle=record.subtitle or record.provider_or_brand or record.owner_name or record.category,
                record_type=record.record_type,
                status=record.status,
            )
        )

    return summaries

def to_responsibility_event_response(
    event: ResponsibilityEvent,
    attachment_repo: RecordAttachmentRepository,
) -> ResponsibilityEventResponse:
    documents: list[ResponsibilityDocumentEvidence] = []
    for document_id in event.related_document_ids:
        attachment = (
            attachment_repo.get_attachment(event.user_id, event.item_id, document_id)
            if event.item_id
            else None
        )
        if attachment is None or attachment.status in {AttachmentStatus.DELETED, AttachmentStatus.DELETING}:
            documents.append(
                ResponsibilityDocumentEvidence(
                    document_id=document_id,
                    record_id=event.item_id,
                    display_name="Document no longer available",
                    status="unavailable",
                    available=False,
                )
            )
            continue
        is_available = attachment.status == AttachmentStatus.AVAILABLE
        documents.append(
            ResponsibilityDocumentEvidence(
                document_id=document_id,
                record_id=event.item_id,
                display_name=attachment.display_name,
                status=attachment.status.value,
                available=is_available,
            )
        )
    return ResponsibilityEventResponse(
        event_id=event.event_id,
        reminder_id=event.reminder_id,
        item_id=event.item_id,
        occurrence_id=event.occurrence_id,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        effective_date=event.effective_date,
        previous_due_date=event.previous_due_date,
        next_due_date=event.next_due_date,
        completed_at=event.completed_at,
        note=event.note,
        source=event.source,
        schema_version=event.schema_version,
        created_at=event.created_at,
        responsibility_title_snapshot=event.responsibility_title_snapshot,
        item_title_snapshot=event.item_title_snapshot,
        item_type_snapshot=event.item_type_snapshot,
        related_event_id=event.related_event_id,
        reconciliation_status=event.reconciliation_status,
        search_sync_status=event.search_sync_status,
        document_reference_status=event.document_reference_status,
        documents=documents,
    )

def to_response(
    reminder: Reminder,
    *,
    linked_records: list[ReminderLinkedRecordSummary] | None = None,
    lifecycle_reconciliation_status: LifecycleReconciliationStatus | None = None,
    last_lifecycle_event_id: str | None = None,
) -> ReminderResponse:
    now = utc_now()
    return ReminderResponse.model_validate(
        {
            **reminder.model_dump(),
            "status": calculate_status(reminder, now=now),
            "effective_attention_date": get_effective_attention_date(reminder, now=now),
            "linked_records": linked_records or [],
            "current_occurrence_id": current_occurrence_id(reminder),
            "lifecycle_reconciliation_status": lifecycle_reconciliation_status,
            "last_lifecycle_event_id": last_lifecycle_event_id,
            "next_due_date": get_response_next_due_date(reminder),
            "computed_label": get_computed_label(reminder),
            "birthday_age_label": get_birthday_age_label(reminder.birthday_details)
            if reminder.reminder_type == ReminderType.BIRTHDAY
            else None,
            "renewal_status_label": get_renewal_status_label(reminder.renewal_details)
            if reminder.reminder_type == ReminderType.RENEWAL
            else None,
            "renewal_window_label": get_renewal_window_label(reminder.renewal_details)
            if reminder.reminder_type == ReminderType.RENEWAL
            else None,
            "maintenance_status_label": get_maintenance_status_label(reminder.maintenance_details)
            if reminder.reminder_type == ReminderType.MAINTENANCE
            else None,
        }
    )

def to_alert_response(reminder: Reminder, eligibility) -> ReminderAlertResponse:
    return ReminderAlertResponse.model_validate(
        {
            **to_response(reminder).model_dump(),
            "alert_reason": eligibility.reason,
            "alert_reminder_start_date": eligibility.reminder_start_date,
        }
    )

def to_digest_preferences_response(preferences) -> DigestPreferences:
    return DigestPreferences.model_validate(preferences)

def to_push_subscription_response(subscription: PushSubscription) -> PushSubscriptionResponse:
    return PushSubscriptionResponse.model_validate(subscription)

def to_push_status_response(settings: Settings, subscriptions: list[PushSubscription], preferences) -> PushStatusResponse:
    last_success_at = max(
        (subscription.last_success_at for subscription in subscriptions if subscription.last_success_at is not None),
        default=None,
    )
    last_failure_at = max(
        (subscription.last_failure_at for subscription in subscriptions if subscription.last_failure_at is not None),
        default=None,
    )

    return PushStatusResponse(
        configured=settings.push_notifications_configured,
        active_subscription_count=len(subscriptions),
        last_success_at=last_success_at,
        last_failure_at=last_failure_at,
        failure_count=sum(subscription.failure_count for subscription in subscriptions),
        digest_enabled=preferences.digest_enabled,
        digest_time=preferences.digest_time,
        timezone=preferences.timezone,
    )

def sync_linked_search_neighbors_safe(
    service: SearchProjectionService,
    user_id: str,
    links: list[LinkedItem],
    operation: str,
    *,
    excluded_entities: set[tuple[LinkedEntityType, str]] | None = None,
) -> None:
    excluded = excluded_entities or set()
    seen: set[tuple[LinkedEntityType, str]] = set()
    for link in links:
        for entity_type, entity_id in ((link.source_type, link.source_id), (link.target_type, link.target_id)):
            key = (entity_type, entity_id)
            if key in excluded or key in seen:
                continue
            seen.add(key)
            sync_search_entity_safe(service, user_id, entity_type, entity_id, operation)

def sync_search_entity_safe(
    service: SearchProjectionService,
    user_id: str,
    entity_type: LinkedEntityType,
    entity_id: str,
    operation: str,
) -> None:
    try:
        service.sync_entity_and_neighbors_observed(user_id, entity_type, entity_id, operation=operation)
        logger.info(
            "search_projection_sync",
            extra={
                "operation": operation,
                "entity_type": entity_type.value,
                "entity_id": entity_id,
                "authenticated_user_hash": user_hash(user_id),
                "result": "success",
                "retryable": False,
                "projection_sync_status": "synchronized",
            },
        )
    except Exception:
        logger.error(
            "search_projection_sync_failed",
            extra={
                "operation": operation,
                "entity_type": entity_type.value,
                "entity_id": entity_id,
                "authenticated_user_hash": user_hash(user_id),
                "result": "failure",
                "retryable": True,
                "projection_sync_status": "reconciliation_required",
            },
        )

def delete_search_entity_safe(
    service: SearchProjectionService,
    user_id: str,
    entity_type: LinkedEntityType,
    entity_id: str,
    operation: str,
) -> None:
    try:
        service.delete_entity_observed(user_id, entity_type, entity_id, operation=operation)
        logger.info(
            "search_projection_delete",
            extra={
                "operation": operation,
                "entity_type": entity_type.value,
                "entity_id": entity_id,
                "authenticated_user_hash": user_hash(user_id),
                "result": "success",
                "retryable": False,
                "projection_sync_status": "synchronized",
            },
        )
    except Exception:
        logger.error(
            "search_projection_delete_failed",
            extra={
                "operation": operation,
                "entity_type": entity_type.value,
                "entity_id": entity_id,
                "authenticated_user_hash": user_hash(user_id),
                "result": "failure",
                "retryable": True,
                "projection_sync_status": "reconciliation_required",
            },
        )

def normalize_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > 128 or any(character in normalized for character in "\r\n\t"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid idempotency key.")
    return normalized

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def prepare_create_fields(payload: ReminderCreate) -> dict:
    data = payload.model_dump()
    return prepare_smart_fields(data)

def prepare_update_fields(reminder: Reminder, updates: dict) -> dict:
    reminder_type = updates.get("reminder_type", reminder.reminder_type)
    if is_reminder_type(reminder_type, ReminderType.BIRTHDAY):
        merged = {**reminder.model_dump(), **updates}
        return prepare_birthday_fields(merged, keep_existing_timing=True)

    if is_reminder_type(reminder_type, ReminderType.RENEWAL):
        merged = {**reminder.model_dump(), **updates}
        return prepare_renewal_fields(merged, keep_existing_timing=True)

    if is_reminder_type(reminder_type, ReminderType.MAINTENANCE):
        merged = {**reminder.model_dump(), **updates}
        return prepare_maintenance_fields(merged, keep_existing_timing=True)

    if is_reminder_type(reminder_type, ReminderType.GENERIC):
        updates["reminder_type"] = ReminderType.GENERIC
        updates["birthday_details"] = None
        updates["renewal_details"] = None
        updates["maintenance_details"] = None

    return updates

def prepare_smart_fields(data: dict) -> dict:
    reminder_type = data.get("reminder_type", ReminderType.GENERIC)
    if is_reminder_type(reminder_type, ReminderType.BIRTHDAY):
        return prepare_birthday_fields(data)

    if is_reminder_type(reminder_type, ReminderType.RENEWAL):
        return prepare_renewal_fields(data)

    if is_reminder_type(reminder_type, ReminderType.MAINTENANCE):
        return prepare_maintenance_fields(data)

    data["reminder_type"] = ReminderType.GENERIC
    data["birthday_details"] = None
    data["renewal_details"] = None
    data["maintenance_details"] = None
    return data

def prepare_birthday_fields(data: dict, keep_existing_timing: bool = False) -> dict:
    if not is_reminder_type(data.get("reminder_type"), ReminderType.BIRTHDAY):
        data["reminder_type"] = ReminderType.GENERIC
        data["birthday_details"] = None
        data["renewal_details"] = None
        data["maintenance_details"] = None
        return data

    details = data.get("birthday_details")
    if details is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Birthday details are required")

    if not hasattr(details, "birth_month"):
        from app.schemas import BirthdayDetails

        details = BirthdayDetails.model_validate(details)

    due_date = get_next_birthday_due_date(details.birth_month, details.birth_day)
    try:
        enriched_details = enrich_birthday_details(details, due_date)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    data["reminder_type"] = ReminderType.BIRTHDAY
    data["birthday_details"] = enriched_details
    data["renewal_details"] = None
    data["maintenance_details"] = None
    data["due_date"] = due_date
    data["repeat"] = RepeatOption.YEARLY

    if not keep_existing_timing or data.get("reminder_lead_value") is None:
        data["reminder_lead_value"] = data.get("reminder_lead_value") if data.get("reminder_lead_value") is not None else 1
    if not keep_existing_timing or data.get("reminder_lead_unit") is None:
        data["reminder_lead_unit"] = data.get("reminder_lead_unit") or ReminderLeadUnit.WEEKS
    if not keep_existing_timing or data.get("reminder_time") is None:
        data["reminder_time"] = data.get("reminder_time") or "09:00"

    return data

def prepare_renewal_fields(data: dict, keep_existing_timing: bool = False) -> dict:
    if not is_reminder_type(data.get("reminder_type"), ReminderType.RENEWAL):
        data["reminder_type"] = ReminderType.GENERIC
        data["birthday_details"] = None
        data["renewal_details"] = None
        data["maintenance_details"] = None
        return data

    details = data.get("renewal_details")
    if details is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Renewal details are required")

    if not hasattr(details, "item_name"):
        details = RenewalDetails.model_validate(details)

    due_date = get_renewal_due_date(details)
    if due_date is not None:
        data["due_date"] = due_date

    data["reminder_type"] = ReminderType.RENEWAL
    data["birthday_details"] = None
    data["renewal_details"] = details
    data["maintenance_details"] = None

    if not keep_existing_timing or data.get("reminder_lead_value") is None:
        data["reminder_lead_value"] = data.get("reminder_lead_value") if data.get("reminder_lead_value") is not None else 1
    if not keep_existing_timing or data.get("reminder_lead_unit") is None:
        data["reminder_lead_unit"] = data.get("reminder_lead_unit") or ReminderLeadUnit.MONTHS
    if not keep_existing_timing or data.get("reminder_time") is None:
        data["reminder_time"] = data.get("reminder_time") or "09:00"

    return data

def prepare_maintenance_fields(data: dict, keep_existing_timing: bool = False) -> dict:
    if not is_reminder_type(data.get("reminder_type"), ReminderType.MAINTENANCE):
        data["reminder_type"] = ReminderType.GENERIC
        data["birthday_details"] = None
        data["renewal_details"] = None
        data["maintenance_details"] = None
        return data

    details = data.get("maintenance_details")
    if details is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Maintenance details are required")

    if not hasattr(details, "item_name"):
        details = MaintenanceDetails.model_validate(details)

    details = prepare_maintenance_details(details)
    due_date = get_maintenance_due_date(details)
    if due_date is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose the next maintenance due date")

    data["reminder_type"] = ReminderType.MAINTENANCE
    data["birthday_details"] = None
    data["renewal_details"] = None
    data["maintenance_details"] = details
    data["due_date"] = due_date
    if data.get("repeat") in (None, RepeatOption.NONE, RepeatOption.NONE.value):
        data["repeat"] = get_repeat_from_maintenance_interval(details)
    if data.get("priority") is None:
        data["priority"] = "Medium"

    if not keep_existing_timing or data.get("reminder_lead_value") is None:
        data["reminder_lead_value"] = data.get("reminder_lead_value") if data.get("reminder_lead_value") is not None else 1
    if not keep_existing_timing or data.get("reminder_lead_unit") is None:
        data["reminder_lead_unit"] = data.get("reminder_lead_unit") or ReminderLeadUnit.WEEKS
    if not keep_existing_timing or data.get("reminder_time") is None:
        data["reminder_time"] = data.get("reminder_time") or "09:00"

    return data

def get_computed_label(reminder: Reminder) -> str | None:
    if reminder.reminder_type == ReminderType.BIRTHDAY:
        return get_birthday_computed_label(reminder.birthday_details, reminder.due_date)

    if reminder.reminder_type == ReminderType.RENEWAL:
        return get_renewal_computed_label(reminder.renewal_details)

    if reminder.reminder_type == ReminderType.MAINTENANCE:
        return get_maintenance_computed_label(reminder.maintenance_details)

    return None

def get_response_next_due_date(reminder: Reminder):
    if reminder.reminder_type == ReminderType.MAINTENANCE:
        return get_maintenance_due_date(reminder.maintenance_details)

    return get_next_due_date(reminder.due_date, reminder.repeat)

def get_repeat_from_maintenance_interval(details: MaintenanceDetails) -> RepeatOption:
    if details.interval_value is None or details.interval_unit is None:
        return RepeatOption.NONE

    interval_value = details.interval_value
    interval_unit = details.interval_unit.value
    if interval_unit == "weeks" and interval_value == 1:
        return RepeatOption.WEEKLY
    if interval_unit == "months" and interval_value == 1:
        return RepeatOption.MONTHLY
    if interval_unit == "months" and interval_value == 3:
        return RepeatOption.QUARTERLY
    if (interval_unit == "years" and interval_value == 1) or (interval_unit == "months" and interval_value == 12):
        return RepeatOption.YEARLY

    return RepeatOption.NONE

def is_reminder_type(value: ReminderType | str | None, expected: ReminderType) -> bool:
    return value == expected or value == expected.value
