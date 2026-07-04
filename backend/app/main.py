from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app.auth import UserContext, get_current_user
from app.config import get_settings
from app.models import Reminder
from app.recurrence import advance_due_date, calculate_status, get_next_due_date
from app.repository import ReminderRepository
from app.repository_factory import create_repository
from app.schemas import ReminderCreate, ReminderResponse, ReminderUpdate, RepeatOption

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
    reminder = Reminder(
        id=str(uuid4()),
        user_id=current_user.user_id,
        title=payload.title,
        category=payload.category,
        due_date=payload.due_date,
        repeat=payload.repeat,
        priority=payload.priority,
        notes=payload.notes,
        reminder_lead_value=payload.reminder_lead_value,
        reminder_lead_unit=payload.reminder_lead_unit,
        reminder_time=payload.reminder_time,
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

    updated = reminder.model_copy(update={**updates, "updated_at": utc_now()})
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
    advanced_reminder = reminder.model_copy(
        update={
            "completed": False,
            "completed_at": now,
            "due_date": next_due_date,
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
        }
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
