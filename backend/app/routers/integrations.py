from fastapi import APIRouter

from app.route_support import *  # noqa: F403

router = APIRouter(tags=["integrations"])
integrations_router = router

@integrations_router.get("/integrations/google-calendar/status", response_model=GoogleCalendarStatusResponse)
def get_google_calendar_status(
    current_user: UserContext = Depends(get_current_user),
    repo: GoogleCalendarConnectionRepository = Depends(get_google_calendar_connection_repository),
    app_settings: Settings = Depends(get_app_settings),
) -> GoogleCalendarStatusResponse:
    connection = repo.get_connection(current_user.user_id)
    return to_google_calendar_status_response(app_settings, connection)

@integrations_router.post("/integrations/google-calendar/connect", response_model=GoogleCalendarConnectResponse)
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

@integrations_router.post("/integrations/google-calendar/callback", response_model=GoogleCalendarStatusResponse)
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

@integrations_router.get("/integrations/google-calendar/calendars", response_model=list[GoogleCalendarOptionResponse])
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

@integrations_router.put("/integrations/google-calendar/calendar", response_model=GoogleCalendarStatusResponse)
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

@integrations_router.delete("/integrations/google-calendar/disconnect", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_google_calendar(
    current_user: UserContext = Depends(get_current_user),
    reminder_repo: ReminderRepository = Depends(get_repository),
    connection_repo: GoogleCalendarConnectionRepository = Depends(get_google_calendar_connection_repository),
) -> Response:
    now = utc_now()
    connection_repo.disconnect_connection(current_user.user_id, now)
    mark_user_google_reminders_needs_attention(reminder_repo, current_user.user_id, now)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@integrations_router.post("/reminders/{reminder_id}/calendar-sync/enable", response_model=ReminderResponse)
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

@integrations_router.post("/reminders/{reminder_id}/calendar-sync/disable", response_model=ReminderResponse)
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
