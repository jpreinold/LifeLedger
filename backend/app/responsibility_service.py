from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from app.attachments_repository import RecordAttachmentRepository
from app.linked_items_repository import (
    DuplicateLinkedItemError,
    LinkedItemRepository,
    canonical_pair_key,
    linked_item_lookup_key,
)
from app.models import LinkedItem, Reminder
from app.person_birthday_service import PersonBirthdayService
from app.records_repository import RecordRepository
from app.relationship_service import ItemResolver
from app.repository import ReminderRepository
from app.responsibility_lifecycle_service import LifecycleOperationResult, ResponsibilityLifecycleService
from app.schemas import (
    LinkedEntityType,
    RelationshipType,
    ReminderCompleteRequest,
    ReminderCreate,
    ReminderRenewRequest,
    ResponsibilityEventSource,
)
from app.search_service import SearchProjectionService


class ResponsibilityNotFound(KeyError):
    pass


class ResponsibilityConflict(ValueError):
    pass


@dataclass(frozen=True)
class ResponsibilityMutationResult:
    reminder: Reminder
    idempotent_replay: bool


class RelationshipApplicationService:
    def __init__(
        self,
        relationships: LinkedItemRepository,
        records: RecordRepository,
        reminders: ReminderRepository,
        attachments: RecordAttachmentRepository,
        search: SearchProjectionService,
    ):
        self.relationships = relationships
        self.records = records
        self.reminders = reminders
        self.attachments = attachments
        self.search = search

    def create(
        self,
        *,
        user_id: str,
        source_type: LinkedEntityType,
        source_id: str,
        target_type: LinkedEntityType,
        target_id: str,
        relationship_type: RelationshipType,
        label: str | None,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> tuple[LinkedItem, bool]:
        resolver = ItemResolver(self.records, self.reminders, self.attachments)
        resolver.require_summary(user_id, source_type, source_id)
        resolver.require_summary(user_id, target_type, target_id)
        existing = self.relationships.list_links_for_entity(user_id, source_type, source_id)
        replay = next(
            (
                item
                for item in existing
                if {item.source_type, item.target_type} == {source_type, target_type}
                and {item.source_id, item.target_id} == {source_id, target_id}
            ),
            None,
        )
        if replay:
            return replay, True
        current = _utc(now)
        link_id = str(uuid5(NAMESPACE_URL, f"lifeledger:relationship-service:{user_id}:{idempotency_key}"))
        link = LinkedItem(
            user_id=user_id,
            link_id=link_id,
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            relationship_type=relationship_type,
            label=label,
            canonical_pair_key=canonical_pair_key(source_type, source_id, target_type, target_id),
            source_link_key=linked_item_lookup_key(source_type, source_id, link_id),
            target_link_key=linked_item_lookup_key(target_type, target_id, link_id),
            created_at=current,
            updated_at=current,
            created_by="assistant_capture",
        )
        try:
            saved = self.relationships.create_link(link)
        except DuplicateLinkedItemError:
            existing = self.relationships.list_links_for_entity(user_id, source_type, source_id)
            replay = next(
                item
                for item in existing
                if {item.source_id, item.target_id} == {source_id, target_id}
            )
            return replay, True
        self.search.sync_entity_and_neighbors_observed(
            user_id, source_type, source_id, operation="assistant_relationship_create"
        )
        return saved, False


class ResponsibilityApplicationService:
    """Assistant-safe boundary over responsibility lifecycle and relationship services."""

    def __init__(
        self,
        reminders: ReminderRepository,
        lifecycle: ResponsibilityLifecycleService,
        relationships: RelationshipApplicationService,
        linked_repository: LinkedItemRepository,
        birthdays: PersonBirthdayService | None = None,
    ):
        self.reminders = reminders
        self.lifecycle = lifecycle
        self.relationships = relationships
        self.linked_repository = linked_repository
        self.birthdays = birthdays

    def create(
        self,
        *,
        user_id: str,
        fields: dict,
        item_id: str | None,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> ResponsibilityMutationResult:
        payload = ReminderCreate.model_validate(fields)
        duplicate = self._find_duplicate(user_id, payload, item_id)
        if duplicate:
            if self.birthdays is not None:
                self.birthdays.synchronize_from_reminder(duplicate, item_id=item_id, now=now)
            return ResponsibilityMutationResult(duplicate, True)
        reminder_id = str(uuid5(NAMESPACE_URL, f"lifeledger:responsibility-service:{user_id}:{idempotency_key}"))
        existing = self.reminders.get_reminder(user_id, reminder_id)
        if existing:
            if self.birthdays is not None:
                self.birthdays.synchronize_from_reminder(existing, item_id=item_id, now=now)
            return ResponsibilityMutationResult(existing, True)
        current = _utc(now)
        reminder = Reminder(
            id=reminder_id,
            user_id=user_id,
            **payload.model_dump(),
            completed=False,
            created_at=current,
            updated_at=current,
            completed_at=None,
        )
        result = self.lifecycle.create_responsibility(
            reminder,
            item_id=item_id,
            idempotency_key=idempotency_key,
            now=current,
            source=ResponsibilityEventSource.ASSISTANT_CAPTURE,
        )
        if item_id:
            self.relationships.create(
                user_id=user_id,
                source_type=LinkedEntityType.RECORD,
                source_id=item_id,
                target_type=LinkedEntityType.REMINDER,
                target_id=result.reminder.id,
                relationship_type=RelationshipType.REMINDER_FOR,
                label=None,
                idempotency_key=f"{idempotency_key}:item-link",
                now=current,
            )
        if self.birthdays is not None:
            self.birthdays.synchronize_from_reminder(result.reminder, item_id=item_id, now=current)
        return ResponsibilityMutationResult(result.reminder, result.idempotent_replay)

    def complete(
        self, *, user_id: str, reminder_id: str, fields: dict, idempotency_key: str, now: datetime | None = None
    ) -> ResponsibilityMutationResult:
        reminder = self._required(user_id, reminder_id)
        if reminder.archived_at is not None:
            raise ResponsibilityConflict("Archived responsibilities cannot be completed.")
        if reminder.completed:
            return ResponsibilityMutationResult(reminder, True)
        result = self.lifecycle.complete(
            user_id,
            reminder,
            ReminderCompleteRequest.model_validate(fields),
            idempotency_key=idempotency_key,
            now=_utc(now),
        )
        return ResponsibilityMutationResult(result.reminder, result.idempotent_replay)

    def renew(
        self, *, user_id: str, reminder_id: str, fields: dict, idempotency_key: str, now: datetime | None = None
    ) -> ResponsibilityMutationResult:
        reminder = self._required(user_id, reminder_id)
        if reminder.archived_at is not None:
            raise ResponsibilityConflict("Archived responsibilities cannot be renewed.")
        result = self.lifecycle.renew(
            user_id,
            reminder,
            ReminderRenewRequest.model_validate(fields),
            idempotency_key=idempotency_key,
            now=_utc(now),
        )
        return ResponsibilityMutationResult(result.reminder, result.idempotent_replay)

    def snooze(
        self, *, user_id: str, reminder_id: str, snoozed_until: datetime, idempotency_key: str, now: datetime | None = None
    ) -> ResponsibilityMutationResult:
        reminder = self._required(user_id, reminder_id)
        current = _utc(now)
        target = _utc(snoozed_until)
        if reminder.completed or reminder.archived_at is not None or target <= current:
            raise ResponsibilityConflict("This responsibility cannot be snoozed to that time.")
        if reminder.snoozed_until == target:
            return ResponsibilityMutationResult(reminder, True)
        result = self.lifecycle.snooze(
            user_id,
            reminder,
            target,
            idempotency_key=idempotency_key,
            now=current,
        )
        return ResponsibilityMutationResult(result.reminder, result.idempotent_replay)

    def get(self, user_id: str, reminder_id: str) -> Reminder:
        return self._required(user_id, reminder_id)

    def _required(self, user_id: str, reminder_id: str) -> Reminder:
        reminder = self.reminders.get_reminder(user_id, reminder_id)
        if reminder is None:
            raise ResponsibilityNotFound("Responsibility not found.")
        return reminder

    def _find_duplicate(self, user_id: str, payload: ReminderCreate, item_id: str | None) -> Reminder | None:
        if not item_id:
            return None
        links = self.linked_repository.list_links_for_entity(user_id, LinkedEntityType.RECORD, item_id)
        reminder_ids = {
            link.target_id if link.target_type == LinkedEntityType.REMINDER else link.source_id
            for link in links
            if link.source_type == LinkedEntityType.REMINDER or link.target_type == LinkedEntityType.REMINDER
        }
        for reminder in self.reminders.list_reminders(user_id, limit=500):
            if reminder.id not in reminder_ids or reminder.archived_at is not None:
                continue
            if reminder.reminder_type != payload.reminder_type:
                continue
            if payload.birthday_details and reminder.birthday_details:
                if (
                    reminder.birthday_details.birth_month == payload.birthday_details.birth_month
                    and reminder.birthday_details.birth_day == payload.birthday_details.birth_day
                ):
                    return reminder
            elif reminder.title.casefold() == payload.title.casefold():
                return reminder
        return None


def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)
