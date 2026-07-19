from fastapi import APIRouter

from app.route_support import *  # noqa: F403

router = APIRouter(tags=["lifecycle"])
lifecycle_router = router

@lifecycle_router.get("/records/{record_id}/activity", response_model=ResponsibilityHistoryPage)
def get_record_activity(
    record_id: str,
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None),
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    history_repo: ResponsibilityHistoryRepository = Depends(get_responsibility_history_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
) -> ResponsibilityHistoryPage:
    require_record(record_repo, current_user.user_id, record_id)
    try:
        events, next_cursor = history_repo.list_for_item(
            current_user.user_id,
            record_id,
            limit=limit,
            cursor=cursor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ResponsibilityHistoryPage(
        items=[to_responsibility_event_response(event, attachment_repo) for event in events],
        next_cursor=next_cursor,
    )

@lifecycle_router.get("/reminders/{reminder_id}/history", response_model=ResponsibilityHistoryPage)
def get_reminder_history(
    reminder_id: str,
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None),
    current_user: UserContext = Depends(get_current_user),
    reminder_repo: ReminderRepository = Depends(get_repository),
    history_repo: ResponsibilityHistoryRepository = Depends(get_responsibility_history_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
) -> ResponsibilityHistoryPage:
    require_reminder(reminder_repo, current_user.user_id, reminder_id)
    try:
        events, next_cursor = history_repo.list_for_reminder(
            current_user.user_id,
            reminder_id,
            limit=limit,
            cursor=cursor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ResponsibilityHistoryPage(
        items=[to_responsibility_event_response(event, attachment_repo) for event in events],
        next_cursor=next_cursor,
    )

@lifecycle_router.post("/reminders/{reminder_id}/history/evidence", response_model=ResponsibilityEventResponse, status_code=status.HTTP_201_CREATED)
def add_reminder_history_evidence(
    reminder_id: str,
    payload: ResponsibilityEvidenceRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: UserContext = Depends(get_current_user),
    reminder_repo: ReminderRepository = Depends(get_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    lifecycle_service: ResponsibilityLifecycleService = Depends(get_responsibility_lifecycle_service),
) -> ResponsibilityEventResponse:
    reminder = require_reminder(reminder_repo, current_user.user_id, reminder_id)
    try:
        event = lifecycle_service.attach_evidence(
            current_user.user_id,
            reminder,
            payload,
            idempotency_key=normalize_idempotency_key(idempotency_key),
            now=utc_now(),
        )
    except LifecycleWriteConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return to_responsibility_event_response(event, attachment_repo)

@lifecycle_router.post("/reminders/{reminder_id}/history/reconcile", response_model=LifecycleReconciliationResult)
def reconcile_reminder_history(
    reminder_id: str,
    dry_run: bool = Query(default=False),
    current_user: UserContext = Depends(get_current_user),
    reminder_repo: ReminderRepository = Depends(get_repository),
    lifecycle_service: ResponsibilityLifecycleService = Depends(get_responsibility_lifecycle_service),
) -> LifecycleReconciliationResult:
    reminder = require_reminder(reminder_repo, current_user.user_id, reminder_id)
    return lifecycle_service.reconcile_reminder(current_user.user_id, reminder, dry_run=dry_run)

@lifecycle_router.post("/responsibility-history/reconcile", response_model=LifecycleReconciliationPage)
def reconcile_user_responsibility_history(
    dry_run: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None),
    current_user: UserContext = Depends(get_current_user),
    reminder_repo: ReminderRepository = Depends(get_repository),
    lifecycle_service: ResponsibilityLifecycleService = Depends(get_responsibility_lifecycle_service),
) -> LifecycleReconciliationPage:
    try:
        marker = decode_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    reminders = sorted(reminder_repo.list_reminders(current_user.user_id), key=lambda reminder: reminder.id)
    if marker:
        reminders = [reminder for reminder in reminders if reminder.id > marker]
    page = reminders[:limit]
    next_cursor = encode_cursor(page[-1].id) if len(reminders) > limit and page else None
    return LifecycleReconciliationPage(
        items=[
            lifecycle_service.reconcile_reminder(current_user.user_id, reminder, dry_run=dry_run)
            for reminder in page
        ],
        next_cursor=next_cursor,
    )

@lifecycle_router.get("/responsibility-events/{event_id}", response_model=ResponsibilityEventResponse)
def get_responsibility_event(
    event_id: str,
    current_user: UserContext = Depends(get_current_user),
    history_repo: ResponsibilityHistoryRepository = Depends(get_responsibility_history_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
) -> ResponsibilityEventResponse:
    event = history_repo.get_event(current_user.user_id, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History entry not found")
    return to_responsibility_event_response(event, attachment_repo)

@lifecycle_router.post("/reminders/{reminder_id}/renew", response_model=ReminderResponse)
def renew_reminder(
    reminder_id: str,
    payload: ReminderRenewRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
    connection_repo: GoogleCalendarConnectionRepository = Depends(get_google_calendar_connection_repository),
    app_settings: Settings = Depends(get_app_settings),
    calendar_service: GoogleCalendarService = Depends(get_google_calendar_service),
    lifecycle_service: ResponsibilityLifecycleService = Depends(get_responsibility_lifecycle_service),
) -> ReminderResponse:
    reminder = require_reminder(repo, current_user.user_id, reminder_id)
    if reminder.archived_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived reminders cannot be renewed.")
    if not is_renewable_reminder(reminder):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This reminder does not support renewal.")

    now = utc_now()
    local_today = date.today()
    if payload.new_due_date < local_today:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose today or a future renewal date.")
    if payload.renewed_on and payload.renewed_on > local_today:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Renewal date cannot be in the future.")
    if payload.renewed_on and payload.new_due_date < payload.renewed_on:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="New due date cannot be before the renewal date.")
    try:
        result = lifecycle_service.renew(
            current_user.user_id,
            reminder,
            payload,
            idempotency_key=normalize_idempotency_key(idempotency_key),
            now=now,
        )
    except LifecycleWriteConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    synced = sync_existing_calendar_event_after_change(
        repo,
        connection_repo,
        app_settings,
        calendar_service,
        result.reminder,
        now,
    )
    return to_response(synced, lifecycle_reconciliation_status=result.reconciliation_status, last_lifecycle_event_id=result.event.event_id)

@lifecycle_router.post("/reminders/{reminder_id}/complete", response_model=ReminderResponse)
def complete_reminder(
    reminder_id: str,
    payload: ReminderCompleteRequest | None = Body(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
    connection_repo: GoogleCalendarConnectionRepository = Depends(get_google_calendar_connection_repository),
    app_settings: Settings = Depends(get_app_settings),
    calendar_service: GoogleCalendarService = Depends(get_google_calendar_service),
    lifecycle_service: ResponsibilityLifecycleService = Depends(get_responsibility_lifecycle_service),
) -> ReminderResponse:
    reminder = require_reminder(repo, current_user.user_id, reminder_id)
    now = utc_now()
    local_today = date.today()
    if reminder.archived_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived reminders cannot be completed.")
    if reminder.completed:
        return to_response(reminder)
    if payload and payload.completed_on and payload.completed_on > local_today:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Completion date cannot be in the future.")
    try:
        result = lifecycle_service.complete(
            current_user.user_id,
            reminder,
            payload or ReminderCompleteRequest(),
            idempotency_key=normalize_idempotency_key(idempotency_key),
            now=now,
        )
    except LifecycleWriteConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    synced = sync_existing_calendar_event_after_change(
        repo,
        connection_repo,
        app_settings,
        calendar_service,
        result.reminder,
        now,
    )
    return to_response(synced, lifecycle_reconciliation_status=result.reconciliation_status, last_lifecycle_event_id=result.event.event_id)

@lifecycle_router.post("/reminders/{reminder_id}/reopen", response_model=ReminderResponse)
def reopen_reminder(
    reminder_id: str,
    occurrence_id: str | None = Query(default=None, max_length=120),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
    lifecycle_service: ResponsibilityLifecycleService = Depends(get_responsibility_lifecycle_service),
) -> ReminderResponse:
    reminder = require_reminder(repo, current_user.user_id, reminder_id)
    if reminder.archived_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived reminders cannot be reopened.")
    try:
        result = lifecycle_service.reopen(
            current_user.user_id,
            reminder,
            occurrence_id=occurrence_id,
            idempotency_key=normalize_idempotency_key(idempotency_key),
            now=utc_now(),
        )
    except LifecycleWriteConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return to_response(result.reminder, lifecycle_reconciliation_status=result.reconciliation_status, last_lifecycle_event_id=result.event.event_id)
