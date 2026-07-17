import hashlib
import logging
import time
from datetime import date, datetime, timedelta, timezone
from secrets import token_urlsafe
from uuid import uuid4

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

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
from app.models import DynamicRecordField, GoogleCalendarConnection, GoogleOAuthState, LinkedItem, PushSubscription, Record, RecordAttachment, Reminder
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
from app.reminder_lifecycle import append_lifecycle_event, has_recent_lifecycle_action
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
    create_saved_search_view_repository,
    create_search_index_repository,
)
from app.records_repository import RecordRepository
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
    ReminderAlertResponse,
    ReminderLeadUnit,
    ReminderLifecycleEventType,
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
from app.security_audit import log_security_event
from app.push_sender import (
    InvalidPushSubscriptionError,
    PushConfigurationError,
    PushPayload,
    PushSendError,
    PushSender,
    PyWebPushSender,
)

settings = get_settings()
app = FastAPI(title="LifeLedger API", version="0.1.0")
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins or [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_store_attachment_responses(request: Request, call_next):
    response = await call_next(request)
    if "/attachments" in request.url.path or "/fields/" in request.url.path:
        for header, value in no_store_headers().items():
            response.headers[header] = value
    return response

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


def get_app_settings() -> Settings:
    return get_settings()


def get_repository() -> ReminderRepository:
    return repository


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
    return SearchProjectionService(search_repo, record_repo, reminder_repo, attachment_repo, linked_repo)


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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/search", response_model=SearchResponse)
def search_items(
    q: str = Query(default="", max_length=120),
    item_types: str | None = Query(default=None, alias="itemTypes"),
    statuses: str | None = Query(default=None),
    archived: bool = Query(default=False),
    date_from: date | None = Query(default=None, alias="dateFrom"),
    date_to: date | None = Query(default=None, alias="dateTo"),
    category: str | None = Query(default=None, max_length=80),
    owner: str | None = Query(default=None, max_length=120),
    has_documents: bool | None = Query(default=None, alias="hasDocuments"),
    has_linked_items: bool | None = Query(default=None, alias="hasLinkedItems"),
    sort: SearchSort = Query(default=SearchSort.RELEVANCE),
    page_size: int = Query(default=20, ge=1, le=50, alias="pageSize"),
    cursor: str | None = Query(default=None, max_length=512),
    current_user: UserContext = Depends(get_current_user),
    search_service: SearchQueryService = Depends(get_search_query_service),
) -> SearchResponse:
    started = time.perf_counter()
    try:
        request = validate_search_request(
            query=q,
            item_types=item_types,
            statuses=statuses,
            include_archived=archived,
            date_from=date_from,
            date_to=date_to,
            category=category,
            owner=owner,
            has_documents=has_documents,
            has_linked_items=has_linked_items,
            sort=sort,
            page_size=page_size,
            cursor=cursor,
        )
        result = search_service.search(current_user.user_id, request)
    except SearchValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    latency_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "search_request",
        extra={
            "operation": "search",
            "query_present": bool(q.strip()),
            "query_length": len(q.strip()),
            "filter_types": sorted(key for key, value in result.applied_filters.items() if value not in (None, "", [], False)),
            "sort": sort.value,
            "page_size": page_size,
            "result_count": result.result_count,
            "has_next_page": result.next_cursor is not None,
            "latency_ms": latency_ms,
        },
    )
    return result


@app.get("/saved-views", response_model=list[SavedSearchViewResponse])
def list_saved_views(
    current_user: UserContext = Depends(get_current_user),
    service: SavedSearchViewService = Depends(get_saved_search_view_service),
) -> list[SavedSearchViewResponse]:
    return [to_saved_view_response(view) for view in service.list_views(current_user.user_id)]


@app.post("/saved-views", response_model=SavedSearchViewResponse, status_code=status.HTTP_201_CREATED)
def create_saved_view(
    payload: SavedSearchViewCreate,
    current_user: UserContext = Depends(get_current_user),
    service: SavedSearchViewService = Depends(get_saved_search_view_service),
) -> SavedSearchViewResponse:
    saved = service.create_view(
        user_id=current_user.user_id,
        saved_view_id=str(uuid4()),
        name=payload.name,
        query=payload.query,
        filters=payload.filters,
        sort=payload.sort,
        icon=payload.icon,
        is_pinned=payload.is_pinned,
        now=utc_now(),
    )
    return to_saved_view_response(saved)


@app.get("/saved-views/{saved_view_id}", response_model=SavedSearchViewResponse)
def get_saved_view(
    saved_view_id: str,
    current_user: UserContext = Depends(get_current_user),
    service: SavedSearchViewService = Depends(get_saved_search_view_service),
) -> SavedSearchViewResponse:
    view = service.get_view(current_user.user_id, saved_view_id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved view not found")
    return to_saved_view_response(view)


@app.patch("/saved-views/{saved_view_id}", response_model=SavedSearchViewResponse)
def update_saved_view(
    saved_view_id: str,
    payload: SavedSearchViewUpdate,
    current_user: UserContext = Depends(get_current_user),
    service: SavedSearchViewService = Depends(get_saved_search_view_service),
) -> SavedSearchViewResponse:
    view = service.get_view(current_user.user_id, saved_view_id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved view not found")
    updated = service.update_view(
        view,
        name=payload.name,
        query=payload.query,
        filters=payload.filters,
        sort=payload.sort,
        icon=payload.icon,
        is_pinned=payload.is_pinned,
        now=utc_now(),
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved view not found")
    return to_saved_view_response(updated)


@app.delete("/saved-views/{saved_view_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_view(
    saved_view_id: str,
    current_user: UserContext = Depends(get_current_user),
    service: SavedSearchViewService = Depends(get_saved_search_view_service),
) -> Response:
    if not service.delete_view(current_user.user_id, saved_view_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved view not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@app.get("/reminders", response_model=list[ReminderResponse])
def list_reminders(
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
    record_repo: RecordRepository = Depends(get_record_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
) -> list[ReminderResponse]:
    reminders = repo.list_reminders(current_user.user_id)
    sorted_reminders = sorted(reminders, key=lambda item: (item.completed, item.due_date, item.created_at))
    return [
        to_response(
            reminder,
            linked_records=get_reminder_linked_record_summaries(
                current_user.user_id,
                reminder.id,
                linked_repo,
                record_repo,
            ),
        )
        for reminder in sorted_reminders
    ]


@app.get("/alerts", response_model=list[ReminderAlertResponse])
def list_alerts(
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
) -> list[ReminderAlertResponse]:
    now = utc_now()
    current_day = date.today()
    alert_reminders = []

    for reminder in repo.list_reminders(current_user.user_id):
        eligibility = get_alert_eligibility(reminder, now, current_day=current_day)
        if eligibility is not None:
            alert_reminders.append((reminder, eligibility))

    return [to_alert_response(reminder, eligibility) for reminder, eligibility in sort_alerts(alert_reminders)]


@app.get("/records", response_model=list[RecordResponse])
def list_records(
    include_archived: bool = Query(default=False),
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
) -> list[RecordResponse]:
    records = repo.list_records(current_user.user_id, include_archived=include_archived)
    sorted_records = sorted(records, key=lambda item: (item.status == RecordStatus.ARCHIVED, item.title.lower(), item.created_at))
    return [to_record_response(record) for record in sorted_records]


@app.post("/records", response_model=RecordResponse, status_code=status.HTTP_201_CREATED)
def create_record(
    payload: RecordCreate,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> RecordResponse:
    now = utc_now()
    record_fields = payload.model_dump()
    record_fields["status"] = RecordStatus.ACTIVE
    record = Record(
        id=str(uuid4()),
        user_id=current_user.user_id,
        **record_fields,
        created_at=now,
        updated_at=now,
    )

    saved = repo.create_record(record)
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, saved.id, "record_create")
    return to_record_response(saved)


@app.get("/records/{record_id}", response_model=RecordResponse)
def get_record(
    record_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
) -> RecordResponse:
    return to_record_response(require_record(repo, current_user.user_id, record_id))


@app.put("/records/{record_id}", response_model=RecordResponse)
def update_record(
    record_id: str,
    payload: RecordUpdate,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> RecordResponse:
    record = require_record(repo, current_user.user_id, record_id)
    updates = payload.model_dump(exclude_unset=True)
    for required_field in ("record_type", "title", "category", "status"):
        if updates.get(required_field) is None:
            updates.pop(required_field, None)
    if "tags" in updates and updates["tags"] is None:
        updates["tags"] = []
    updated = Record.model_validate({**record.model_dump(), **updates, "updated_at": utc_now()})
    saved = repo.update_record(updated)
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, saved.id, "record_update")
    return to_record_response(saved)


@app.post("/records/{record_id}/fields", response_model=RecordResponse, status_code=status.HTTP_201_CREATED)
def add_record_field(
    record_id: str,
    payload: DynamicRecordFieldCreate,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    encryption_service: EncryptionService = Depends(get_encryption_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> RecordResponse:
    record = require_record(repo, current_user.user_id, record_id)
    if len(record.dynamic_fields) >= 30:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Records can have up to 30 custom fields.")

    now = utc_now()
    field_id = str(uuid4())
    field_value = payload.value
    field = DynamicRecordField(
        field_id=field_id,
        key=normalize_dynamic_field_key(payload.key or payload.label, field_id),
        label=payload.label,
        field_type=payload.field_type,
        value=None if payload.is_sensitive else field_value,
        is_sensitive=payload.is_sensitive,
        has_value=dynamic_value_has_content(field_value),
        display_order=payload.display_order if payload.display_order is not None else next_dynamic_field_order(record),
        select_options=payload.select_options,
        created_at=now,
        updated_at=now,
    )

    updated_record = record.model_copy(update={"dynamic_fields": sorted_dynamic_fields([*record.dynamic_fields, field]), "updated_at": now})
    if field.is_sensitive and dynamic_value_has_content(field_value):
        updated_record = set_dynamic_sensitive_value(record, updated_record, field.field_id, field_value, encryption_service, now)

    saved = repo.update_record(updated_record)
    log_security_event(
        "record_dynamic_field_created",
        user_id=current_user.user_id,
        record_id=record.id,
        field_id=field.field_id,
        field_type=field.field_type.value,
        is_sensitive=field.is_sensitive,
        result="success",
    )
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, saved.id, "record_field_create")
    return to_record_response(saved)


@app.put("/records/{record_id}/fields/{field_id}", response_model=RecordResponse)
def update_record_field(
    record_id: str,
    field_id: str,
    payload: DynamicRecordFieldUpdate,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    encryption_service: EncryptionService = Depends(get_encryption_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> RecordResponse:
    record = require_record(repo, current_user.user_id, record_id)
    existing = find_dynamic_field(record, field_id)
    updates = payload.model_dump(exclude_unset=True)
    now = utc_now()

    next_type = updates.get("field_type", existing.field_type)
    next_select_options = updates.get("select_options", existing.select_options)
    if "value" in updates:
        updates["value"] = normalize_dynamic_field_value(next_type, updates["value"], next_select_options)

    if next_type != existing.field_type and existing.has_value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Remove and recreate this field to change its type without losing data.",
        )

    next_sensitive = updates.get("is_sensitive", existing.is_sensitive)
    if next_sensitive != existing.is_sensitive and existing.has_value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Remove and recreate this populated field to change its sensitivity.",
        )

    next_value = updates.pop("value", existing.value)
    if next_sensitive:
        next_value_for_model = None
        next_has_value = existing.has_value
        if "value" in payload.model_fields_set:
            next_has_value = dynamic_value_has_content(next_value)
    else:
        next_value_for_model = next_value
        next_has_value = dynamic_value_has_content(next_value)

    updated_field = existing.model_copy(
        update={
            **updates,
            "field_type": next_type,
            "is_sensitive": next_sensitive,
            "select_options": next_select_options,
            "value": next_value_for_model,
            "has_value": next_has_value,
            "updated_at": now,
        }
    )
    updated_record = record.model_copy(
        update={
            "dynamic_fields": sorted_dynamic_fields(replace_dynamic_field(record.dynamic_fields, updated_field)),
            "updated_at": now,
        }
    )

    if updated_field.is_sensitive and "value" in payload.model_fields_set:
        updated_record = set_dynamic_sensitive_value(record, updated_record, field_id, next_value, encryption_service, now)
    elif existing.is_sensitive and not updated_field.is_sensitive:
        updated_record = remove_dynamic_sensitive_value(record, updated_record, field_id, encryption_service, now)

    saved = repo.update_record(updated_record)
    log_security_event(
        "record_dynamic_field_updated",
        user_id=current_user.user_id,
        record_id=record.id,
        field_id=field_id,
        field_type=updated_field.field_type.value,
        is_sensitive=updated_field.is_sensitive,
        result="success",
    )
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, saved.id, "record_field_update")
    return to_record_response(saved)


@app.get("/records/{record_id}/fields/{field_id}/reveal", response_model=DynamicRecordFieldRevealResponse)
def reveal_record_field(
    record_id: str,
    field_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    encryption_service: EncryptionService = Depends(get_encryption_service),
) -> DynamicRecordFieldRevealResponse:
    for header, value in no_store_headers().items():
        response.headers[header] = value
    record = require_record(repo, current_user.user_id, record_id)
    field = find_dynamic_field(record, field_id)
    if not field.is_sensitive:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only sensitive fields require reveal.")
    if not field.has_value:
        return DynamicRecordFieldRevealResponse(field_id=field_id, value=None)

    values = decrypt_record_private_payload(record, encryption_service)
    dynamic_values = protected_dynamic_values(values)
    if field_id not in dynamic_values:
        return DynamicRecordFieldRevealResponse(field_id=field_id, value=None)

    log_security_event(
        "record_dynamic_field_revealed",
        user_id=current_user.user_id,
        record_id=record.id,
        field_id=field_id,
        result="success",
    )
    return DynamicRecordFieldRevealResponse(field_id=field_id, value=dynamic_values[field_id])


@app.delete("/records/{record_id}/fields/{field_id}", response_model=RecordResponse)
def delete_record_field(
    record_id: str,
    field_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    encryption_service: EncryptionService = Depends(get_encryption_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> RecordResponse:
    record = require_record(repo, current_user.user_id, record_id)
    existing = find_dynamic_field(record, field_id)
    now = utc_now()
    updated_record = record.model_copy(
        update={
            "dynamic_fields": [field for field in record.dynamic_fields if field.field_id != field_id],
            "updated_at": now,
        }
    )
    if existing.is_sensitive:
        updated_record = remove_dynamic_sensitive_value(record, updated_record, field_id, encryption_service, now)

    saved = repo.update_record(updated_record)
    log_security_event(
        "record_dynamic_field_deleted",
        user_id=current_user.user_id,
        record_id=record.id,
        field_id=field_id,
        result="success",
    )
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, saved.id, "record_field_delete")
    return to_record_response(saved)

@app.post("/records/{record_id}/archive", response_model=RecordResponse)
def archive_record(
    record_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> RecordResponse:
    archived = repo.archive_record(current_user.user_id, record_id)
    if archived is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, archived.id, "record_archive")
    return to_record_response(archived)


@app.post("/records/{record_id}/restore", response_model=RecordResponse)
def restore_record(
    record_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> RecordResponse:
    restored = repo.unarchive_record(current_user.user_id, record_id)
    if restored is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, restored.id, "record_restore")
    return to_record_response(restored)


@app.delete("/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(
    record_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    document_storage=Depends(get_document_storage_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> Response:
    require_record(repo, current_user.user_id, record_id)
    deleted_links = linked_repo.list_links_for_entity(current_user.user_id, LinkedEntityType.RECORD, record_id)
    cleanup_record_attachments_before_delete(
        current_user.user_id,
        record_id,
        attachment_repo,
        document_storage,
        linked_repo,
    )
    linked_repo.delete_links_for_entity(current_user.user_id, LinkedEntityType.RECORD, record_id)
    deleted = repo.delete_record(current_user.user_id, record_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    sync_linked_search_neighbors_safe(
        search_service,
        current_user.user_id,
        deleted_links,
        "record_delete_relationship_cleanup",
        excluded_entities={(LinkedEntityType.RECORD, record_id)},
    )
    delete_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, record_id, "record_delete")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/records/{record_id}/links", response_model=LinkedItemsResponse)
def list_record_links(
    record_id: str,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    reminder_repo: ReminderRepository = Depends(get_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
) -> LinkedItemsResponse:
    require_record(record_repo, current_user.user_id, record_id)
    return get_entity_neighborhood(
        current_user.user_id,
        LinkedEntityType.RECORD,
        record_id,
        linked_repo,
        record_repo,
        reminder_repo,
        attachment_repo,
    )


@app.post("/records/{record_id}/links", response_model=LinkedItemResponse, status_code=status.HTTP_201_CREATED)
def add_record_link(
    record_id: str,
    payload: LinkCreateRequest,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    reminder_repo: ReminderRepository = Depends(get_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> LinkedItemResponse:
    source_record = require_record(record_repo, current_user.user_id, record_id)
    assert_supported_record_link(payload)
    response = create_record_link(
        current_user.user_id,
        source_record,
        payload,
        linked_repo,
        record_repo,
        reminder_repo,
        utc_now(),
        attachment_repo,
    )
    log_security_event(
        "linked_item_created",
        user_id=current_user.user_id,
        source_type=LinkedEntityType.RECORD.value,
        source_id=record_id,
        target_type=payload.target_type.value,
        target_id=payload.target_id,
        relationship_type=payload.relationship_type.value,
        result="created",
    )
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, record_id, "relationship_create")
    sync_search_entity_safe(search_service, current_user.user_id, payload.target_type, payload.target_id, "relationship_create")
    return response


@app.delete("/records/{record_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_record_link(
    record_id: str,
    link_id: str,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> Response:
    require_record(record_repo, current_user.user_id, record_id)
    link = require_link_for_entity(current_user.user_id, link_id, LinkedEntityType.RECORD, record_id, linked_repo)
    linked_repo.delete_link(current_user.user_id, link_id)
    log_security_event(
        "linked_item_removed",
        user_id=current_user.user_id,
        source_type=link.source_type.value,
        source_id=link.source_id,
        target_type=link.target_type.value,
        target_id=link.target_id,
        relationship_type=link.relationship_type.value,
        result="removed",
    )
    sync_search_entity_safe(search_service, current_user.user_id, link.source_type, link.source_id, "relationship_delete")
    sync_search_entity_safe(search_service, current_user.user_id, link.target_type, link.target_id, "relationship_delete")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/relationships/candidates", response_model=RelationshipCandidatesResponse)
def list_relationship_candidates(
    source_item_type: LinkedEntityType = Query(...),
    source_item_id: str = Query(..., min_length=1, max_length=240),
    item_type: LinkedEntityType | None = Query(default=None),
    q: str = Query(default="", max_length=120),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=25, ge=1, le=50),
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    reminder_repo: ReminderRepository = Depends(get_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
) -> RelationshipCandidatesResponse:
    resolver = ItemResolver(record_repo, reminder_repo, attachment_repo)
    return resolver.candidates(
        current_user.user_id,
        source_item_type,
        source_item_id,
        linked_repo,
        item_type=item_type,
        query=q,
        include_archived=include_archived,
        limit=limit,
    )


@app.post("/relationships", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED)
def create_relationship_route(
    payload: RelationshipCreateRequest,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    reminder_repo: ReminderRepository = Depends(get_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> RelationshipResponse:
    response = create_relationship(
        current_user.user_id,
        payload,
        linked_repo,
        record_repo,
        reminder_repo,
        utc_now(),
        attachment_repo,
    )
    log_security_event(
        "relationship_created",
        user_id=current_user.user_id,
        relationship_id=response.relationship_id,
        source_type=payload.source_item_type.value,
        target_type=payload.target_item_type.value,
        relationship_type=payload.relationship_type.value,
        result="created",
    )
    sync_search_entity_safe(search_service, current_user.user_id, payload.source_item_type, payload.source_item_id, "relationship_create")
    sync_search_entity_safe(search_service, current_user.user_id, payload.target_item_type, payload.target_item_id, "relationship_create")
    return response


@app.get("/relationships/{relationship_id}", response_model=RelationshipResponse)
def get_relationship_route(
    relationship_id: str,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    reminder_repo: ReminderRepository = Depends(get_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
) -> RelationshipResponse:
    return read_relationship(
        current_user.user_id,
        relationship_id,
        linked_repo,
        record_repo,
        reminder_repo,
        attachment_repo,
    )


@app.patch("/relationships/{relationship_id}", response_model=RelationshipResponse)
def update_relationship_route(
    relationship_id: str,
    payload: RelationshipUpdateRequest,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    reminder_repo: ReminderRepository = Depends(get_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> RelationshipResponse:
    response = update_relationship(
        current_user.user_id,
        relationship_id,
        payload,
        linked_repo,
        record_repo,
        reminder_repo,
        utc_now(),
        attachment_repo,
    )
    log_security_event(
        "relationship_updated",
        user_id=current_user.user_id,
        relationship_id=relationship_id,
        relationship_type=response.relationship_type.value,
        result="updated",
    )
    sync_search_entity_safe(search_service, current_user.user_id, response.source_item.entity_type, response.source_item.id, "relationship_update")
    sync_search_entity_safe(search_service, current_user.user_id, response.target_item.entity_type, response.target_item.id, "relationship_update")
    return response


@app.delete("/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relationship_route(
    relationship_id: str,
    current_user: UserContext = Depends(get_current_user),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> Response:
    link = delete_relationship(current_user.user_id, relationship_id, linked_repo)
    log_security_event(
        "relationship_removed",
        user_id=current_user.user_id,
        relationship_id=relationship_id,
        source_type=link.source_type.value,
        target_type=link.target_type.value,
        relationship_type=link.relationship_type.value,
        result="removed",
    )
    sync_search_entity_safe(search_service, current_user.user_id, link.source_type, link.source_id, "relationship_delete")
    sync_search_entity_safe(search_service, current_user.user_id, link.target_type, link.target_id, "relationship_delete")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/records/{record_id}/attachments", response_model=list[RecordAttachmentResponse])
def list_record_attachments(
    record_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    document_storage=Depends(get_document_storage_service),
    app_settings: Settings = Depends(get_app_settings),
) -> list[RecordAttachmentResponse]:
    set_attachment_no_store(response)
    require_record(record_repo, current_user.user_id, record_id)
    attachments = [
        maybe_reconcile_attachment(attachment, attachment_repo, document_storage, app_settings)
        for attachment in attachment_repo.list_for_record(current_user.user_id, record_id)
    ]
    return [to_attachment_response(attachment) for attachment in sort_attachments(attachments)]


@app.post(
    "/records/{record_id}/attachments/upload-intent",
    response_model=RecordAttachmentUploadIntentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_record_attachment_upload_intent(
    record_id: str,
    payload: RecordAttachmentUploadIntentRequest,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    document_storage=Depends(get_document_storage_service),
    app_settings: Settings = Depends(get_app_settings),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> RecordAttachmentUploadIntentResponse:
    set_attachment_no_store(response)
    require_record(record_repo, current_user.user_id, record_id)
    require_document_storage_configured(document_storage)

    try:
        attachment = new_record_attachment(
            user_id=current_user.user_id,
            record_id=record_id,
            filename=payload.filename,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
            settings=app_settings,
            now=utc_now(),
        )
    except AttachmentValidationError as exc:
        raise attachment_http_exception(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.safe_message) from exc

    existing = attachment_repo.list_for_record(current_user.user_id, record_id)
    if active_attachment_count(existing) >= app_settings.attachment_max_per_record:
        raise attachment_http_exception(
            status.HTTP_409_CONFLICT,
            "Records can have up to 5 active attachments.",
        )

    saved = attachment_repo.create_attachment(attachment)
    document_entity_id = document_item_id(record_id, saved.attachment_id)
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.DOCUMENT, document_entity_id, "document_create")
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, record_id, "document_create")
    try:
        presigned_upload = document_storage.create_presigned_upload(
            saved,
            max_size_bytes=app_settings.attachment_max_size_bytes,
            expires_in_seconds=UPLOAD_INTENT_EXPIRATION_SECONDS,
        )
    except (DocumentStorageConfigurationError, DocumentStorageOperationError) as exc:
        attachment_repo.delete_attachment_metadata(current_user.user_id, record_id, saved.attachment_id)
        delete_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.DOCUMENT, document_entity_id, "document_create_rollback")
        sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, record_id, "document_create_rollback")
        raise attachment_http_exception(status.HTTP_503_SERVICE_UNAVAILABLE, exc.safe_message) from exc

    log_security_event(
        "attachment_upload_intent_created",
        user_id=current_user.user_id,
        record_id=record_id,
        attachment_id=saved.attachment_id,
        content_type=saved.content_type,
        size=saved.size_bytes,
        result="created",
    )
    return RecordAttachmentUploadIntentResponse(
        attachment_id=saved.attachment_id,
        upload=presigned_upload,
        expires_at=saved.upload_expires_at,
        max_size_bytes=app_settings.attachment_max_size_bytes,
    )


@app.post("/records/{record_id}/attachments/{attachment_id}/complete", response_model=RecordAttachmentResponse)
def complete_record_attachment_upload(
    record_id: str,
    attachment_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    document_storage=Depends(get_document_storage_service),
    app_settings: Settings = Depends(get_app_settings),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> RecordAttachmentResponse:
    set_attachment_no_store(response)
    require_record(record_repo, current_user.user_id, record_id)
    require_document_storage_configured(document_storage)
    attachment = require_attachment(attachment_repo, current_user.user_id, record_id, attachment_id)

    try:
        completed = complete_attachment_upload(
            attachment=attachment,
            storage=document_storage,
            settings=app_settings,
            now=utc_now(),
        )
    except AttachmentValidationError as exc:
        reject_failed_upload(attachment, attachment_repo, document_storage)
        raise attachment_http_exception(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.safe_message) from exc
    except (DocumentStorageConfigurationError, DocumentStorageOperationError) as exc:
        raise attachment_http_exception(status.HTTP_503_SERVICE_UNAVAILABLE, exc.safe_message) from exc

    saved = attachment_repo.update_attachment(completed)
    document_entity_id = document_item_id(record_id, attachment_id)
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.DOCUMENT, document_entity_id, "document_upload_complete")
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, record_id, "document_upload_complete")
    log_security_event(
        "attachment_upload_completed",
        user_id=current_user.user_id,
        record_id=record_id,
        attachment_id=attachment_id,
        content_type=saved.content_type,
        size=saved.size_bytes,
        result="scanning",
    )
    return to_attachment_response(saved)


@app.get("/records/{record_id}/attachments/{attachment_id}", response_model=RecordAttachmentResponse)
def get_record_attachment(
    record_id: str,
    attachment_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    document_storage=Depends(get_document_storage_service),
    app_settings: Settings = Depends(get_app_settings),
) -> RecordAttachmentResponse:
    set_attachment_no_store(response)
    require_record(record_repo, current_user.user_id, record_id)
    attachment = require_attachment(attachment_repo, current_user.user_id, record_id, attachment_id)
    return to_attachment_response(maybe_reconcile_attachment(attachment, attachment_repo, document_storage, app_settings))


@app.post("/records/{record_id}/attachments/{attachment_id}/refresh-status", response_model=RecordAttachmentResponse)
def refresh_record_attachment_status(
    record_id: str,
    attachment_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    document_storage=Depends(get_document_storage_service),
    app_settings: Settings = Depends(get_app_settings),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> RecordAttachmentResponse:
    set_attachment_no_store(response)
    require_record(record_repo, current_user.user_id, record_id)
    attachment = require_attachment(attachment_repo, current_user.user_id, record_id, attachment_id)
    refreshed = maybe_reconcile_attachment(attachment, attachment_repo, document_storage, app_settings)
    document_entity_id = document_item_id(record_id, attachment_id)
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.DOCUMENT, document_entity_id, "document_refresh")
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, record_id, "document_refresh")
    return to_attachment_response(refreshed)


@app.post("/records/{record_id}/attachments/{attachment_id}/download-url", response_model=RecordAttachmentDownloadUrlResponse)
def create_record_attachment_download_url(
    record_id: str,
    attachment_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    document_storage=Depends(get_document_storage_service),
    app_settings: Settings = Depends(get_app_settings),
) -> RecordAttachmentDownloadUrlResponse:
    set_attachment_no_store(response)
    require_record(record_repo, current_user.user_id, record_id)
    require_document_storage_configured(document_storage)
    attachment = require_attachment(attachment_repo, current_user.user_id, record_id, attachment_id)
    attachment = maybe_reconcile_attachment(attachment, attachment_repo, document_storage, app_settings)

    if attachment.status != AttachmentStatus.AVAILABLE or not attachment.clean_object_key:
        raise attachment_http_exception(status.HTTP_409_CONFLICT, ATTACHMENT_NOT_AVAILABLE)

    try:
        document_storage.head_clean_object(attachment.clean_object_key)
        url = document_storage.create_presigned_download(
            attachment,
            content_disposition=attachment_content_disposition(attachment),
            expires_in_seconds=DOWNLOAD_URL_EXPIRATION_SECONDS,
        )
    except (DocumentStorageConfigurationError, DocumentStorageOperationError) as exc:
        raise attachment_http_exception(status.HTTP_503_SERVICE_UNAVAILABLE, exc.safe_message) from exc

    log_security_event(
        "attachment_download_url_issued",
        user_id=current_user.user_id,
        record_id=record_id,
        attachment_id=attachment_id,
        content_type=attachment.content_type,
        size=attachment.size_bytes,
        result="issued",
    )
    return RecordAttachmentDownloadUrlResponse(
        url=url,
        expires_at=utc_now() + timedelta(seconds=DOWNLOAD_URL_EXPIRATION_SECONDS),
    )


@app.post("/records/{record_id}/attachments/{attachment_id}/preview-url", response_model=RecordAttachmentDownloadUrlResponse)
def create_record_attachment_preview_url(
    record_id: str,
    attachment_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    document_storage=Depends(get_document_storage_service),
    app_settings: Settings = Depends(get_app_settings),
) -> RecordAttachmentDownloadUrlResponse:
    set_attachment_no_store(response)
    require_record(record_repo, current_user.user_id, record_id)
    require_document_storage_configured(document_storage)
    attachment = require_attachment(attachment_repo, current_user.user_id, record_id, attachment_id)
    attachment = maybe_reconcile_attachment(attachment, attachment_repo, document_storage, app_settings)

    if attachment.status != AttachmentStatus.AVAILABLE or not attachment.clean_object_key:
        raise attachment_http_exception(status.HTTP_409_CONFLICT, ATTACHMENT_NOT_AVAILABLE)

    try:
        document_storage.head_clean_object(attachment.clean_object_key)
        url = document_storage.create_presigned_download(
            attachment,
            content_disposition=attachment_content_disposition(attachment, "inline"),
            expires_in_seconds=DOWNLOAD_URL_EXPIRATION_SECONDS,
        )
    except (DocumentStorageConfigurationError, DocumentStorageOperationError) as exc:
        raise attachment_http_exception(status.HTTP_503_SERVICE_UNAVAILABLE, exc.safe_message) from exc

    log_security_event(
        "attachment_preview_url_issued",
        user_id=current_user.user_id,
        record_id=record_id,
        attachment_id=attachment_id,
        content_type=attachment.content_type,
        size=attachment.size_bytes,
        result="issued",
    )
    return RecordAttachmentDownloadUrlResponse(
        url=url,
        expires_at=utc_now() + timedelta(seconds=DOWNLOAD_URL_EXPIRATION_SECONDS),
    )


@app.delete("/records/{record_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record_attachment(
    record_id: str,
    attachment_id: str,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    document_storage=Depends(get_document_storage_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> Response:
    require_record(record_repo, current_user.user_id, record_id)
    attachment = require_attachment(attachment_repo, current_user.user_id, record_id, attachment_id)
    document_entity_id = document_item_id(record_id, attachment_id)
    deleted_links = linked_repo.list_links_for_entity(current_user.user_id, LinkedEntityType.DOCUMENT, document_entity_id)
    cleanup_attachment_or_raise(attachment, attachment_repo, document_storage)
    linked_repo.delete_links_for_entity(
        current_user.user_id,
        LinkedEntityType.DOCUMENT,
        document_entity_id,
    )
    sync_linked_search_neighbors_safe(
        search_service,
        current_user.user_id,
        deleted_links,
        "document_delete_relationship_cleanup",
        excluded_entities={(LinkedEntityType.DOCUMENT, document_entity_id)},
    )
    delete_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.DOCUMENT, document_entity_id, "document_delete")
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, record_id, "document_delete")
    log_security_event(
        "attachment_deleted",
        user_id=current_user.user_id,
        record_id=record_id,
        attachment_id=attachment_id,
        content_type=attachment.content_type,
        size=attachment.size_bytes,
        result="deleted",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=no_store_headers())


@app.get("/records/{record_id}/protected/status", response_model=ProtectedRecordStatusResponse)
def get_protected_record_status(
    record_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
) -> ProtectedRecordStatusResponse:
    record = require_record(repo, current_user.user_id, record_id)
    return to_protected_record_status(record)


@app.put("/records/{record_id}/protected", response_model=ProtectedRecordStatusResponse)
def set_protected_record_payload(
    record_id: str,
    payload: ProtectedRecordPayload,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    encryption_service: EncryptionService = Depends(get_encryption_service),
) -> ProtectedRecordStatusResponse:
    record = require_record(repo, current_user.user_id, record_id)
    values = payload.safe_values()
    validate_protected_record_fields(record, values)
    now = utc_now()
    current_payload = decrypt_record_private_payload(record, encryption_service) if record_has_protected_data(record) else {}
    dynamic_values = protected_dynamic_values(current_payload)

    if not values and not dynamic_values:
        cleared = repo.update_record(clear_record_protected_fields(record, now))
        log_security_event(
            "protected_record_cleared",
            user_id=current_user.user_id,
            record_id=record.id,
            record_type=record.record_type.value,
            result="success",
        )
        return to_protected_record_status(cleared)

    next_payload = {**values}
    if dynamic_values:
        next_payload[DYNAMIC_PROTECTED_VALUES_KEY] = dynamic_values

    updated = encrypt_record_private_payload(record, next_payload, sorted(values.keys()), encryption_service, now)
    saved = repo.update_record(updated)
    log_security_event(
        "protected_record_set",
        user_id=current_user.user_id,
        record_id=record.id,
        record_type=record.record_type.value,
        result="success",
    )
    return to_protected_record_status(saved)

@app.get("/records/{record_id}/protected", response_model=ProtectedRecordPayload)
def reveal_protected_record_payload(
    record_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    encryption_service: EncryptionService = Depends(get_encryption_service),
) -> ProtectedRecordPayload:
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    record = require_record(repo, current_user.user_id, record_id)

    if not record_has_protected_data(record):
        return ProtectedRecordPayload()

    try:
        decrypted = encryption_service.decrypt_json(record_encrypted_payload(record), record_encryption_context(record.user_id, record.id))
    except EncryptionConfigurationError as exc:
        log_security_event(
            "protected_record_decrypt_failed",
            user_id=current_user.user_id,
            record_id=record.id,
            record_type=record.record_type.value,
            result="configuration_missing",
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.safe_message) from exc
    except EncryptionOperationError as exc:
        log_security_event(
            "protected_record_decrypt_failed",
            user_id=current_user.user_id,
            record_id=record.id,
            record_type=record.record_type.value,
            result="decrypt_failed",
        )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.safe_message) from exc

    allowed = protected_fields_for_record(record)
    safe_payload = {field: value for field, value in decrypted.items() if field in allowed}
    log_security_event(
        "protected_record_revealed",
        user_id=current_user.user_id,
        record_id=record.id,
        record_type=record.record_type.value,
        result="success",
    )
    return ProtectedRecordPayload.model_validate(safe_payload)


@app.delete("/records/{record_id}/protected", response_model=ProtectedRecordStatusResponse)
def clear_protected_record_payload(
    record_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    encryption_service: EncryptionService = Depends(get_encryption_service),
) -> ProtectedRecordStatusResponse:
    record = require_record(repo, current_user.user_id, record_id)
    now = utc_now()
    current_payload = decrypt_record_private_payload(record, encryption_service) if record_has_protected_data(record) else {}
    dynamic_values = protected_dynamic_values(current_payload)
    if dynamic_values:
        updated = encrypt_record_private_payload(
            record,
            {DYNAMIC_PROTECTED_VALUES_KEY: dynamic_values},
            [],
            encryption_service,
            now,
        )
    else:
        updated = clear_record_protected_fields(record, now)

    cleared = repo.update_record(updated)
    log_security_event(
        "protected_record_cleared",
        user_id=current_user.user_id,
        record_id=record.id,
        record_type=record.record_type.value,
        result="success",
    )
    return to_protected_record_status(cleared)

@app.get("/preferences/digest", response_model=DigestPreferences)
def get_digest_preferences(
    current_user: UserContext = Depends(get_current_user),
    repo: PreferencesRepository = Depends(get_preferences_repository),
) -> DigestPreferences:
    preferences = repo.get_preferences(current_user.user_id) or default_digest_preferences(current_user.user_id, utc_now())
    return to_digest_preferences_response(preferences)


@app.put("/preferences/digest", response_model=DigestPreferences)
def update_digest_preferences(
    payload: DigestPreferencesUpdate,
    current_user: UserContext = Depends(get_current_user),
    repo: PreferencesRepository = Depends(get_preferences_repository),
) -> DigestPreferences:
    now = utc_now()
    current = repo.get_preferences(current_user.user_id) or default_digest_preferences(current_user.user_id, now)
    updates = payload.model_dump(exclude_unset=True)
    updated = current.model_copy(update={**updates, "updated_at": now})

    return to_digest_preferences_response(repo.save_preferences(updated))




@app.get("/integrations/google-calendar/status", response_model=GoogleCalendarStatusResponse)
def get_google_calendar_status(
    current_user: UserContext = Depends(get_current_user),
    repo: GoogleCalendarConnectionRepository = Depends(get_google_calendar_connection_repository),
    app_settings: Settings = Depends(get_app_settings),
) -> GoogleCalendarStatusResponse:
    connection = repo.get_connection(current_user.user_id)
    return to_google_calendar_status_response(app_settings, connection)


@app.post("/integrations/google-calendar/connect", response_model=GoogleCalendarConnectResponse)
def connect_google_calendar(
    current_user: UserContext = Depends(get_current_user),
    state_repo: GoogleOAuthStateRepository = Depends(get_google_oauth_state_repository),
    app_settings: Settings = Depends(get_app_settings),
    calendar_service: GoogleCalendarService = Depends(get_google_calendar_service),
) -> GoogleCalendarConnectResponse:
    if not app_settings.google_calendar_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Calendar sync is not configured for this environment.",
        )

    now = utc_now()
    state = token_urlsafe(32)
    state_repo.save_state(
        GoogleOAuthState(
            state=state,
            user_id=current_user.user_id,
            created_at=now,
            expires_at=now + timedelta(minutes=10),
        )
    )

    try:
        authorization_url = calendar_service.build_authorization_url(state)
    except GoogleCalendarConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.safe_message) from exc

    return GoogleCalendarConnectResponse(authorization_url=authorization_url)


@app.post("/integrations/google-calendar/callback", response_model=GoogleCalendarStatusResponse)
def complete_google_calendar_connection(
    payload: GoogleCalendarCallbackRequest,
    current_user: UserContext = Depends(get_current_user),
    connection_repo: GoogleCalendarConnectionRepository = Depends(get_google_calendar_connection_repository),
    state_repo: GoogleOAuthStateRepository = Depends(get_google_oauth_state_repository),
    app_settings: Settings = Depends(get_app_settings),
    calendar_service: GoogleCalendarService = Depends(get_google_calendar_service),
) -> GoogleCalendarStatusResponse:
    if not app_settings.google_calendar_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Calendar sync is not configured for this environment.",
        )

    now = utc_now()
    saved_state = state_repo.get_state(payload.state)
    invalid_state_reason = get_google_oauth_invalid_state_reason(saved_state, current_user.user_id, now)
    if invalid_state_reason is not None:
        log_invalid_google_oauth_state(invalid_state_reason, payload.state)
        if invalid_state_reason == "already_consumed":
            connection = connection_repo.get_connection(current_user.user_id)
            if connection is not None:
                return to_google_calendar_status_response(app_settings, connection)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google Calendar connection expired. Try again.")

    consumed_state = state_repo.consume_state(payload.state, now)
    if consumed_state is None:
        log_invalid_google_oauth_state("already_consumed", payload.state)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google Calendar connection expired. Try again.")

    try:
        token_set = calendar_service.exchange_authorization_code(payload.code)
    except GoogleCalendarConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.safe_message) from exc
    except GoogleCalendarAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.safe_message) from exc
    except GoogleCalendarError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.safe_message) from exc

    existing = connection_repo.get_connection(current_user.user_id)
    connection = GoogleCalendarConnection(
        user_id=current_user.user_id,
        google_account_email=(token_set.google_account_email or existing.google_account_email) if existing else token_set.google_account_email,
        calendar_id=existing.calendar_id if existing else "primary",
        calendar_label=selected_calendar_label(existing) if existing else "Primary calendar",
        access_token=token_set.access_token,
        refresh_token=token_set.refresh_token or "",
        token_expires_at=token_set.token_expires_at,
        scopes=token_set.scopes,
        connected_at=existing.connected_at if existing else now,
        updated_at=now,
        disconnected_at=None,
        status=GoogleCalendarConnectionStatus.CONNECTED,
        last_error=None,
    )
    saved_connection = connection_repo.save_connection(connection)

    return to_google_calendar_status_response(app_settings, saved_connection)


@app.get("/integrations/google-calendar/calendars", response_model=list[GoogleCalendarOptionResponse])
def list_google_calendar_options(
    current_user: UserContext = Depends(get_current_user),
    connection_repo: GoogleCalendarConnectionRepository = Depends(get_google_calendar_connection_repository),
    app_settings: Settings = Depends(get_app_settings),
    calendar_service: GoogleCalendarService = Depends(get_google_calendar_service),
) -> list[GoogleCalendarOptionResponse]:
    now = utc_now()
    connection = require_ready_google_connection(connection_repo, current_user.user_id, app_settings, calendar_service, now)
    options = list_google_calendar_options_or_raise(connection_repo, calendar_service, connection, now)
    return [to_google_calendar_option_response(option, connection.calendar_id) for option in options]


@app.put("/integrations/google-calendar/calendar", response_model=GoogleCalendarStatusResponse)
def update_google_calendar_selection(
    payload: GoogleCalendarSelectRequest,
    current_user: UserContext = Depends(get_current_user),
    connection_repo: GoogleCalendarConnectionRepository = Depends(get_google_calendar_connection_repository),
    app_settings: Settings = Depends(get_app_settings),
    calendar_service: GoogleCalendarService = Depends(get_google_calendar_service),
) -> GoogleCalendarStatusResponse:
    now = utc_now()
    connection = require_ready_google_connection(connection_repo, current_user.user_id, app_settings, calendar_service, now)
    options = list_google_calendar_options_or_raise(connection_repo, calendar_service, connection, now)
    selected = next(
        (
            option
            for option in options
            if option.id == payload.calendar_id and option.access_role in WRITABLE_CALENDAR_ACCESS_ROLES
        ),
        None,
    )
    if selected is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select a writable Google Calendar.")

    updated = connection.model_copy(
        update={
            "calendar_id": selected.id,
            "calendar_label": selected.label,
            "updated_at": now,
            "status": GoogleCalendarConnectionStatus.CONNECTED,
            "last_error": None,
        }
    )
    saved_connection = connection_repo.save_connection(updated)
    return to_google_calendar_status_response(app_settings, saved_connection)


@app.delete("/integrations/google-calendar/disconnect", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_google_calendar(
    current_user: UserContext = Depends(get_current_user),
    reminder_repo: ReminderRepository = Depends(get_repository),
    connection_repo: GoogleCalendarConnectionRepository = Depends(get_google_calendar_connection_repository),
) -> Response:
    now = utc_now()
    connection_repo.disconnect_connection(current_user.user_id, now)
    mark_user_google_reminders_needs_attention(reminder_repo, current_user.user_id, now)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@app.get("/push/config", response_model=PushConfigurationResponse)
def get_push_configuration(
    _current_user: UserContext = Depends(get_current_user),
    app_settings: Settings = Depends(get_app_settings),
) -> PushConfigurationResponse:
    return PushConfigurationResponse(configured=app_settings.push_notifications_configured)


@app.get("/push/status", response_model=PushStatusResponse)
def get_push_status(
    current_user: UserContext = Depends(get_current_user),
    preferences_repo: PreferencesRepository = Depends(get_preferences_repository),
    push_repo: PushSubscriptionRepository = Depends(get_push_subscription_repository),
    app_settings: Settings = Depends(get_app_settings),
) -> PushStatusResponse:
    subscriptions = push_repo.list_subscriptions(current_user.user_id)
    preferences = preferences_repo.get_preferences(current_user.user_id) or default_digest_preferences(current_user.user_id, utc_now())
    return to_push_status_response(app_settings, subscriptions, preferences)


@app.post("/push/test", response_model=PushTestResponse)
def send_test_push(
    current_user: UserContext = Depends(get_current_user),
    repo: PushSubscriptionRepository = Depends(get_push_subscription_repository),
    app_settings: Settings = Depends(get_app_settings),
    sender: PushSender = Depends(get_push_sender),
) -> PushTestResponse:
    if not app_settings.push_notifications_configured:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=PUSH_CONFIG_MISSING_DETAIL)

    subscriptions = repo.list_subscriptions(current_user.user_id)
    if not subscriptions:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=NO_ACTIVE_PUSH_SUBSCRIPTION_DETAIL)

    now = utc_now()
    sent = 0

    for subscription in subscriptions:
        try:
            sender.send(subscription, TEST_PUSH_PAYLOAD)
        except PushConfigurationError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=PUSH_CONFIG_MISSING_DETAIL) from exc
        except InvalidPushSubscriptionError:
            repo.save_subscription(
                subscription.model_copy(
                    update={
                        "disabled_at": now,
                        "last_failure_at": now,
                        "failure_count": subscription.failure_count + 1,
                        "updated_at": now,
                    }
                )
            )
        except (PushSendError, Exception):
            repo.save_subscription(
                subscription.model_copy(
                    update={
                        "last_failure_at": now,
                        "failure_count": subscription.failure_count + 1,
                        "updated_at": now,
                    }
                )
            )
        else:
            sent += 1
            repo.save_subscription(
                subscription.model_copy(
                    update={
                        "last_success_at": now,
                        "failure_count": 0,
                        "updated_at": now,
                    }
                )
            )

    if sent == 0:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to send test push.")

    return PushTestResponse(sent=sent)


@app.get("/push/subscriptions", response_model=list[PushSubscriptionResponse])
def list_push_subscriptions(
    current_user: UserContext = Depends(get_current_user),
    repo: PushSubscriptionRepository = Depends(get_push_subscription_repository),
) -> list[PushSubscriptionResponse]:
    return [to_push_subscription_response(subscription) for subscription in repo.list_subscriptions(current_user.user_id)]


@app.post("/push/subscriptions", response_model=PushSubscriptionResponse)
def save_push_subscription(
    payload: PushSubscriptionCreate,
    current_user: UserContext = Depends(get_current_user),
    repo: PushSubscriptionRepository = Depends(get_push_subscription_repository),
) -> PushSubscriptionResponse:
    now = utc_now()
    existing = repo.get_subscription_by_endpoint(current_user.user_id, payload.endpoint)
    subscription = PushSubscription(
        user_id=current_user.user_id,
        subscription_id=existing.subscription_id if existing else push_subscription_id_for_endpoint(payload.endpoint),
        endpoint=payload.endpoint,
        p256dh=payload.keys.p256dh,
        auth=payload.keys.auth,
        user_agent=payload.user_agent,
        created_at=existing.created_at if existing else now,
        updated_at=now,
        disabled_at=None,
        last_success_at=existing.last_success_at if existing else None,
        last_failure_at=None,
        failure_count=0,
    )

    return to_push_subscription_response(repo.save_subscription(subscription))


@app.delete("/push/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_push_subscription(
    subscription_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: PushSubscriptionRepository = Depends(get_push_subscription_repository),
) -> Response:
    disabled = repo.disable_subscription(current_user.user_id, subscription_id, utc_now())
    if not disabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Push subscription not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)

@app.post("/reminders/{reminder_id}/alert/dismiss", response_model=ReminderResponse)
def dismiss_reminder_alert(
    reminder_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> ReminderResponse:
    reminder = require_reminder(repo, current_user.user_id, reminder_id)
    now = utc_now()
    updated = reminder.model_copy(update={**dismiss_alert_state(now), "updated_at": now})

    saved = repo.update_reminder(updated)
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.REMINDER, saved.id, "reminder_update")
    return to_response(saved)


@app.post("/reminders/{reminder_id}/alert/snooze", response_model=ReminderResponse)
def snooze_reminder_alert(
    reminder_id: str,
    payload: AlertSnoozeRequest | None = Body(default=None),
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> ReminderResponse:
    reminder = require_reminder(repo, current_user.user_id, reminder_id)
    now = utc_now()
    snoozed_until = normalize_alert_datetime(payload.snoozed_until) if payload and payload.snoozed_until else None
    if snoozed_until is not None and snoozed_until <= now:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Snooze time must be in the future")

    resolved_snooze = snooze_alert_state(now, snoozed_until)["snoozed_until"]
    updated = reminder.model_copy(
        update={
            **snooze_alert_state(now, snoozed_until),
            "updated_at": now,
            "lifecycle_events": append_lifecycle_event(
                reminder,
                event_type=ReminderLifecycleEventType.SNOOZED,
                occurred_at=now,
                summary=f"Snoozed until {resolved_snooze.date().isoformat()}.",
                previous_due_date=reminder.due_date,
                new_due_date=reminder.due_date,
                snoozed_until=resolved_snooze,
            ),
        }
    )
    saved = repo.update_reminder(updated)
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.REMINDER, saved.id, "reminder_update")
    return to_response(saved)


@app.post("/reminders/{reminder_id}/calendar-sync/enable", response_model=ReminderResponse)
def enable_reminder_calendar_sync(
    reminder_id: str,
    current_user: UserContext = Depends(get_current_user),
    reminder_repo: ReminderRepository = Depends(get_repository),
    connection_repo: GoogleCalendarConnectionRepository = Depends(get_google_calendar_connection_repository),
    app_settings: Settings = Depends(get_app_settings),
    calendar_service: GoogleCalendarService = Depends(get_google_calendar_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> ReminderResponse:
    reminder = require_reminder(reminder_repo, current_user.user_id, reminder_id)
    now = utc_now()
    connection = require_ready_google_connection(connection_repo, current_user.user_id, app_settings, calendar_service, now)

    try:
        event_id = calendar_service.create_event(
            connection,
            build_google_calendar_event(reminder, get_computed_label(reminder)),
        )
    except GoogleCalendarAuthError as exc:
        mark_google_connection_needs_reconnect(connection_repo, connection, now, exc.safe_message)
        save_calendar_sync_error(reminder_repo, reminder, now, exc.safe_message, CalendarSyncStatus.NEEDS_ATTENTION)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.safe_message) from exc
    except GoogleCalendarError as exc:
        save_calendar_sync_error(reminder_repo, reminder, now, exc.safe_message, CalendarSyncStatus.ERROR)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.safe_message) from exc

    synced = reminder.model_copy(
        update={
            "calendar_sync_enabled": True,
            "calendar_provider": "google_calendar",
            "calendar_id": connection.calendar_id,
            "calendar_event_id": event_id,
            "calendar_last_synced_at": now,
            "calendar_sync_status": CalendarSyncStatus.SYNCED,
            "calendar_sync_error": None,
            "updated_at": now,
        }
    )
    saved = reminder_repo.update_reminder(synced)
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.REMINDER, saved.id, "reminder_calendar_sync")
    return to_response(saved)


@app.post("/reminders/{reminder_id}/calendar-sync/disable", response_model=ReminderResponse)
def disable_reminder_calendar_sync(
    reminder_id: str,
    current_user: UserContext = Depends(get_current_user),
    reminder_repo: ReminderRepository = Depends(get_repository),
    connection_repo: GoogleCalendarConnectionRepository = Depends(get_google_calendar_connection_repository),
    app_settings: Settings = Depends(get_app_settings),
    calendar_service: GoogleCalendarService = Depends(get_google_calendar_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> ReminderResponse:
    reminder = require_reminder(reminder_repo, current_user.user_id, reminder_id)
    now = utc_now()
    if not reminder.calendar_sync_enabled and not reminder.calendar_event_id:
        saved = reminder_repo.update_reminder(clear_calendar_sync_metadata(reminder, now))
        sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.REMINDER, saved.id, "reminder_calendar_sync")
        return to_response(saved)

    if reminder.calendar_event_id:
        connection = require_ready_google_connection(connection_repo, current_user.user_id, app_settings, calendar_service, now)
        target_connection = with_google_calendar_id(connection, reminder.calendar_id)
        try:
            calendar_service.delete_event(target_connection, reminder.calendar_event_id)
        except GoogleCalendarNotFoundError:
            pass
        except GoogleCalendarAuthError as exc:
            mark_google_connection_needs_reconnect(connection_repo, connection, now, exc.safe_message)
            save_calendar_sync_error(reminder_repo, reminder, now, exc.safe_message, CalendarSyncStatus.NEEDS_ATTENTION)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.safe_message) from exc
        except GoogleCalendarError as exc:
            save_calendar_sync_error(reminder_repo, reminder, now, exc.safe_message, CalendarSyncStatus.ERROR)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.safe_message) from exc

    saved = reminder_repo.update_reminder(clear_calendar_sync_metadata(reminder, now))
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.REMINDER, saved.id, "reminder_calendar_sync")
    return to_response(saved)


@app.post("/reminders", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
def create_reminder(
    payload: ReminderCreate,
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> ReminderResponse:
    now = utc_now()
    reminder_fields = prepare_create_fields(payload)
    reminder = Reminder(
        id=str(uuid4()),
        user_id=current_user.user_id,
        **reminder_fields,
        completed=False,
        created_at=now,
        updated_at=now,
        completed_at=None,
    )
    reminder = reminder.model_copy(
        update={
            "lifecycle_events": append_lifecycle_event(
                reminder,
                event_type=ReminderLifecycleEventType.CREATED,
                occurred_at=now,
                summary="Reminder created.",
                new_due_date=reminder.due_date,
            )
        }
    )

    saved = repo.create_reminder(reminder)
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.REMINDER, saved.id, "reminder_create")
    return to_response(saved)


@app.get("/reminders/{reminder_id}", response_model=ReminderResponse)
def get_reminder(
    reminder_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
    record_repo: RecordRepository = Depends(get_record_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
) -> ReminderResponse:
    reminder = require_reminder(repo, current_user.user_id, reminder_id)
    return to_response(
        reminder,
        linked_records=get_reminder_linked_record_summaries(
            current_user.user_id,
            reminder.id,
            linked_repo,
            record_repo,
        ),
    )


@app.get("/reminders/{reminder_id}/links", response_model=LinkedItemsResponse)
def list_reminder_links(
    reminder_id: str,
    current_user: UserContext = Depends(get_current_user),
    reminder_repo: ReminderRepository = Depends(get_repository),
    record_repo: RecordRepository = Depends(get_record_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
) -> LinkedItemsResponse:
    require_reminder(reminder_repo, current_user.user_id, reminder_id)
    return get_entity_neighborhood(
        current_user.user_id,
        LinkedEntityType.REMINDER,
        reminder_id,
        linked_repo,
        record_repo,
        reminder_repo,
        attachment_repo,
        include_reminders=False,
    )


@app.delete("/reminders/{reminder_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_reminder_link(
    reminder_id: str,
    link_id: str,
    current_user: UserContext = Depends(get_current_user),
    reminder_repo: ReminderRepository = Depends(get_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> Response:
    require_reminder(reminder_repo, current_user.user_id, reminder_id)
    link = require_link_for_entity(current_user.user_id, link_id, LinkedEntityType.REMINDER, reminder_id, linked_repo)
    linked_repo.delete_link(current_user.user_id, link_id)
    log_security_event(
        "linked_item_removed",
        user_id=current_user.user_id,
        source_type=link.source_type.value,
        source_id=link.source_id,
        target_type=link.target_type.value,
        target_id=link.target_id,
        relationship_type=link.relationship_type.value,
        result="removed",
    )
    sync_search_entity_safe(search_service, current_user.user_id, link.source_type, link.source_id, "relationship_delete")
    sync_search_entity_safe(search_service, current_user.user_id, link.target_type, link.target_id, "relationship_delete")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.put("/reminders/{reminder_id}", response_model=ReminderResponse)
def update_reminder(
    reminder_id: str,
    payload: ReminderUpdate,
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
    connection_repo: GoogleCalendarConnectionRepository = Depends(get_google_calendar_connection_repository),
    app_settings: Settings = Depends(get_app_settings),
    calendar_service: GoogleCalendarService = Depends(get_google_calendar_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> ReminderResponse:
    reminder = require_reminder(repo, current_user.user_id, reminder_id)
    updates = payload.model_dump(exclude_unset=True)
    prepared_updates = prepare_update_fields(reminder, updates)
    now = utc_now()
    previous_due_date = reminder.due_date
    next_due_date = prepared_updates.get("due_date", reminder.due_date)
    date_changed = next_due_date != previous_due_date

    if date_changed:
        prepared_updates["snoozed_until"] = None
        prepared_updates["alert_snoozed_until"] = None

    if prepared_updates:
        event_type = ReminderLifecycleEventType.DATE_CHANGED if date_changed else ReminderLifecycleEventType.EDITED
        summary = (
            f"Important date changed from {previous_due_date.isoformat()} to {next_due_date.isoformat()}."
            if date_changed
            else "Reminder edited."
        )
        prepared_updates["lifecycle_events"] = append_lifecycle_event(
            reminder,
            event_type=event_type,
            occurred_at=now,
            summary=summary,
            previous_due_date=previous_due_date,
            new_due_date=next_due_date,
        )

    updated = Reminder.model_validate({**reminder.model_dump(), **prepared_updates, "updated_at": now})
    saved = repo.update_reminder(updated)
    synced = sync_existing_calendar_event_after_change(
        repo,
        connection_repo,
        app_settings,
        calendar_service,
        saved,
        now,
    )
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.REMINDER, synced.id, "reminder_update")
    return to_response(synced)


@app.delete("/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(
    reminder_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    connection_repo: GoogleCalendarConnectionRepository = Depends(get_google_calendar_connection_repository),
    app_settings: Settings = Depends(get_app_settings),
    calendar_service: GoogleCalendarService = Depends(get_google_calendar_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> Response:
    reminder = require_reminder(repo, current_user.user_id, reminder_id)
    cleanup_calendar_event_before_delete(
        repo,
        connection_repo,
        app_settings,
        calendar_service,
        reminder,
        utc_now(),
    )
    deleted_links = linked_repo.list_links_for_entity(current_user.user_id, LinkedEntityType.REMINDER, reminder_id)
    linked_repo.delete_links_for_entity(current_user.user_id, LinkedEntityType.REMINDER, reminder_id)
    deleted = repo.delete_reminder(current_user.user_id, reminder_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")

    sync_linked_search_neighbors_safe(
        search_service,
        current_user.user_id,
        deleted_links,
        "reminder_delete_relationship_cleanup",
        excluded_entities={(LinkedEntityType.REMINDER, reminder_id)},
    )
    delete_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.REMINDER, reminder_id, "reminder_delete")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/reminders/{reminder_id}/snooze/clear", response_model=ReminderResponse)
def clear_reminder_snooze(
    reminder_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> ReminderResponse:
    reminder = require_reminder(repo, current_user.user_id, reminder_id)
    now = utc_now()
    had_snooze = reminder.snoozed_until is not None or reminder.alert_snoozed_until is not None
    updates: dict[str, object] = {
        "snoozed_until": None,
        "alert_snoozed_until": None,
        "alert_last_action_at": now,
        "updated_at": now,
    }
    if had_snooze:
        updates["lifecycle_events"] = append_lifecycle_event(
            reminder,
            event_type=ReminderLifecycleEventType.SNOOZE_CLEARED,
            occurred_at=now,
            summary="Snooze cleared.",
            previous_due_date=reminder.due_date,
            new_due_date=reminder.due_date,
        )

    saved = repo.update_reminder(reminder.model_copy(update=updates))
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.REMINDER, saved.id, "reminder_update")
    return to_response(saved)


@app.post("/reminders/{reminder_id}/snooze", response_model=ReminderResponse)
def snooze_reminder(
    reminder_id: str,
    payload: ReminderSnoozeRequest,
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> ReminderResponse:
    reminder = require_reminder(repo, current_user.user_id, reminder_id)
    if reminder.completed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Completed reminders cannot be snoozed.")
    if reminder.archived_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived reminders cannot be snoozed.")

    now = utc_now()
    snoozed_until = normalize_alert_datetime(payload.snoozed_until)
    if snoozed_until <= now:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose a future snooze time.")

    updated = reminder.model_copy(
        update={
            **snooze_alert_state(now, snoozed_until),
            "updated_at": now,
            "lifecycle_events": append_lifecycle_event(
                reminder,
                event_type=ReminderLifecycleEventType.SNOOZED,
                occurred_at=now,
                summary=f"Snoozed until {snoozed_until.date().isoformat()}.",
                previous_due_date=reminder.due_date,
                new_due_date=reminder.due_date,
                snoozed_until=snoozed_until,
            ),
        }
    )
    saved = repo.update_reminder(updated)
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.REMINDER, saved.id, "reminder_update")
    return to_response(saved)


@app.post("/reminders/{reminder_id}/renew", response_model=ReminderResponse)
def renew_reminder(
    reminder_id: str,
    payload: ReminderRenewRequest,
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
    record_repo: RecordRepository = Depends(get_record_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    connection_repo: GoogleCalendarConnectionRepository = Depends(get_google_calendar_connection_repository),
    app_settings: Settings = Depends(get_app_settings),
    calendar_service: GoogleCalendarService = Depends(get_google_calendar_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> ReminderResponse:
    reminder = require_reminder(repo, current_user.user_id, reminder_id)
    if reminder.archived_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived reminders cannot be renewed.")
    if not is_renewable_reminder(reminder):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This reminder does not support renewal.")

    now = utc_now()
    if payload.new_due_date < now.date():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose today or a future renewal date.")
    if has_recent_lifecycle_action(reminder, ReminderLifecycleEventType.RENEWED, now):
        return to_response(reminder)

    previous_due_date = reminder.due_date
    renewal_details = renewal_details_for_new_date(reminder, payload.new_due_date)
    maintenance_details = maintenance_details_for_new_date(reminder, payload.new_due_date, now.date())
    updated = reminder.model_copy(
        update={
            **clear_alert_action_state(now),
            "completed": False,
            "completed_at": now,
            "due_date": payload.new_due_date,
            "renewal_details": renewal_details,
            "maintenance_details": maintenance_details,
            "updated_at": now,
            "lifecycle_events": append_lifecycle_event(
                reminder,
                event_type=ReminderLifecycleEventType.RENEWED,
                occurred_at=now,
                summary=f"Renewed from {previous_due_date.isoformat()} to {payload.new_due_date.isoformat()}.",
                previous_due_date=previous_due_date,
                new_due_date=payload.new_due_date,
            ),
        }
    )
    saved = repo.update_reminder(updated)
    update_linked_record_dates(current_user.user_id, reminder.id, previous_due_date, payload.new_due_date, now, linked_repo, record_repo)
    synced = sync_existing_calendar_event_after_change(
        repo,
        connection_repo,
        app_settings,
        calendar_service,
        saved,
        now,
    )
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.REMINDER, synced.id, "reminder_update")
    return to_response(synced)


@app.post("/reminders/{reminder_id}/complete", response_model=ReminderResponse)
def complete_reminder(
    reminder_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
    connection_repo: GoogleCalendarConnectionRepository = Depends(get_google_calendar_connection_repository),
    app_settings: Settings = Depends(get_app_settings),
    calendar_service: GoogleCalendarService = Depends(get_google_calendar_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> ReminderResponse:
    reminder = require_reminder(repo, current_user.user_id, reminder_id)
    now = utc_now()
    if reminder.archived_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived reminders cannot be completed.")
    if reminder.completed:
        return to_response(reminder)
    if has_recent_lifecycle_action(reminder, ReminderLifecycleEventType.COMPLETED, now):
        return to_response(reminder)

    alert_updates = clear_alert_action_state(now)

    if (
        reminder.reminder_type == ReminderType.MAINTENANCE
        and reminder.maintenance_details is not None
        and reminder.maintenance_details.interval_value is not None
        and reminder.maintenance_details.interval_unit is not None
    ):
        maintenance_details = advance_maintenance_details(reminder.maintenance_details, now.date())
        next_due_date = get_maintenance_due_date(maintenance_details)
        if next_due_date is not None:
            advanced_reminder = reminder.model_copy(
                update={
                    **alert_updates,
                    "completed": False,
                    "completed_at": now,
                    "due_date": next_due_date,
                    "maintenance_details": maintenance_details,
                    "updated_at": now,
                    "lifecycle_events": append_lifecycle_event(
                        reminder,
                        event_type=ReminderLifecycleEventType.COMPLETED,
                        occurred_at=now,
                        summary=f"Completed maintenance; next due {next_due_date.isoformat()}.",
                        previous_due_date=reminder.due_date,
                        new_due_date=next_due_date,
                    ),
                }
            )
            saved = repo.update_reminder(advanced_reminder)
            synced = sync_existing_calendar_event_after_change(
                repo,
                connection_repo,
                app_settings,
                calendar_service,
                saved,
                now,
            )
            sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.REMINDER, synced.id, "reminder_update")
            return to_response(synced)

    if reminder.repeat == RepeatOption.NONE:
        completed_reminder = reminder.model_copy(
            update={
                **alert_updates,
                "completed": True,
                "completed_at": now,
                "updated_at": now,
                "lifecycle_events": append_lifecycle_event(
                    reminder,
                    event_type=ReminderLifecycleEventType.COMPLETED,
                    occurred_at=now,
                    summary="Reminder completed.",
                    previous_due_date=reminder.due_date,
                    new_due_date=reminder.due_date,
                ),
            }
        )
        saved = repo.update_reminder(completed_reminder)
        sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.REMINDER, saved.id, "reminder_complete")
        return to_response(saved)

    next_due_date = advance_due_date(reminder.due_date, reminder.repeat, today=now.date())
    birthday_details = reminder.birthday_details
    renewal_details = reminder.renewal_details
    maintenance_details = reminder.maintenance_details
    if reminder.reminder_type == ReminderType.BIRTHDAY and birthday_details is not None:
        birthday_details = enrich_birthday_details(birthday_details, next_due_date)
    if reminder.reminder_type == ReminderType.RENEWAL and renewal_details is not None:
        renewal_details = advance_renewal_details(renewal_details, reminder.due_date, next_due_date)

    advanced_reminder = reminder.model_copy(
        update={
            **alert_updates,
            "completed": False,
            "completed_at": now,
            "due_date": next_due_date,
            "birthday_details": birthday_details,
            "renewal_details": renewal_details,
            "maintenance_details": maintenance_details,
            "updated_at": now,
            "lifecycle_events": append_lifecycle_event(
                reminder,
                event_type=ReminderLifecycleEventType.COMPLETED,
                occurred_at=now,
                summary=f"Completed recurring reminder; next due {next_due_date.isoformat()}.",
                previous_due_date=reminder.due_date,
                new_due_date=next_due_date,
            ),
        }
    )
    saved = repo.update_reminder(advanced_reminder)
    synced = sync_existing_calendar_event_after_change(
        repo,
        connection_repo,
        app_settings,
        calendar_service,
        saved,
        now,
    )
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.REMINDER, synced.id, "reminder_update")
    return to_response(synced)


def is_renewable_reminder(reminder: Reminder) -> bool:
    return reminder.reminder_type in {ReminderType.RENEWAL, ReminderType.MAINTENANCE} or reminder.repeat != RepeatOption.NONE


def renewal_details_for_new_date(reminder: Reminder, new_due_date: date) -> RenewalDetails | None:
    details = reminder.renewal_details
    if reminder.reminder_type != ReminderType.RENEWAL or details is None:
        return details

    data = details.model_dump()
    if str(details.renewal_kind) == "RenewalKind.EXPIRATION" or getattr(details.renewal_kind, "value", None) == "expiration":
        data["expiration_date"] = new_due_date
    else:
        data["renewal_date"] = new_due_date
    return RenewalDetails.model_validate(data)


def maintenance_details_for_new_date(reminder: Reminder, new_due_date: date, completed_on: date) -> MaintenanceDetails | None:
    details = reminder.maintenance_details
    if reminder.reminder_type != ReminderType.MAINTENANCE or details is None:
        return details

    data = details.model_dump()
    data["last_completed_date"] = completed_on
    data["next_due_date"] = new_due_date
    return MaintenanceDetails.model_validate(data)


def update_linked_record_dates(
    user_id: str,
    reminder_id: str,
    previous_due_date: date,
    new_due_date: date,
    now: datetime,
    linked_repo: LinkedItemRepository,
    record_repo: RecordRepository,
) -> None:
    for summary in get_reminder_linked_record_summaries(user_id, reminder_id, linked_repo, record_repo):
        record = record_repo.get_record(user_id, summary.id)
        if record is None or record.status == RecordStatus.ARCHIVED:
            continue

        updates: dict[str, object] = {}
        if record.renewal_date == previous_due_date:
            updates["renewal_date"] = new_due_date
        if record.expiration_date == previous_due_date:
            updates["expiration_date"] = new_due_date

        if not updates:
            continue

        try:
            record_repo.update_record(record.model_copy(update={**updates, "updated_at": now}))
        except Exception:
            logger.exception("Failed to update linked record dates for renewed reminder", extra={"reminder_id": reminder_id})

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
def to_response(
    reminder: Reminder,
    *,
    linked_records: list[ReminderLinkedRecordSummary] | None = None,
) -> ReminderResponse:
    now = utc_now()
    return ReminderResponse.model_validate(
        {
            **reminder.model_dump(),
            "status": calculate_status(reminder, now=now),
            "effective_attention_date": get_effective_attention_date(reminder, now=now),
            "linked_records": linked_records or [],
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
        service.sync_entity(user_id, entity_type, entity_id)
        logger.info(
            "search_projection_sync",
            extra={
                "operation": operation,
                "source_item_type": entity_type.value,
                "projection_update_result": "success",
            },
        )
    except Exception:
        logger.exception(
            "search_projection_sync_failed",
            extra={
                "operation": operation,
                "source_item_type": entity_type.value,
                "projection_update_result": "failure",
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
        if entity_type == LinkedEntityType.RECORD:
            service.delete_record(user_id, entity_id)
        elif entity_type == LinkedEntityType.REMINDER:
            service.delete_reminder(user_id, entity_id)
        elif entity_type == LinkedEntityType.DOCUMENT:
            parsed = entity_id.split("#", 1)
            if len(parsed) == 2:
                service.delete_document(user_id, parsed[0], parsed[1])
        logger.info(
            "search_projection_delete",
            extra={
                "operation": operation,
                "source_item_type": entity_type.value,
                "projection_update_result": "success",
            },
        )
    except Exception:
        logger.exception(
            "search_projection_delete_failed",
            extra={
                "operation": operation,
                "source_item_type": entity_type.value,
                "projection_update_result": "failure",
            },
        )

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










