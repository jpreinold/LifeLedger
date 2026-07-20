from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from app.birthday_value import BirthdayValueError, ParsedBirthday, parse_birthday_value
from app.birthdays import enrich_birthday_details, get_next_birthday_due_date
from app.linked_items_repository import (
    DuplicateLinkedItemError,
    LinkedItemRepository,
    canonical_pair_key,
    linked_item_lookup_key,
)
from app.models import LinkedItem, Record, Reminder
from app.records_repository import RecordRepository
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
SUPPORTED_BIRTHDAY_RECORD_TYPES = {RecordType.PERSON, RecordType.PET}

PersonBirthdayValueError = BirthdayValueError
ParsedPersonBirthday = ParsedBirthday
parse_person_birthday = parse_birthday_value


def validate_person_birthday_field(
    record: Record,
    *,
    field_key: str,
    value: object,
    is_sensitive: bool,
    has_value: bool,
    today: date | None = None,
) -> None:
    if record.record_type not in SUPPORTED_BIRTHDAY_RECORD_TYPES or field_key != PERSON_BIRTHDAY_KEY or not has_value:
        return
    if is_sensitive:
        raise PersonBirthdayValueError("Birthday must be a normal detail so LifeLedger can maintain its reminder.")
    parse_birthday_value(value, today=today)


class PersonBirthdayService:
    """Keeps Person/Pet items and their one linked annual birthday reminder in sync."""

    def __init__(
        self,
        reminders: ReminderRepository,
        lifecycle: ResponsibilityLifecycleService,
        links: LinkedItemRepository,
        search: SearchProjectionService,
        records: RecordRepository | None = None,
    ):
        self.reminders = reminders
        self.records = records
        self.lifecycle = lifecycle
        self.links = links
        self.search = search

    def synchronize(self, record: Record, *, now: datetime | None = None) -> Reminder | None:
        current = _utc(now)
        record = self._canonical_record(record, today=current.date(), persist=True)
        birthday = self._birthday(record, today=current.date())
        existing = self._managed_reminder(record, birthday)
        if record.record_type not in SUPPORTED_BIRTHDAY_RECORD_TYPES or record.status == RecordStatus.ARCHIVED or birthday is None:
            return self._archive(existing, current)

        due_date = get_next_birthday_due_date(birthday.month, birthday.day, today=current.date())
        retained_age = None
        if (
            birthday.year is None
            and existing is not None
            and existing.birthday_details is not None
            and existing.birthday_details.inferred_birth_year
            and (existing.birthday_details.birth_month, existing.birthday_details.birth_day) == (birthday.month, birthday.day)
        ):
            retained_age = existing.birthday_details.age_turning_next_birthday
        inferred_birth_year = record.birthday_inferred_birth_year if birthday.year is None else None
        if retained_age is None and inferred_birth_year is not None:
            retained_age = due_date.year - inferred_birth_year
        details = enrich_birthday_details(
            BirthdayDetails(
                subject_type=record.record_type,
                person_name=record.title,
                birth_month=birthday.month,
                birth_day=birthday.day,
                birth_year=birthday.year,
                age_turning_next_birthday=retained_age,
                inferred_birth_year=inferred_birth_year is not None,
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

    def synchronize_from_reminder(
        self,
        reminder: Reminder,
        *,
        item_id: str | None = None,
        now: datetime | None = None,
    ) -> Record | None:
        """Create or update the birthday subject for a confirmed birthday reminder.

        This intentionally does not call ``synchronize`` again: the reminder that
        caused the item write is already the canonical paired reminder.
        """
        if reminder.reminder_type != ReminderType.BIRTHDAY or reminder.birthday_details is None:
            return None
        if self.records is None:
            return None

        current = _utc(now)
        details = reminder.birthday_details
        subject_type = details.subject_type
        if subject_type not in SUPPORTED_BIRTHDAY_RECORD_TYPES:
            return None
        birthday = ParsedBirthday(
            month=details.birth_month,
            day=details.birth_day,
            year=None if details.inferred_birth_year else details.birth_year,
        )

        record = self._linked_birthday_record(reminder, preferred_record_id=item_id)
        if record is None:
            record = self._matching_birthday_record(reminder.user_id, subject_type, details.person_name, birthday)

        if record is None:
            record_id = str(uuid5(NAMESPACE_URL, f"lifeledger:birthday-subject:{reminder.user_id}:{reminder.id}"))
            record = self.records.get_record(reminder.user_id, record_id)
            if record is None:
                record = Record(
                    id=record_id,
                    user_id=reminder.user_id,
                    record_type=subject_type,
                    title=details.person_name,
                    category="People" if subject_type == RecordType.PERSON else "Family",
                    birthday=birthday.stored_value,
                    birthday_inferred_birth_year=details.birth_year if details.inferred_birth_year else None,
                    relationship_context=details.relationship if subject_type == RecordType.PERSON else None,
                    created_at=current,
                    updated_at=current,
                )
                record = self.records.create_record(record)

        next_title = details.person_name if record.id == str(
            uuid5(NAMESPACE_URL, f"lifeledger:birthday-subject:{reminder.user_id}:{reminder.id}")
        ) else record.title
        updates: dict[str, object] = {
            "birthday": birthday.stored_value,
            "birthday_inferred_birth_year": details.birth_year if details.inferred_birth_year else None,
            "dynamic_fields": [
                field
                for field in record.dynamic_fields
                if field.key not in {PERSON_BIRTHDAY_KEY, PERSON_RELATIONSHIP_KEY}
            ],
            "updated_at": current,
        }
        if subject_type == RecordType.PERSON and details.relationship is not None:
            updates["relationship_context"] = details.relationship
        if next_title != record.title:
            updates["title"] = next_title
        updated = record.model_copy(update=updates)
        if updated != record:
            record = self.records.update_record(updated)
            self.search.sync_entity_and_neighbors_observed(
                record.user_id,
                LinkedEntityType.RECORD,
                record.id,
                operation="birthday_reminder_item_sync",
            )
        self._ensure_link(record, reminder, current)
        return record

    def canonical_record(self, record: Record, *, today: date | None = None) -> Record:
        """Expose old dynamic birthday data through the new first-class field."""
        return self._canonical_record(record, today=today or date.today(), persist=False)

    @staticmethod
    def reminder_id(user_id: str, record_id: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"lifeledger:person-birthday:{user_id}:{record_id}"))

    def _canonical_record(self, record: Record, *, today: date, persist: bool) -> Record:
        updated = canonicalize_birthday_record(record, today=today)
        if updated == record:
            return record
        return self.records.update_record(updated) if persist and self.records is not None else updated

    def _linked_birthday_record(self, reminder: Reminder, *, preferred_record_id: str | None) -> Record | None:
        if preferred_record_id:
            preferred = self.records.get_record(reminder.user_id, preferred_record_id)
            if preferred is not None and preferred.record_type in SUPPORTED_BIRTHDAY_RECORD_TYPES:
                return preferred
        for link in self.links.list_links_for_entity(reminder.user_id, LinkedEntityType.REMINDER, reminder.id):
            if link.source_type == LinkedEntityType.RECORD:
                record_id = link.source_id
            elif link.target_type == LinkedEntityType.RECORD:
                record_id = link.target_id
            else:
                continue
            candidate = self.records.get_record(reminder.user_id, record_id)
            if candidate is not None and candidate.record_type in SUPPORTED_BIRTHDAY_RECORD_TYPES:
                return candidate
        return None

    def _matching_birthday_record(
        self,
        user_id: str,
        subject_type: RecordType,
        name: str,
        birthday: ParsedBirthday,
    ) -> Record | None:
        matches: list[Record] = []
        for candidate in self.records.list_records(user_id):
            if candidate.record_type != subject_type or candidate.title.casefold() != name.casefold():
                continue
            existing = self._birthday(candidate, today=date.today())
            if existing is None or (existing.month, existing.day) == (birthday.month, birthday.day):
                matches.append(candidate)
        return matches[0] if len(matches) == 1 else None

    def _managed_reminder(self, record: Record, birthday: ParsedBirthday | None) -> Reminder | None:
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
    def _birthday(record: Record, *, today: date) -> ParsedBirthday | None:
        if record.record_type not in SUPPORTED_BIRTHDAY_RECORD_TYPES:
            return None
        if record.birthday:
            return parse_birthday_value(record.birthday, today=today)
        field = next(
            (
                item
                for item in record.dynamic_fields
                if item.key == PERSON_BIRTHDAY_KEY and item.has_value and not item.is_sensitive and item.value is not None
            ),
            None,
        )
        return parse_birthday_value(field.value, today=today) if field else None

    @staticmethod
    def _relationship(record: Record) -> str | None:
        if record.record_type != RecordType.PERSON:
            return None
        if record.relationship_context:
            return record.relationship_context
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


def canonicalize_birthday_record(record: Record, *, today: date | None = None) -> Record:
    if record.record_type not in SUPPORTED_BIRTHDAY_RECORD_TYPES:
        return record
    legacy = next(
        (
            field
            for field in record.dynamic_fields
            if field.key == PERSON_BIRTHDAY_KEY and field.has_value and not field.is_sensitive and field.value is not None
        ),
        None,
    )
    birthday = record.birthday
    if birthday is None and legacy is not None:
        birthday = parse_birthday_value(legacy.value, today=today).stored_value
    legacy_relationship = next(
        (
            field
            for field in record.dynamic_fields
            if record.record_type == RecordType.PERSON
            and field.key == PERSON_RELATIONSHIP_KEY
            and field.has_value
            and not field.is_sensitive
            and field.value is not None
        ),
        None,
    )
    relationship = record.relationship_context
    if relationship is None and legacy_relationship is not None:
        relationship = str(legacy_relationship.value).strip() or None
    migrated_keys = {PERSON_BIRTHDAY_KEY}
    if record.record_type == RecordType.PERSON:
        migrated_keys.add(PERSON_RELATIONSHIP_KEY)
    next_fields = [field for field in record.dynamic_fields if field.key not in migrated_keys]
    if (
        birthday == record.birthday
        and relationship == record.relationship_context
        and len(next_fields) == len(record.dynamic_fields)
    ):
        return record
    return record.model_copy(
        update={
            "birthday": birthday,
            "relationship_context": relationship,
            "dynamic_fields": next_fields,
        }
    )


def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)
