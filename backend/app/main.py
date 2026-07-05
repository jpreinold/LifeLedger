from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app.auth import UserContext, get_current_user
from app.birthdays import (
    enrich_birthday_details,
    get_birthday_age_label,
    get_birthday_computed_label,
    get_next_birthday_due_date,
)
from app.config import get_settings
from app.models import Reminder
from app.recurrence import advance_due_date, calculate_status, get_next_due_date
from app.repository import ReminderRepository
from app.repository_factory import create_repository
from app.schemas import ReminderCreate, ReminderLeadUnit, ReminderResponse, ReminderType, ReminderUpdate, RepeatOption

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


def get_repository() -> ReminderRepository:
    return repository


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

    if reminder.repeat == RepeatOption.NONE:
        completed_reminder = reminder.model_copy(
            update={
                "completed": True,
                "completed_at": now,
                "updated_at": now,
            }
        )
        return to_response(repo.update_reminder(completed_reminder))

    next_due_date = advance_due_date(reminder.due_date, reminder.repeat, today=now.date())
    birthday_details = reminder.birthday_details
    if reminder.reminder_type == ReminderType.BIRTHDAY and birthday_details is not None:
        birthday_details = enrich_birthday_details(birthday_details, next_due_date)

    advanced_reminder = reminder.model_copy(
        update={
            "completed": False,
            "completed_at": now,
            "due_date": next_due_date,
            "birthday_details": birthday_details,
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
            "next_due_date": get_next_due_date(reminder.due_date, reminder.repeat),
            "computed_label": get_computed_label(reminder),
            "birthday_age_label": get_birthday_age_label(reminder.birthday_details)
            if reminder.reminder_type == ReminderType.BIRTHDAY
            else None,
        }
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def prepare_create_fields(payload: ReminderCreate) -> dict:
    data = payload.model_dump()
    return prepare_birthday_fields(data)


def prepare_update_fields(reminder: Reminder, updates: dict) -> dict:
    reminder_type = updates.get("reminder_type", reminder.reminder_type)
    if reminder_type == ReminderType.BIRTHDAY or reminder_type == ReminderType.BIRTHDAY.value:
        merged = {**reminder.model_dump(), **updates}
        return prepare_birthday_fields(merged, keep_existing_timing=True)

    if reminder_type == ReminderType.GENERIC or reminder_type == ReminderType.GENERIC.value:
        updates["reminder_type"] = ReminderType.GENERIC
        updates["birthday_details"] = None

    return updates


def prepare_birthday_fields(data: dict, keep_existing_timing: bool = False) -> dict:
    if data.get("reminder_type") != ReminderType.BIRTHDAY and data.get("reminder_type") != ReminderType.BIRTHDAY.value:
        data["reminder_type"] = ReminderType.GENERIC
        data["birthday_details"] = None
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
    data["due_date"] = due_date
    data["repeat"] = RepeatOption.YEARLY

    if not keep_existing_timing or data.get("reminder_lead_value") is None:
        data["reminder_lead_value"] = data.get("reminder_lead_value") if data.get("reminder_lead_value") is not None else 1
    if not keep_existing_timing or data.get("reminder_lead_unit") is None:
        data["reminder_lead_unit"] = data.get("reminder_lead_unit") or ReminderLeadUnit.WEEKS
    if not keep_existing_timing or data.get("reminder_time") is None:
        data["reminder_time"] = data.get("reminder_time") or "09:00"

    return data


def get_computed_label(reminder: Reminder) -> str | None:
    if reminder.reminder_type != ReminderType.BIRTHDAY:
        return None

    return get_birthday_computed_label(reminder.birthday_details, reminder.due_date)
