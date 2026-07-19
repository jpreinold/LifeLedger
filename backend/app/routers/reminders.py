from fastapi import APIRouter

from app.route_support import *  # noqa: F403

router = APIRouter(tags=["reminders"])
reminders_router = router

@reminders_router.get("/reminders", response_model=list[ReminderResponse])
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

@reminders_router.get("/alerts", response_model=list[ReminderAlertResponse])
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

@reminders_router.post("/reminders/{reminder_id}/alert/dismiss", response_model=ReminderResponse)
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

@reminders_router.post("/reminders/{reminder_id}/alert/snooze", response_model=ReminderResponse)
def snooze_reminder_alert(
    reminder_id: str,
    payload: AlertSnoozeRequest | None = Body(default=None),
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
    lifecycle_service: ResponsibilityLifecycleService = Depends(get_responsibility_lifecycle_service),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ReminderResponse:
    reminder = require_reminder(repo, current_user.user_id, reminder_id)
    now = utc_now()
    snoozed_until = normalize_alert_datetime(payload.snoozed_until) if payload and payload.snoozed_until else None
    if snoozed_until is not None and snoozed_until <= now:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Snooze time must be in the future")

    resolved_snooze = snooze_alert_state(now, snoozed_until)["snoozed_until"]
    try:
        result = lifecycle_service.snooze(
            current_user.user_id,
            reminder,
            resolved_snooze,
            idempotency_key=normalize_idempotency_key(idempotency_key),
            now=now,
        )
    except LifecycleWriteConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return to_response(result.reminder, lifecycle_reconciliation_status=result.reconciliation_status, last_lifecycle_event_id=result.event.event_id)

@reminders_router.post("/reminders", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
def create_reminder(
    payload: ReminderCreate,
    item_id: str | None = Query(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
    lifecycle_service: ResponsibilityLifecycleService = Depends(get_responsibility_lifecycle_service),
) -> ReminderResponse:
    normalized_key = normalize_idempotency_key(idempotency_key)
    reminder_id = (
        str(uuid5(NAMESPACE_URL, f"lifeledger:reminder:{current_user.user_id}:{normalized_key}"))
        if normalized_key
        else str(uuid4())
    )
    existing = repo.get_reminder(current_user.user_id, reminder_id)
    if existing is not None:
        return to_response(existing)

    now = utc_now()
    reminder_fields = prepare_create_fields(payload)
    reminder = Reminder(
        id=reminder_id,
        user_id=current_user.user_id,
        **reminder_fields,
        completed=False,
        created_at=now,
        updated_at=now,
        completed_at=None,
    )
    try:
        result = lifecycle_service.create_responsibility(
            reminder,
            item_id=item_id,
            idempotency_key=normalized_key,
            now=now,
        )
    except LifecycleWriteConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return to_response(result.reminder, lifecycle_reconciliation_status=result.reconciliation_status, last_lifecycle_event_id=result.event.event_id)

@reminders_router.get("/reminders/{reminder_id}", response_model=ReminderResponse)
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

@reminders_router.put("/reminders/{reminder_id}", response_model=ReminderResponse)
def update_reminder(
    reminder_id: str,
    payload: ReminderUpdate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
    connection_repo: GoogleCalendarConnectionRepository = Depends(get_google_calendar_connection_repository),
    app_settings: Settings = Depends(get_app_settings),
    calendar_service: GoogleCalendarService = Depends(get_google_calendar_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
    lifecycle_service: ResponsibilityLifecycleService = Depends(get_responsibility_lifecycle_service),
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

    updated = Reminder.model_validate({**reminder.model_dump(), **prepared_updates, "updated_at": now})
    reconciliation_status: LifecycleReconciliationStatus | None = None
    if date_changed:
        try:
            result = lifecycle_service.change_due_date(
                current_user.user_id,
                reminder,
                updated,
                idempotency_key=normalize_idempotency_key(idempotency_key),
                now=now,
            )
        except LifecycleWriteConflict as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        saved = result.reminder
        reconciliation_status = result.reconciliation_status
    else:
        saved = repo.update_reminder(updated.model_copy(update={"version": reminder.version + 1}))
    synced = sync_existing_calendar_event_after_change(
        repo,
        connection_repo,
        app_settings,
        calendar_service,
        saved,
        now,
    )
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.REMINDER, synced.id, "reminder_update")
    return to_response(synced, lifecycle_reconciliation_status=reconciliation_status)

@reminders_router.delete("/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(
    reminder_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    connection_repo: GoogleCalendarConnectionRepository = Depends(get_google_calendar_connection_repository),
    app_settings: Settings = Depends(get_app_settings),
    calendar_service: GoogleCalendarService = Depends(get_google_calendar_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
    history_repo: ResponsibilityHistoryRepository = Depends(get_responsibility_history_repository),
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
    # Ownership was established above. A concurrent duplicate request may have
    # removed the row after that read, so deletion is idempotent from here and
    # both requests are allowed to finish the remaining user-scoped cleanup.
    repo.delete_reminder(current_user.user_id, reminder_id)
    history_repo.delete_for_reminder(current_user.user_id, reminder_id)

    sync_linked_search_neighbors_safe(
        search_service,
        current_user.user_id,
        deleted_links,
        "reminder_delete_relationship_cleanup",
        excluded_entities={(LinkedEntityType.REMINDER, reminder_id)},
    )
    delete_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.REMINDER, reminder_id, "reminder_delete")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@reminders_router.post("/reminders/{reminder_id}/snooze/clear", response_model=ReminderResponse)
def clear_reminder_snooze(
    reminder_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
    lifecycle_service: ResponsibilityLifecycleService = Depends(get_responsibility_lifecycle_service),
) -> ReminderResponse:
    reminder = require_reminder(repo, current_user.user_id, reminder_id)
    now = utc_now()
    try:
        result = lifecycle_service.clear_snooze(
            current_user.user_id,
            reminder,
            idempotency_key=normalize_idempotency_key(idempotency_key),
            now=now,
        )
    except LifecycleWriteConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if result is None:
        return to_response(reminder)
    return to_response(result.reminder, lifecycle_reconciliation_status=result.reconciliation_status, last_lifecycle_event_id=result.event.event_id)

@reminders_router.post("/reminders/{reminder_id}/snooze", response_model=ReminderResponse)
def snooze_reminder(
    reminder_id: str,
    payload: ReminderSnoozeRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
    lifecycle_service: ResponsibilityLifecycleService = Depends(get_responsibility_lifecycle_service),
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

    try:
        result = lifecycle_service.snooze(
            current_user.user_id,
            reminder,
            snoozed_until,
            idempotency_key=normalize_idempotency_key(idempotency_key),
            now=now,
        )
    except LifecycleWriteConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return to_response(result.reminder, lifecycle_reconciliation_status=result.reconciliation_status, last_lifecycle_event_id=result.event.event_id)
