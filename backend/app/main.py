from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import Body, Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app.alerts import (
    clear_alert_action_state,
    dismiss_alert_state,
    get_alert_eligibility,
    normalize_alert_datetime,
    snooze_alert_state,
    sort_alerts,
)
from app.auth import UserContext, get_current_user
from app.birthdays import (
    enrich_birthday_details,
    get_birthday_age_label,
    get_birthday_computed_label,
    get_next_birthday_due_date,
)
from app.config import get_settings
from app.maintenance import (
    advance_maintenance_details,
    get_maintenance_computed_label,
    get_maintenance_due_date,
    get_maintenance_status_label,
    prepare_maintenance_details,
)
from app.models import PushSubscription, Reminder
from app.preferences import default_digest_preferences
from app.preferences_repository import PreferencesRepository
from app.push_repository import PushSubscriptionRepository, push_subscription_id_for_endpoint
from app.recurrence import advance_due_date, calculate_status, get_next_due_date
from app.renewals import (
    advance_renewal_details,
    get_renewal_computed_label,
    get_renewal_due_date,
    get_renewal_status_label,
    get_renewal_window_label,
)
from app.repository import ReminderRepository
from app.repository_factory import create_preferences_repository, create_push_subscription_repository, create_repository
from app.schemas import (
    AlertSnoozeRequest,
    DigestPreferences,
    DigestPreferencesUpdate,
    MaintenanceDetails,
    PushConfigurationResponse,
    PushSubscriptionCreate,
    PushSubscriptionResponse,
    ReminderCreate,
    ReminderAlertResponse,
    ReminderLeadUnit,
    ReminderResponse,
    ReminderType,
    ReminderUpdate,
    RenewalDetails,
    RepeatOption,
)

settings = get_settings()
app = FastAPI(title="LifeLedger API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins or [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

repository = create_repository()
preferences_repository = create_preferences_repository()
push_subscription_repository = create_push_subscription_repository()


def get_repository() -> ReminderRepository:
    return repository


def get_preferences_repository() -> PreferencesRepository:
    return preferences_repository

def get_push_subscription_repository() -> PushSubscriptionRepository:
    return push_subscription_repository


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/reminders", response_model=list[ReminderResponse])
def list_reminders(
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
) -> list[ReminderResponse]:
    reminders = repo.list_reminders(current_user.user_id)
    sorted_reminders = sorted(reminders, key=lambda item: (item.completed, item.due_date, item.created_at))
    return [to_response(reminder) for reminder in sorted_reminders]


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




@app.get("/push/config", response_model=PushConfigurationResponse)
def get_push_configuration(
    _current_user: UserContext = Depends(get_current_user),
) -> PushConfigurationResponse:
    return PushConfigurationResponse(configured=get_settings().push_notifications_configured)


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
) -> ReminderResponse:
    reminder = require_reminder(repo, current_user.user_id, reminder_id)
    now = utc_now()
    updated = reminder.model_copy(update={**dismiss_alert_state(now), "updated_at": now})

    return to_response(repo.update_reminder(updated))


@app.post("/reminders/{reminder_id}/alert/snooze", response_model=ReminderResponse)
def snooze_reminder_alert(
    reminder_id: str,
    payload: AlertSnoozeRequest | None = Body(default=None),
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
) -> ReminderResponse:
    reminder = require_reminder(repo, current_user.user_id, reminder_id)
    now = utc_now()
    snoozed_until = normalize_alert_datetime(payload.snoozed_until) if payload and payload.snoozed_until else None
    if snoozed_until is not None and snoozed_until <= now:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Snooze time must be in the future")

    updated = reminder.model_copy(update={**snooze_alert_state(now, snoozed_until), "updated_at": now})
    return to_response(repo.update_reminder(updated))


@app.post("/reminders", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
def create_reminder(
    payload: ReminderCreate,
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
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

    return to_response(repo.create_reminder(reminder))


@app.get("/reminders/{reminder_id}", response_model=ReminderResponse)
def get_reminder(
    reminder_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
) -> ReminderResponse:
    return to_response(require_reminder(repo, current_user.user_id, reminder_id))


@app.put("/reminders/{reminder_id}", response_model=ReminderResponse)
def update_reminder(
    reminder_id: str,
    payload: ReminderUpdate,
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
) -> ReminderResponse:
    reminder = require_reminder(repo, current_user.user_id, reminder_id)
    updates = payload.model_dump(exclude_unset=True)
    prepared_updates = prepare_update_fields(reminder, updates)

    updated = Reminder.model_validate({**reminder.model_dump(), **prepared_updates, "updated_at": utc_now()})
    return to_response(repo.update_reminder(updated))


@app.delete("/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(
    reminder_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
) -> Response:
    deleted = repo.delete_reminder(current_user.user_id, reminder_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/reminders/{reminder_id}/complete", response_model=ReminderResponse)
def complete_reminder(
    reminder_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: ReminderRepository = Depends(get_repository),
) -> ReminderResponse:
    reminder = require_reminder(repo, current_user.user_id, reminder_id)
    now = utc_now()
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
                }
            )
            return to_response(repo.update_reminder(advanced_reminder))

    if reminder.repeat == RepeatOption.NONE:
        completed_reminder = reminder.model_copy(
            update={
                **alert_updates,
                "completed": True,
                "completed_at": now,
                "updated_at": now,
            }
        )
        return to_response(repo.update_reminder(completed_reminder))

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
        }
    )
    return to_response(repo.update_reminder(advanced_reminder))


def require_reminder(repo: ReminderRepository, user_id: str, reminder_id: str) -> Reminder:
    reminder = repo.get_reminder(user_id, reminder_id)
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")

    return reminder


def to_response(reminder: Reminder) -> ReminderResponse:
    return ReminderResponse.model_validate(
        {
            **reminder.model_dump(),
            "status": calculate_status(reminder),
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
