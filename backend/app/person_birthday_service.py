from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import re
from uuid import NAMESPACE_URL, uuid5

from app.birthdays import enrich_birthday_details, get_next_birthday_due_date
from app.linked_items_repository import (
    DuplicateLinkedItemError,
    LinkedItemRepository,
    canonical_pair_key,
    linked_item_lookup_key,
)
from app.models import LinkedItem, Record, Reminder
from app.repository import ReminderRepository
from app.responsibility_lifecycle_service import ResponsibilityLifecycleService
from app.schemas import (
    BirthdayDetails,
    LinkedEntityType,
    PriorityOption,
    RecordStatus,
    RecordType,
    RelationshipType,
    ReminderCategory,
    ReminderLeadUnit,
    ReminderType,
    RepeatOption,
    ResponsibilityEventSource,
    ResponsibilityWorkflowId,
)
from app.search_service import SearchProjectionService


PERSON_BIRTHDAY_KEY = "birthday"
PERSON_RELATIONSHIP_KEY = "relationship_context"


class PersonBirthdayValueError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedPersonBirthday:
    month: int
    day: int
    year: int | None = None

    @property
    def stored_value(self) -> str:
        if self.year is None:
            return f"--{self.month:02d}-{self.day:02d}"
        return f"{self.year:04d}-{self.month:02d}-{self.day:02d}"


def parse_person_birthday(value: object, *, today: date | None = None) -> ParsedPersonBirthday:
    text = str(value).strip()
    month_day = re.fullmatch(r"--(\d{2})-(\d{2})", text)
    full_date = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if not month_day and not full_date:
        raise PersonBirthdayValueError("Person birthdays must include a month and day; the year is optional.")

    year = int(full_date.group(1)) if full_date else None
    month = int((full_date or month_day).group(2 if full_date else 1))
    day = int((full_date or month_day).group(3 if full_date else 2))
    try:
        date(year or 2000, month, day)
    except ValueError as exc:
        raise PersonBirthdayValueError("Choose a valid birthday.") from exc

    parsed = ParsedPersonBirthday(month=month, day=day, year=year)
    if year is not None:
        due_date = get_next_birthday_due_date(month, day, today=today)
        age = due_date.year - year
        if age < 0 or age > 150:
            raise PersonBirthdayValueError("Birth year must produce an age between 0 and 150.")
    return parsed


def validate_person_birthday_field(
    record: Record,
    *,
    field_key: str,
    value: object,
    is_sensitive: bool,
    has_value: bool,
    today: date | None = None,
) -> None:
    if record.record_type != RecordType.PERSON or field_key != PERSON_BIRTHDAY_KEY or not has_value:
        return
    if is_sensitive:
        raise PersonBirthdayValueError("Birthday must be a normal detail so LifeLedger can maintain its reminder.")
    parse_person_birthday(value, today=today)


class PersonBirthdayService:
    """Maintains the one system-owned birthday reminder derived from a Person item."""

    def __init__(
        self,
        reminders: ReminderRepository,
        lifecycle: ResponsibilityLifecycleService,
        links: LinkedItemRepository,
        search: SearchProjectionService,
    ):
        self.reminders = reminders
        self.lifecycle = lifecycle
        self.links = links
        self.search = search

    def synchronize(self, record: Record, *, now: datetime | None = None) -> Reminder | None:
        current = _utc(now)
        birthday = self._birthday(record, today=current.date())
        existing = self._managed_reminder(record, birthday)
        if record.record_type != RecordType.PERSON or record.status == RecordStatus.ARCHIVED or birthday is None:
            return self._archive(existing, current)

        due_date = get_next_birthday_due_date(birthday.month, birthday.day, today=current.date())
        details = enrich_birthday_details(
            BirthdayDetails(
                person_name=record.title,
                birth_month=birthday.month,
                birth_day=birthday.day,
                birth_year=birthday.year,
                relationship=self._relationship(record),
            ),
            due_date,
        )

        if existing is None:
            reminder_id = self.reminder_id(record.user_id, record.id)
            reminder = Reminder(
                id=reminder_id,
                user_id=record.user_id,
                title=self._title(record),
                category=ReminderCategory.FAMILY,
                due_date=due_date,
                repeat=RepeatOption.YEARLY,
                priority=PriorityOption.MEDIUM,
                reminder_lead_value=7,
                reminder_lead_unit=ReminderLeadUnit.DAYS,
                reminder_type=ReminderType.BIRTHDAY,
                birthday_details=details,
                workflow_id=ResponsibilityWorkflowId.PERSON_BIRTHDAY,
                completed=False,
                created_at=current,
                updated_at=current,
            )
            result = self.lifecycle.create_responsibility(
                reminder,
                item_id=record.id,
                idempotency_key=f"person-birthday:{record.id}",
                now=current,
                source=ResponsibilityEventSource.SYSTEM,
            )
            saved = result.reminder
            self._ensure_link(record, saved, current)
            return saved

        self._ensure_link(record, existing, current)
        updates: dict[str, object] = {
            "title": self._title(record),
            "category": ReminderCategory.FAMILY,
            "due_date": due_date,
            "repeat": RepeatOption.YEARLY,
            "reminder_type": ReminderType.BIRTHDAY,
            "birthday_details": details,
            "workflow_id": ResponsibilityWorkflowId.PERSON_BIRTHDAY,
            "completed": False,
            "completed_at": None,
            "archived_at": None,
            "updated_at": current,
        }
        if due_date != existing.due_date:
            updates.update({"snoozed_until": None, "alert_snoozed_until": None})
        updated = existing.model_copy(update=updates)
        if _managed_values(existing) == _managed_values(updated):
            return existing
        if due_date != existing.due_date:
            return self.lifecycle.change_due_date(
                record.user_id,
                existing,
                updated,
                idempotency_key=f"person-birthday-sync:{record.id}:{birthday.stored_value}:{due_date.isoformat()}",
                now=current,
                sync_item_date=False,
            ).reminder

        saved = self.reminders.update_reminder(updated.model_copy(update={"version": existing.version + 1}))
        self.search.sync_entity_and_neighbors_observed(
            record.user_id,
            LinkedEntityType.REMINDER,
            saved.id,
            operation="person_birthday_sync",
        )
        return saved

    def retire(self, record: Record, *, now: datetime | None = None) -> Reminder | None:
        return self._archive(self._managed_reminder(record, None), _utc(now))

    @staticmethod
    def reminder_id(user_id: str, record_id: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"lifeledger:person-birthday:{user_id}:{record_id}"))

    def _managed_reminder(self, record: Record, birthday: ParsedPersonBirthday | None) -> Reminder | None:
        deterministic = self.reminders.get_reminder(record.user_id, self.reminder_id(record.user_id, record.id))
        if deterministic is not None:
            return deterministic

        for link in self.links.list_links_for_entity(record.user_id, LinkedEntityType.RECORD, record.id):
            reminder_id = link.target_id if link.target_type == LinkedEntityType.REMINDER else link.source_id
            candidate = self.reminders.get_reminder(record.user_id, reminder_id)
            if candidate is None or candidate.reminder_type != ReminderType.BIRTHDAY:
                continue
            if candidate.workflow_id == ResponsibilityWorkflowId.PERSON_BIRTHDAY:
                return candidate
            if birthday and candidate.birthday_details and (
                candidate.birthday_details.birth_month,
                candidate.birthday_details.birth_day,
            ) == (birthday.month, birthday.day):
                return candidate
        return None

    @staticmethod
    def _birthday(record: Record, *, today: date) -> ParsedPersonBirthday | None:
        if record.record_type != RecordType.PERSON:
            return None
        field = next(
            (
                item
                for item in record.dynamic_fields
                if item.key == PERSON_BIRTHDAY_KEY and item.has_value and not item.is_sensitive and item.value is not None
            ),
            None,
        )
        return parse_person_birthday(field.value, today=today) if field else None

    @staticmethod
    def _relationship(record: Record) -> str | None:
        field = next(
            (
                item
                for item in record.dynamic_fields
                if item.key == PERSON_RELATIONSHIP_KEY and item.has_value and not item.is_sensitive and item.value is not None
            ),
            None,
        )
        return str(field.value).strip() or None if field else None

    @staticmethod
    def _title(record: Record) -> str:
        return f"{record.title}'s birthday"

    def _ensure_link(self, record: Record, reminder: Reminder, now: datetime) -> None:
        if self.links.link_exists(
            record.user_id,
            LinkedEntityType.RECORD,
            record.id,
            LinkedEntityType.REMINDER,
            reminder.id,
        ):
            return
        link_id = str(uuid5(NAMESPACE_URL, f"lifeledger:person-birthday-link:{record.user_id}:{record.id}"))
        link = LinkedItem(
            user_id=record.user_id,
            link_id=link_id,
            source_type=LinkedEntityType.RECORD,
            source_id=record.id,
            target_type=LinkedEntityType.REMINDER,
            target_id=reminder.id,
            relationship_type=RelationshipType.REMINDER_FOR,
            canonical_pair_key=canonical_pair_key(
                LinkedEntityType.RECORD,
                record.id,
                LinkedEntityType.REMINDER,
                reminder.id,
            ),
            source_link_key=linked_item_lookup_key(LinkedEntityType.RECORD, record.id, link_id),
            target_link_key=linked_item_lookup_key(LinkedEntityType.REMINDER, reminder.id, link_id),
            created_at=now,
            updated_at=now,
            created_by="system",
        )
        try:
            self.links.create_link(link)
        except DuplicateLinkedItemError:
            return
        self.search.sync_entity_and_neighbors_observed(
            record.user_id,
            LinkedEntityType.RECORD,
            record.id,
            operation="person_birthday_link",
        )

    def _archive(self, reminder: Reminder | None, now: datetime) -> Reminder | None:
        if reminder is None or reminder.archived_at is not None:
            return reminder
        saved = self.reminders.update_reminder(
            reminder.model_copy(update={"archived_at": now, "updated_at": now, "version": reminder.version + 1})
        )
        self.search.sync_entity_and_neighbors_observed(
            reminder.user_id,
            LinkedEntityType.REMINDER,
            reminder.id,
            operation="person_birthday_archive",
        )
        return saved


def _managed_values(reminder: Reminder) -> tuple[object, ...]:
    return (
        reminder.title,
        reminder.category,
        reminder.due_date,
        reminder.repeat,
        reminder.reminder_type,
        reminder.birthday_details,
        reminder.workflow_id,
        reminder.completed,
        reminder.completed_at,
        reminder.archived_at,
    )


def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)
