import json
import os
import threading
from pathlib import Path
from typing import Protocol

from app.models import Reminder


class ReminderRepository(Protocol):
    def list_reminders(self, user_id: str, limit: int | None = None) -> list[Reminder]:
        ...

    def list_reminders_page(
        self, user_id: str, *, limit: int, cursor: str | None = None
    ) -> tuple[list[Reminder], str | None]:
        ...

    def create_reminder(self, reminder: Reminder) -> Reminder:
        ...

    def get_reminder(self, user_id: str, reminder_id: str) -> Reminder | None:
        ...

    def update_reminder(self, reminder: Reminder) -> Reminder:
        ...

    def delete_reminder(self, user_id: str, reminder_id: str) -> bool:
        ...


class LocalReminderRepository:
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

        if not self.file_path.exists():
            self._write_all_unlocked([])

    def list_reminders(self, user_id: str, limit: int | None = None) -> list[Reminder]:
        with self._lock:
            reminders = [reminder for reminder in self._read_all_unlocked() if reminder.user_id == user_id]
        return reminders[:limit] if limit is not None else reminders

    def list_reminders_page(
        self, user_id: str, *, limit: int, cursor: str | None = None
    ) -> tuple[list[Reminder], str | None]:
        reminders = sorted(self.list_reminders(user_id), key=lambda item: item.id)
        if cursor:
            reminders = [item for item in reminders if item.id > cursor]
        page = reminders[:limit]
        next_cursor = page[-1].id if len(reminders) > limit and page else None
        return page, next_cursor

    def create_reminder(self, reminder: Reminder) -> Reminder:
        with self._lock:
            reminders = self._read_all_unlocked()
            if any(existing.user_id == reminder.user_id and existing.id == reminder.id for existing in reminders):
                return next(
                    existing
                    for existing in reminders
                    if existing.user_id == reminder.user_id and existing.id == reminder.id
                )
            reminders.append(reminder)
            self._write_all_unlocked(reminders)
            return reminder

    def get_reminder(self, user_id: str, reminder_id: str) -> Reminder | None:
        with self._lock:
            return next(
                (
                    reminder
                    for reminder in self._read_all_unlocked()
                    if reminder.user_id == user_id and reminder.id == reminder_id
                ),
                None,
            )

    def update_reminder(self, reminder: Reminder) -> Reminder:
        with self._lock:
            reminders = self._read_all_unlocked()
            for index, existing in enumerate(reminders):
                if existing.user_id == reminder.user_id and existing.id == reminder.id:
                    reminders[index] = reminder
                    self._write_all_unlocked(reminders)
                    return reminder

            reminders.append(reminder)
            self._write_all_unlocked(reminders)
            return reminder

    def delete_reminder(self, user_id: str, reminder_id: str) -> bool:
        with self._lock:
            reminders = self._read_all_unlocked()
            next_reminders = [
                reminder
                for reminder in reminders
                if not (reminder.user_id == user_id and reminder.id == reminder_id)
            ]

            if len(next_reminders) == len(reminders):
                return False

            self._write_all_unlocked(next_reminders)
            return True

    def _read_all_unlocked(self) -> list[Reminder]:
        if not self.file_path.exists():
            return []

        raw_data = json.loads(self.file_path.read_text(encoding="utf-8") or "[]")
        return [Reminder.model_validate(item) for item in raw_data]

    def _write_all_unlocked(self, reminders: list[Reminder]) -> None:
        serialized = [reminder.model_dump(mode="json") for reminder in reminders]
        temp_path = self.file_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
        os.replace(temp_path, self.file_path)


def default_data_file() -> Path:
    backend_root = Path(__file__).resolve().parents[1]
    return backend_root / "data" / "reminders.json"
