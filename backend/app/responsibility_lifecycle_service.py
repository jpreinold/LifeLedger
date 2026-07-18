import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

from app.alerts import clear_alert_action_state, snooze_alert_state
from app.attachments_repository import RecordAttachmentRepository
from app.birthdays import enrich_birthday_details
from app.linked_items_repository import LinkedItemRepository
from app.maintenance import advance_maintenance_details, get_maintenance_due_date
from app.models import Record, Reminder, ResponsibilityEvent
from app.recurrence import advance_due_date
from app.records_repository import RecordRepository
from app.renewals import advance_renewal_details
from app.repository import ReminderRepository
from app.responsibility_history_repository import LifecycleWriteConflict, ResponsibilityHistoryRepository
from app.responsibility_sync import resolve_date_target, resolve_date_target_for_key, synchronize_item_date
from app.schemas import (
    AttachmentStatus,
    LifecycleReconciliationResult,
    LifecycleReconciliationStatus,
    LinkedEntityType,
    MaintenanceDetails,
    ReminderCompleteRequest,
    ReminderRenewRequest,
    ReminderType,
    RepeatOption,
    ResponsibilityEventSource,
    ResponsibilityEventType,
    ResponsibilityEvidenceRequest,
    RenewalDetails,
)
from app.search_service import SearchProjectionService


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LifecycleOperationResult:
    reminder: Reminder
    event: ResponsibilityEvent
    reconciliation_status: LifecycleReconciliationStatus
    idempotent_replay: bool = False


class ResponsibilityLifecycleService:
    def __init__(
        self,
        reminder_repo: ReminderRepository,
        history_repo: ResponsibilityHistoryRepository,
        record_repo: RecordRepository,
        linked_repo: LinkedItemRepository,
        attachment_repo: RecordAttachmentRepository,
        search_service: SearchProjectionService,
    ):
        self.reminder_repo = reminder_repo
        self.history_repo = history_repo
        self.record_repo = record_repo
        self.linked_repo = linked_repo
        self.attachment_repo = attachment_repo
        self.search_service = search_service

    def create_responsibility(
        self,
        reminder: Reminder,
        *,
        item_id: str | None,
        idempotency_key: str | None,
        now: datetime,
    ) -> LifecycleOperationResult:
        item = self._require_item(reminder.user_id, item_id) if item_id else None
        occurrence_id = reminder.current_occurrence_id or new_occurrence_id(reminder.id, reminder.due_date, "created")
        operation_key = scoped_operation_key("create", idempotency_key or reminder.id)
        replay = self._replay(reminder.user_id, reminder.id, operation_key)
        if replay:
            return replay
        created = reminder.model_copy(update={"current_occurrence_id": occurrence_id, "version": 1})
        event = new_event(
            reminder=created,
            event_type=ResponsibilityEventType.RESPONSIBILITY_CREATED,
            occurred_at=now,
            idempotency_key=operation_key,
            occurrence_id=occurrence_id,
            item=item,
            next_due_date=created.due_date,
            source=ResponsibilityEventSource.GUIDED_WORKFLOW if created.workflow_id else ResponsibilityEventSource.USER,
        )
        saved = self.history_repo.commit_reminder_event(self.reminder_repo, None, created, event)
        return self._finalize(saved, event, sync_item_date=False)

    def complete(
        self,
        user_id: str,
        reminder: Reminder,
        payload: ReminderCompleteRequest,
        *,
        idempotency_key: str | None,
        now: datetime,
    ) -> LifecycleOperationResult:
        occurrence_id = payload.occurrence_id or current_occurrence_id(reminder)
        operation_key = scoped_operation_key("complete", idempotency_key or occurrence_id)
        replay = self._replay(user_id, reminder.id, operation_key)
        if replay:
            return replay
        self._assert_occurrence(reminder, payload.occurrence_id)
        if reminder.completed:
            raise LifecycleWriteConflict("This responsibility is already completed.")

        completed_on = payload.completed_on or now.date()
        completed_at = datetime.combine(completed_on, datetime_time.min, tzinfo=timezone.utc)
        previous_due_date = reminder.due_date
        next_due_date: date | None = None
        maintenance_details = reminder.maintenance_details
        renewal_details = reminder.renewal_details
        birthday_details = reminder.birthday_details
        completed = True

        if (
            reminder.reminder_type == ReminderType.MAINTENANCE
            and maintenance_details is not None
            and maintenance_details.interval_value is not None
            and maintenance_details.interval_unit is not None
        ):
            maintenance_details = advance_maintenance_details(maintenance_details, completed_on)
            next_due_date = get_maintenance_due_date(maintenance_details)
            completed = next_due_date is None
        elif reminder.repeat != RepeatOption.NONE:
            next_due_date = advance_due_date(previous_due_date, reminder.repeat, today=now.date())
            if reminder.reminder_type == ReminderType.BIRTHDAY and birthday_details is not None:
                birthday_details = enrich_birthday_details(birthday_details, next_due_date)
            if reminder.reminder_type == ReminderType.RENEWAL and renewal_details is not None:
                renewal_details = advance_renewal_details(renewal_details, previous_due_date, next_due_date)
            completed = False

        update_values: dict[str, object] = {
            **clear_alert_action_state(now),
            "completed": completed,
            "completed_at": completed_at,
            "updated_at": now,
            "version": reminder.version + 1,
            "maintenance_details": maintenance_details,
            "renewal_details": renewal_details,
            "birthday_details": birthday_details,
        }
        if next_due_date is not None:
            update_values["due_date"] = next_due_date
            update_values["current_occurrence_id"] = new_occurrence_id(
                reminder.id,
                next_due_date,
                occurrence_id,
            )
        updated = reminder.model_copy(update=update_values)
        item = self._primary_item(user_id, reminder.id)
        target = resolve_date_target(reminder, item)
        event = new_event(
            reminder=reminder,
            event_type=ResponsibilityEventType.COMPLETED,
            occurred_at=now,
            effective_date=completed_on,
            completed_at=completed_at,
            previous_due_date=previous_due_date,
            next_due_date=next_due_date,
            note=payload.note,
            idempotency_key=operation_key,
            occurrence_id=occurrence_id,
            item=item,
            item_date_sync_key=target.key if target and next_due_date else None,
        )
        saved = self.history_repo.commit_reminder_event(self.reminder_repo, reminder, updated, event)
        return self._finalize(saved, event, sync_item_date=next_due_date is not None)

    def renew(
        self,
        user_id: str,
        reminder: Reminder,
        payload: ReminderRenewRequest,
        *,
        idempotency_key: str | None,
        now: datetime,
    ) -> LifecycleOperationResult:
        occurrence_id = payload.occurrence_id or current_occurrence_id(reminder)
        operation_key = scoped_operation_key("renew", idempotency_key or occurrence_id)
        replay = self._replay(user_id, reminder.id, operation_key)
        if replay:
            return replay
        self._assert_occurrence(reminder, payload.occurrence_id)

        previous_due_date = reminder.due_date
        renewed_on = payload.renewed_on or now.date()
        completed_at = datetime.combine(renewed_on, datetime_time.min, tzinfo=timezone.utc)
        renewal_details = renewal_details_for_new_date(reminder, payload.new_due_date)
        maintenance_details = maintenance_details_for_new_date(reminder, payload.new_due_date, renewed_on)
        next_occurrence = new_occurrence_id(reminder.id, payload.new_due_date, occurrence_id)
        updated = reminder.model_copy(
            update={
                **clear_alert_action_state(now),
                "completed": False,
                "completed_at": completed_at,
                "due_date": payload.new_due_date,
                "renewal_details": renewal_details,
                "maintenance_details": maintenance_details,
                "current_occurrence_id": next_occurrence,
                "updated_at": now,
                "version": reminder.version + 1,
            }
        )
        item = self._primary_item(user_id, reminder.id)
        target = resolve_date_target(reminder, item)
        event = new_event(
            reminder=reminder,
            event_type=ResponsibilityEventType.RENEWED,
            occurred_at=now,
            effective_date=renewed_on,
            completed_at=completed_at,
            previous_due_date=previous_due_date,
            next_due_date=payload.new_due_date,
            note=payload.note,
            idempotency_key=operation_key,
            occurrence_id=occurrence_id,
            item=item,
            item_date_sync_key=target.key if target else None,
        )
        saved = self.history_repo.commit_reminder_event(self.reminder_repo, reminder, updated, event)
        return self._finalize(saved, event, sync_item_date=True)

    def snooze(
        self,
        user_id: str,
        reminder: Reminder,
        snoozed_until: datetime,
        *,
        idempotency_key: str | None,
        now: datetime,
    ) -> LifecycleOperationResult:
        occurrence_id = current_occurrence_id(reminder)
        operation_key = scoped_operation_key(
            "snooze",
            idempotency_key or f"{occurrence_id}:{snoozed_until.astimezone(timezone.utc).isoformat()}",
        )
        replay = self._replay(user_id, reminder.id, operation_key)
        if replay:
            return replay
        updated = reminder.model_copy(
            update={
                **snooze_alert_state(now, snoozed_until),
                "updated_at": now,
                "version": reminder.version + 1,
            }
        )
        item = self._primary_item(user_id, reminder.id)
        event = new_event(
            reminder=reminder,
            event_type=ResponsibilityEventType.SNOOZED,
            occurred_at=now,
            effective_date=snoozed_until.date(),
            previous_due_date=reminder.due_date,
            next_due_date=reminder.due_date,
            idempotency_key=operation_key,
            occurrence_id=occurrence_id,
            item=item,
        )
        saved = self.history_repo.commit_reminder_event(self.reminder_repo, reminder, updated, event)
        return self._finalize(saved, event, sync_item_date=False)

    def clear_snooze(
        self,
        user_id: str,
        reminder: Reminder,
        *,
        idempotency_key: str | None,
        now: datetime,
    ) -> LifecycleOperationResult | None:
        snooze_value = reminder.snoozed_until or reminder.alert_snoozed_until
        if snooze_value is None:
            return None
        occurrence_id = current_occurrence_id(reminder)
        operation_key = scoped_operation_key("clear-snooze", idempotency_key or f"{occurrence_id}:{snooze_value.isoformat()}")
        replay = self._replay(user_id, reminder.id, operation_key)
        if replay:
            return replay
        updated = reminder.model_copy(
            update={
                "snoozed_until": None,
                "alert_snoozed_until": None,
                "alert_last_action_at": now,
                "updated_at": now,
                "version": reminder.version + 1,
            }
        )
        event = new_event(
            reminder=reminder,
            event_type=ResponsibilityEventType.SNOOZE_CLEARED,
            occurred_at=now,
            previous_due_date=reminder.due_date,
            next_due_date=reminder.due_date,
            idempotency_key=operation_key,
            occurrence_id=occurrence_id,
            item=self._primary_item(user_id, reminder.id),
        )
        saved = self.history_repo.commit_reminder_event(self.reminder_repo, reminder, updated, event)
        return self._finalize(saved, event, sync_item_date=False)

    def change_due_date(
        self,
        user_id: str,
        reminder: Reminder,
        updated: Reminder,
        *,
        idempotency_key: str | None,
        now: datetime,
    ) -> LifecycleOperationResult:
        occurrence_id = current_occurrence_id(reminder)
        operation_key = scoped_operation_key(
            "due-date",
            idempotency_key or f"{occurrence_id}:{reminder.due_date.isoformat()}:{updated.due_date.isoformat()}",
        )
        replay = self._replay(user_id, reminder.id, operation_key)
        if replay:
            return replay
        next_occurrence = new_occurrence_id(reminder.id, updated.due_date, occurrence_id)
        versioned = updated.model_copy(
            update={"version": reminder.version + 1, "current_occurrence_id": next_occurrence}
        )
        item = self._primary_item(user_id, reminder.id)
        target = resolve_date_target(reminder, item)
        event = new_event(
            reminder=reminder,
            event_type=ResponsibilityEventType.DUE_DATE_CHANGED,
            occurred_at=now,
            previous_due_date=reminder.due_date,
            next_due_date=versioned.due_date,
            idempotency_key=operation_key,
            occurrence_id=occurrence_id,
            item=item,
            item_date_sync_key=target.key if target else None,
        )
        saved = self.history_repo.commit_reminder_event(self.reminder_repo, reminder, versioned, event)
        return self._finalize(saved, event, sync_item_date=True)

    def reopen(
        self,
        user_id: str,
        reminder: Reminder,
        *,
        occurrence_id: str | None,
        idempotency_key: str | None,
        now: datetime,
    ) -> LifecycleOperationResult:
        completed_occurrence = occurrence_id or current_occurrence_id(reminder)
        operation_key = scoped_operation_key("reopen", idempotency_key or completed_occurrence)
        replay = self._replay(user_id, reminder.id, operation_key)
        if replay:
            return replay
        self._assert_occurrence(reminder, occurrence_id)
        if not reminder.completed or reminder.repeat != RepeatOption.NONE:
            raise LifecycleWriteConflict("Only a completed non-recurring responsibility can be reopened.")
        next_occurrence = new_occurrence_id(reminder.id, reminder.due_date, f"reopen:{completed_occurrence}")
        updated = reminder.model_copy(
            update={
                "completed": False,
                "completed_at": None,
                "current_occurrence_id": next_occurrence,
                "updated_at": now,
                "version": reminder.version + 1,
            }
        )
        event = new_event(
            reminder=reminder,
            event_type=ResponsibilityEventType.REOPENED,
            occurred_at=now,
            previous_due_date=reminder.due_date,
            next_due_date=reminder.due_date,
            idempotency_key=operation_key,
            occurrence_id=completed_occurrence,
            item=self._primary_item(user_id, reminder.id),
        )
        saved = self.history_repo.commit_reminder_event(self.reminder_repo, reminder, updated, event)
        return self._finalize(saved, event, sync_item_date=False)

    def attach_evidence(
        self,
        user_id: str,
        reminder: Reminder,
        payload: ResponsibilityEvidenceRequest,
        *,
        idempotency_key: str | None,
        now: datetime,
    ) -> ResponsibilityEvent:
        item = self._require_item(user_id, payload.record_id)
        if not self._item_is_connected(user_id, reminder.id, item.id):
            raise LifecycleWriteConflict("The document item is not connected to this responsibility.")
        attachment = self.attachment_repo.get_attachment(user_id, item.id, payload.document_id)
        if attachment is None or attachment.status in {
            AttachmentStatus.REJECTED,
            AttachmentStatus.SCAN_FAILED,
            AttachmentStatus.DELETING,
            AttachmentStatus.DELETED,
        }:
            raise LifecycleWriteConflict("The supporting document is unavailable or was rejected.")
        if payload.related_event_id:
            related = self.history_repo.get_event(user_id, payload.related_event_id)
            if related is None or related.reminder_id != reminder.id:
                raise LifecycleWriteConflict("The related lifecycle entry was not found.")
        operation_key = scoped_operation_key(
            "evidence",
            idempotency_key or f"{payload.related_event_id or payload.occurrence_id or current_occurrence_id(reminder)}:{payload.document_id}",
        )
        existing = self.history_repo.get_by_idempotency(user_id, operation_key)
        if existing:
            if existing.reminder_id != reminder.id:
                raise LifecycleWriteConflict("That operation key belongs to another responsibility.")
            return existing
        event = new_event(
            reminder=reminder,
            event_type=ResponsibilityEventType.SUPPORTING_DOCUMENT_ADDED,
            occurred_at=now,
            idempotency_key=operation_key,
            occurrence_id=payload.occurrence_id or current_occurrence_id(reminder),
            item=item,
            related_document_ids=[payload.document_id],
            related_event_id=payload.related_event_id,
            document_reference_status=LifecycleReconciliationStatus.PENDING,
        )
        self.history_repo.append_event(event)
        finalized = self._finalize(reminder, event, sync_item_date=False)
        return finalized.event

    def reconcile_reminder(
        self,
        user_id: str,
        reminder: Reminder,
        *,
        dry_run: bool = False,
    ) -> LifecycleReconciliationResult:
        events: list[ResponsibilityEvent] = []
        cursor: str | None = None
        while len(events) < 250:
            page, cursor = self.history_repo.list_for_reminder(user_id, reminder.id, limit=50, cursor=cursor)
            events.extend(page)
            if not cursor:
                break
        pending = [
            event
            for event in events
            if event.reconciliation_status != LifecycleReconciliationStatus.CONSISTENT
            or event.search_sync_status != LifecycleReconciliationStatus.CONSISTENT
            or event.document_reference_status != LifecycleReconciliationStatus.CONSISTENT
        ]
        results: list[str] = []
        repaired = 0
        remaining = 0
        for event in pending:
            if dry_run:
                results.append(f"{event.event_id}: would reconcile")
                remaining += 1
                continue
            sync_item = event.item_date_sync_key is not None and event.next_due_date is not None
            result = self._finalize(reminder, event, sync_item_date=sync_item, idempotent_replay=True)
            if result.reconciliation_status == LifecycleReconciliationStatus.CONSISTENT:
                repaired += 1
                results.append(f"{event.event_id}: consistent")
            else:
                remaining += 1
                results.append(f"{event.event_id}: needs attention")
        return LifecycleReconciliationResult(
            reminder_id=reminder.id,
            dry_run=dry_run,
            inspected=len(pending),
            repaired=repaired,
            remaining=remaining,
            results=results,
        )

    def _finalize(
        self,
        reminder: Reminder,
        event: ResponsibilityEvent,
        *,
        sync_item_date: bool,
        idempotent_replay: bool = False,
    ) -> LifecycleOperationResult:
        started = time.perf_counter()
        reconciliation_status = LifecycleReconciliationStatus.CONSISTENT
        search_status = LifecycleReconciliationStatus.CONSISTENT
        document_status = event.document_reference_status
        item = self.record_repo.get_record(event.user_id, event.item_id) if event.item_id else None
        if sync_item_date and event.next_due_date and event.previous_due_date and item:
            target = resolve_date_target_for_key(event.item_date_sync_key) or resolve_date_target(reminder, item)
            try:
                if target:
                    item = synchronize_item_date(
                        self.record_repo,
                        item,
                        target,
                        previous_due_date=event.previous_due_date,
                        next_due_date=event.next_due_date,
                        now=datetime.now(timezone.utc),
                    )
                else:
                    reconciliation_status = LifecycleReconciliationStatus.NEEDS_ATTENTION
            except Exception:
                logger.exception(
                    "responsibility_item_date_sync_failed",
                    extra={
                        "reminder_id": reminder.id,
                        "item_id": event.item_id,
                        "event_id": event.event_id,
                        "correlation_id": event.correlation_id,
                    },
                )
                reconciliation_status = LifecycleReconciliationStatus.NEEDS_ATTENTION
        elif sync_item_date and event.item_id:
            reconciliation_status = LifecycleReconciliationStatus.NEEDS_ATTENTION

        if event.related_document_ids:
            document_status = self._document_status(event)
            if document_status == LifecycleReconciliationStatus.NEEDS_ATTENTION:
                reconciliation_status = LifecycleReconciliationStatus.NEEDS_ATTENTION
            elif document_status == LifecycleReconciliationStatus.PENDING:
                reconciliation_status = LifecycleReconciliationStatus.PENDING

        try:
            self.search_service.sync_entity_observed(
                event.user_id,
                LinkedEntityType.REMINDER,
                reminder.id,
                operation="responsibility_lifecycle",
            )
            if item:
                self.search_service.sync_entity_observed(
                    event.user_id,
                    LinkedEntityType.RECORD,
                    item.id,
                    operation="responsibility_lifecycle_item",
                )
        except Exception:
            search_status = LifecycleReconciliationStatus.NEEDS_ATTENTION
            reconciliation_status = LifecycleReconciliationStatus.NEEDS_ATTENTION

        try:
            event = self.history_repo.update_operation_status(
                event,
                reconciliation_status=reconciliation_status,
                search_sync_status=search_status,
                document_reference_status=document_status,
            )
        except Exception:
            logger.exception(
                "responsibility_history_status_update_failed",
                extra={"reminder_id": reminder.id, "event_id": event.event_id, "correlation_id": event.correlation_id},
            )
            reconciliation_status = LifecycleReconciliationStatus.NEEDS_ATTENTION

        logger.info(
            "responsibility_lifecycle_operation",
            extra={
                "lifecycle_operation": event.event_type.value,
                "event_type": event.event_type.value,
                "reminder_id": reminder.id,
                "item_id": event.item_id,
                "occurrence_id": event.occurrence_id,
                "result": reconciliation_status.value,
                "idempotent_replay": idempotent_replay,
                "reconciliation_status": reconciliation_status.value,
                "document_reference_status": document_status.value,
                "search_sync_status": search_status.value,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "correlation_id": event.correlation_id,
            },
        )
        return LifecycleOperationResult(
            reminder=reminder,
            event=event,
            reconciliation_status=reconciliation_status,
            idempotent_replay=idempotent_replay,
        )

    def _document_status(self, event: ResponsibilityEvent) -> LifecycleReconciliationStatus:
        if not event.item_id:
            return LifecycleReconciliationStatus.NEEDS_ATTENTION
        for document_id in event.related_document_ids:
            attachment = self.attachment_repo.get_attachment(event.user_id, event.item_id, document_id)
            if attachment is None or attachment.status in {
                AttachmentStatus.REJECTED,
                AttachmentStatus.SCAN_FAILED,
                AttachmentStatus.DELETING,
                AttachmentStatus.DELETED,
            }:
                return LifecycleReconciliationStatus.NEEDS_ATTENTION
            if attachment.status != AttachmentStatus.AVAILABLE:
                return LifecycleReconciliationStatus.PENDING
        return LifecycleReconciliationStatus.CONSISTENT

    def _replay(self, user_id: str, reminder_id: str, operation_key: str) -> LifecycleOperationResult | None:
        event = self.history_repo.get_by_idempotency(user_id, operation_key)
        if event is None:
            return None
        if event.reminder_id != reminder_id:
            raise LifecycleWriteConflict("That operation key belongs to another responsibility.")
        current = self.reminder_repo.get_reminder(user_id, reminder_id)
        if current is None:
            raise LifecycleWriteConflict("The responsibility no longer exists.")
        return LifecycleOperationResult(
            reminder=current,
            event=event,
            reconciliation_status=event.reconciliation_status,
            idempotent_replay=True,
        )

    def _assert_occurrence(self, reminder: Reminder, supplied: str | None) -> None:
        if supplied and supplied != current_occurrence_id(reminder):
            raise LifecycleWriteConflict("This responsibility cycle has already changed. Refresh and try again.")

    def _require_item(self, user_id: str, item_id: str) -> Record:
        item = self.record_repo.get_record(user_id, item_id)
        if item is None:
            raise LifecycleWriteConflict("Connected item not found.")
        return item

    def _primary_item(self, user_id: str, reminder_id: str) -> Record | None:
        links = sorted(
            self.linked_repo.list_links_for_entity(user_id, LinkedEntityType.REMINDER, reminder_id),
            key=lambda link: link.created_at,
        )
        for link in links:
            record_id = None
            if link.source_type == LinkedEntityType.RECORD and link.target_type == LinkedEntityType.REMINDER:
                record_id = link.source_id
            elif link.target_type == LinkedEntityType.RECORD and link.source_type == LinkedEntityType.REMINDER:
                record_id = link.target_id
            if record_id:
                record = self.record_repo.get_record(user_id, record_id)
                if record and record.status.value != "archived":
                    return record
        return None

    def _item_is_connected(self, user_id: str, reminder_id: str, item_id: str) -> bool:
        return any(
            {
                (link.source_type, link.source_id),
                (link.target_type, link.target_id),
            }
            == {
                (LinkedEntityType.REMINDER, reminder_id),
                (LinkedEntityType.RECORD, item_id),
            }
            for link in self.linked_repo.list_links_for_entity(user_id, LinkedEntityType.REMINDER, reminder_id)
        )


def new_event(
    *,
    reminder: Reminder,
    event_type: ResponsibilityEventType,
    occurred_at: datetime,
    idempotency_key: str,
    occurrence_id: str | None,
    item: Record | None,
    effective_date: date | None = None,
    previous_due_date: date | None = None,
    next_due_date: date | None = None,
    completed_at: datetime | None = None,
    note: str | None = None,
    source: ResponsibilityEventSource = ResponsibilityEventSource.USER,
    item_date_sync_key: str | None = None,
    related_document_ids: list[str] | None = None,
    related_event_id: str | None = None,
    document_reference_status: LifecycleReconciliationStatus = LifecycleReconciliationStatus.CONSISTENT,
) -> ResponsibilityEvent:
    correlation_id = idempotency_key.split(":", 1)[-1].split(":", 1)[0] or str(uuid4())
    event_id = str(uuid5(NAMESPACE_URL, f"lifeledger:responsibility-event:{reminder.user_id}:{idempotency_key}"))
    return ResponsibilityEvent(
        event_id=event_id,
        user_id=reminder.user_id,
        reminder_id=reminder.id,
        item_id=item.id if item else None,
        occurrence_id=occurrence_id,
        event_type=event_type,
        occurred_at=occurred_at,
        effective_date=effective_date,
        previous_due_date=previous_due_date,
        next_due_date=next_due_date,
        completed_at=completed_at,
        note=note,
        related_document_ids=related_document_ids or [],
        related_event_id=related_event_id,
        source=source,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
        created_at=occurred_at,
        responsibility_title_snapshot=reminder.title,
        item_title_snapshot=item.title if item else None,
        item_type_snapshot=item.record_type if item else None,
        item_date_sync_key=item_date_sync_key,
        document_reference_status=document_reference_status,
    )


def scoped_operation_key(operation: str, key: str) -> str:
    normalized = key.strip()[:200]
    if not normalized:
        normalized = str(uuid4())
    return f"{operation}:{normalized}"


def current_occurrence_id(reminder: Reminder) -> str:
    return reminder.current_occurrence_id or new_occurrence_id(reminder.id, reminder.due_date, "legacy")


def new_occurrence_id(reminder_id: str, due_date: date, seed: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"lifeledger:occurrence:{reminder_id}:{due_date.isoformat()}:{seed}"))


def renewal_details_for_new_date(reminder: Reminder, new_due_date: date) -> RenewalDetails | None:
    details = reminder.renewal_details
    if reminder.reminder_type != ReminderType.RENEWAL or details is None:
        return details
    data = details.model_dump()
    if getattr(details.renewal_kind, "value", None) == "expiration":
        data["expiration_date"] = new_due_date
    else:
        data["renewal_date"] = new_due_date
    return RenewalDetails.model_validate(data)


def maintenance_details_for_new_date(
    reminder: Reminder,
    new_due_date: date,
    completed_on: date,
) -> MaintenanceDetails | None:
    details = reminder.maintenance_details
    if reminder.reminder_type != ReminderType.MAINTENANCE or details is None:
        return details
    data = details.model_dump()
    data["last_completed_date"] = completed_on
    data["next_due_date"] = new_due_date
    return MaintenanceDetails.model_validate(data)
