from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib

from app.capture_models import ActionProposal, ActionResultStatus, ActionType, Capture, CaptureStatus, ProposalStatus
from app.reconciliation import ReconciliationDomain, ReconciliationSeverity
from app.reconciliation_service import ReconciliationService
from app.relationship_service import ItemResolver, document_item_id
from app.schemas import AttachmentStatus, LifecycleReconciliationStatus, LinkedEntityType, RecordStatus, ResponsibilityEventType
from app.responsibility_lifecycle_service import new_occurrence_id
from app.responsibility_sync import current_item_date, resolve_date_target_for_key
from app.search_service import (
    SEARCH_PROJECTION_VERSION,
    document_search_item_id,
    record_search_item_id,
    reminder_search_item_id,
)


class ReconciliationDetector:
    def __init__(
        self,
        service: ReconciliationService,
        records,
        reminders,
        history,
        attachments,
        relationships,
        search,
        document_storage=None,
        assistant=None,
    ):
        self.service = service
        self.records = records
        self.reminders = reminders
        self.history = history
        self.attachments = attachments
        self.relationships = relationships
        self.search = search
        self.document_storage = document_storage
        self.assistant = assistant

    def detect_user(self, user_id: str, *, limit: int = 100, now: datetime | None = None) -> int:
        if limit < 1 or limit > 500:
            raise ValueError("Detection limit must be between 1 and 500.")
        current = _utc(now or datetime.now(timezone.utc))
        detected = 0
        records = self.records.list_records(user_id, include_archived=True, limit=limit)
        reminders = self.reminders.list_reminders(user_id, limit=limit)
        attachments = self.attachments.list_for_user(user_id, limit=limit)
        links = self.relationships.list_for_user(user_id, limit=limit)
        events = self.history.list_for_user(user_id, limit=limit)
        resolver = ItemResolver(self.records, self.reminders, self.attachments)

        for record in records:
            projection_id = record_search_item_id(record.id)
            projection = self.search.get_projection(user_id, projection_id)
            detected += self._check_projection(
                user_id,
                LinkedEntityType.RECORD,
                record.id,
                projection,
                archived=record.status == RecordStatus.ARCHIVED,
                has_links=bool(self.relationships.list_links_for_entity(user_id, LinkedEntityType.RECORD, record.id)),
                now=current,
            )

        for reminder in reminders:
            projection = self.search.get_projection(user_id, reminder_search_item_id(reminder.id))
            detected += self._check_projection(
                user_id,
                LinkedEntityType.REMINDER,
                reminder.id,
                projection,
                archived=reminder.archived_at is not None,
                has_links=bool(self.relationships.list_links_for_entity(user_id, LinkedEntityType.REMINDER, reminder.id)),
                now=current,
            )
            if hasattr(self.history, "list_for_reminder"):
                reminder_events, _ = self.history.list_for_reminder(
                    user_id,
                    reminder.id,
                    limit=1,
                )
            else:
                reminder_events = [event for event in events if event.reminder_id == reminder.id]
            expected_occurrence = _expected_occurrence(reminder, reminder_events)
            if (
                reminder.current_occurrence_id
                and reminder_events
                and reminder.current_occurrence_id != expected_occurrence
            ):
                detected += self._detect(
                    user_id,
                    ReconciliationDomain.LIFECYCLE,
                    "reminder",
                    reminder.id,
                    "occurrence_state_mismatch",
                    ReconciliationSeverity.HIGH,
                    False,
                    current,
                )

        for attachment in attachments:
            document_id = document_item_id(attachment.record_id, attachment.attachment_id)
            projection = self.search.get_projection(
                user_id, document_search_item_id(attachment.record_id, attachment.attachment_id)
            )
            if attachment.status == AttachmentStatus.AVAILABLE and projection is None:
                detected += self._detect(
                    user_id,
                    ReconciliationDomain.SEARCH,
                    LinkedEntityType.DOCUMENT.value,
                    document_id,
                    "missing_document_projection",
                    ReconciliationSeverity.MEDIUM,
                    True,
                    current,
                )
            if attachment.status in {AttachmentStatus.REJECTED, AttachmentStatus.SCAN_FAILED} and projection is not None:
                detected += self._detect(
                    user_id,
                    ReconciliationDomain.DOCUMENT,
                    "attachment",
                    attachment.attachment_id,
                    "rejected_document_projected_as_usable",
                    ReconciliationSeverity.HIGH,
                    True,
                    current,
                )
            age = current - _utc(attachment.created_at)
            if attachment.status == AttachmentStatus.PENDING_UPLOAD and age > timedelta(minutes=15):
                detected += self._detect(
                    user_id,
                    ReconciliationDomain.DOCUMENT,
                    "attachment",
                    attachment.attachment_id,
                    "upload_intent_incomplete",
                    ReconciliationSeverity.LOW,
                    False,
                    current,
                )
            if attachment.status in {AttachmentStatus.UPLOADED, AttachmentStatus.SCANNING} and age > timedelta(minutes=30):
                detected += self._detect(
                    user_id,
                    ReconciliationDomain.DOCUMENT,
                    "attachment",
                    attachment.attachment_id,
                    "stuck_scanning",
                    ReconciliationSeverity.HIGH,
                    True,
                    current,
                )
            if (
                attachment.status in {AttachmentStatus.UPLOADED, AttachmentStatus.SCANNING}
                and attachment.quarantine_object_key
                and self.document_storage is not None
            ):
                try:
                    self.document_storage.head_quarantine_object(attachment.quarantine_object_key)
                except Exception:
                    detected += self._detect(
                        user_id,
                        ReconciliationDomain.DOCUMENT,
                        "attachment",
                        attachment.attachment_id,
                        "attachment_object_missing",
                        ReconciliationSeverity.CRITICAL,
                        False,
                        current,
                    )
            if attachment.status == AttachmentStatus.AVAILABLE and not attachment.clean_object_key:
                detected += self._detect(
                    user_id,
                    ReconciliationDomain.DOCUMENT,
                    "attachment",
                    attachment.attachment_id,
                    "clean_object_reference_missing",
                    ReconciliationSeverity.CRITICAL,
                    False,
                    current,
                )
            if (
                attachment.status == AttachmentStatus.AVAILABLE
                and attachment.clean_object_key
                and self.document_storage is not None
            ):
                try:
                    self.document_storage.head_clean_object(attachment.clean_object_key)
                except Exception:
                    detected += self._detect(
                        user_id,
                        ReconciliationDomain.DOCUMENT,
                        "attachment",
                        attachment.attachment_id,
                        "clean_object_missing",
                        ReconciliationSeverity.CRITICAL,
                        False,
                        current,
                    )

        if (
            len(attachments) < limit
            and self.document_storage is not None
            and hasattr(self.document_storage, "list_user_objects")
        ):
            referenced_keys = {
                key
                for attachment in attachments
                for key in (attachment.quarantine_object_key, attachment.clean_object_key)
                if key
            }
            try:
                stored_objects = self.document_storage.list_user_objects(user_id, limit=limit)
            except Exception:
                stored_objects = []
            for _object_class, key in stored_objects:
                if key not in referenced_keys:
                    detected += self._detect(
                        user_id,
                        ReconciliationDomain.DOCUMENT,
                        "document_object",
                        hashlib.sha256(key.encode("utf-8")).hexdigest(),
                        "orphaned_user_object",
                        ReconciliationSeverity.HIGH,
                        False,
                        current,
                    )

        pair_keys = set()
        for link in links:
            if link.canonical_pair_key in pair_keys:
                detected += self._detect(
                    user_id,
                    ReconciliationDomain.RELATIONSHIP,
                    "relationship",
                    link.link_id,
                    "duplicate_relationship",
                    ReconciliationSeverity.MEDIUM,
                    False,
                    current,
                )
            pair_keys.add(link.canonical_pair_key)
            if resolver.resolve_summary(user_id, link.source_type, link.source_id) is None or resolver.resolve_summary(
                user_id, link.target_type, link.target_id
            ) is None:
                detected += self._detect(
                    user_id,
                    ReconciliationDomain.RELATIONSHIP,
                    "relationship",
                    link.link_id,
                    "orphaned_relationship",
                    ReconciliationSeverity.HIGH,
                    False,
                    current,
                )

        for event in events:
            if event.reconciliation_status != LifecycleReconciliationStatus.CONSISTENT:
                detected += self._detect(
                    user_id,
                    ReconciliationDomain.LIFECYCLE,
                    "responsibility_event",
                    event.event_id,
                    "lifecycle_reconciliation_flag",
                    ReconciliationSeverity.HIGH,
                    True,
                    current,
                )
            if event.search_sync_status != LifecycleReconciliationStatus.CONSISTENT:
                detected += self._detect(
                    user_id,
                    ReconciliationDomain.SEARCH,
                    "reminder",
                    event.reminder_id,
                    "projection_sync_failure",
                    ReconciliationSeverity.HIGH,
                    True,
                    current,
                )
            if event.document_reference_status != LifecycleReconciliationStatus.CONSISTENT:
                detected += self._detect(
                    user_id,
                    ReconciliationDomain.LIFECYCLE,
                    "responsibility_event",
                    event.event_id,
                    "evidence_document_unavailable",
                    ReconciliationSeverity.MEDIUM,
                    False,
                    current,
                )
            if event.item_id:
                for document_id in event.related_document_ids:
                    evidence = self.attachments.get_attachment(user_id, event.item_id, document_id)
                    if evidence is None or evidence.status not in {
                        AttachmentStatus.PENDING_UPLOAD,
                        AttachmentStatus.UPLOADED,
                        AttachmentStatus.SCANNING,
                        AttachmentStatus.AVAILABLE,
                    }:
                        detected += self._detect(
                            user_id,
                            ReconciliationDomain.LIFECYCLE,
                            "responsibility_event",
                            event.event_id,
                            "evidence_document_unavailable",
                            ReconciliationSeverity.MEDIUM,
                            False,
                            current,
                        )

        latest_item_sync = {}
        for event in events:
            if event.item_id and event.item_date_sync_key and event.next_due_date:
                key = (event.item_id, event.item_date_sync_key)
                if key not in latest_item_sync or event.occurred_at > latest_item_sync[key].occurred_at:
                    latest_item_sync[key] = event
        for (item_id, sync_key), event in latest_item_sync.items():
            item = self.records.get_record(user_id, item_id)
            target = resolve_date_target_for_key(sync_key)
            if item is not None and target is not None and current_item_date(item, target) != event.next_due_date:
                detected += self._detect(
                    user_id,
                    ReconciliationDomain.ITEM_SYNC,
                    "responsibility_event",
                    event.event_id,
                    "accepted_item_date_mismatch",
                    ReconciliationSeverity.HIGH,
                    True,
                    current,
                )

        expected = {
            *(record_search_item_id(item.id) for item in records),
            *(reminder_search_item_id(item.id) for item in reminders),
            *(
                document_search_item_id(item.record_id, item.attachment_id)
                for item in attachments
                if item.status == AttachmentStatus.AVAILABLE
            ),
        }
        source_scan_complete = all(len(items) < limit for items in (records, reminders, attachments))
        if source_scan_complete:
            for projection_id in self.search.list_projection_ids_for_user(user_id, limit * 3):
                if projection_id not in expected:
                    detected += self._detect(
                        user_id,
                        ReconciliationDomain.SEARCH,
                        "search_projection",
                        projection_id,
                        "orphaned_projection",
                        ReconciliationSeverity.MEDIUM,
                        True,
                        current,
                    )
        if self.assistant is not None:
            detected += self._detect_capture_state(user_id, limit=limit, now=current)
        return detected

    def _detect_capture_state(self, user_id: str, *, limit: int, now: datetime) -> int:
        detected = 0
        captures = [
            Capture.model_validate(item)
            for item in self.assistant.list_entity_rows(user_id, "capture", limit=limit)
        ]
        proposals = [
            ActionProposal.model_validate(item)
            for item in self.assistant.list_entity_rows(user_id, "proposal", limit=limit)
        ]
        for capture in captures:
            if capture.status == CaptureStatus.INTERPRETING and now - _utc(capture.updated_at) > timedelta(minutes=10):
                detected += self._detect(
                    user_id, ReconciliationDomain.CAPTURE, "capture", capture.capture_id,
                    "stuck_interpreting", ReconciliationSeverity.MEDIUM, False, now,
                )
        executable = {
            ProposalStatus.READY_FOR_REVIEW,
            ProposalStatus.APPROVED,
            ProposalStatus.EXECUTING,
            ProposalStatus.PARTIALLY_COMPLETED,
            ProposalStatus.FAILED,
        }
        for proposal in proposals:
            if proposal.status == ProposalStatus.EXECUTING and now - _utc(proposal.updated_at) > timedelta(minutes=10):
                detected += self._detect(
                    user_id, ReconciliationDomain.CAPTURE, "proposal", proposal.proposal_id,
                    "stuck_executing", ReconciliationSeverity.HIGH, True, now,
                )
            if proposal.status == ProposalStatus.PARTIALLY_COMPLETED:
                detected += self._detect(
                    user_id, ReconciliationDomain.CAPTURE, "proposal", proposal.proposal_id,
                    "partial_action_execution", ReconciliationSeverity.HIGH, True, now,
                )
            completed_results = [
                item for item in proposal.action_results if item.status == ActionResultStatus.COMPLETED
            ]
            if (
                proposal.status in {ProposalStatus.APPROVED, ProposalStatus.EXECUTING}
                and len(proposal.action_results) < len(proposal.proposed_actions)
                and now - _utc(proposal.updated_at) > timedelta(minutes=10)
            ):
                detected += self._detect(
                    user_id, ReconciliationDomain.CAPTURE, "proposal", proposal.proposal_id,
                    "approved_proposal_missing_action_result", ReconciliationSeverity.HIGH, True, now,
                )
            if (
                proposal.proposed_actions
                and len(completed_results) == len(proposal.proposed_actions)
                and proposal.status != ProposalStatus.COMPLETED
            ):
                detected += self._detect(
                    user_id, ReconciliationDomain.CAPTURE, "proposal", proposal.proposal_id,
                    "proposal_status_stale_after_results", ReconciliationSeverity.HIGH, True, now,
                )
            for result in completed_results:
                if result.resulting_entity_id and not self._capture_result_exists(user_id, result):
                    detected += self._detect(
                        user_id, ReconciliationDomain.CAPTURE, "action_result", result.action_id,
                        "missing_linked_result_after_action", ReconciliationSeverity.HIGH, False, now,
                    )
            if proposal.expires_at <= now and proposal.status in executable:
                detected += self._detect(
                    user_id, ReconciliationDomain.CAPTURE, "proposal", proposal.proposal_id,
                    "expired_proposal_executable", ReconciliationSeverity.MEDIUM, False, now,
                )
            if proposal.status == ProposalStatus.COMPLETED and len(proposal.action_results) < len(proposal.proposed_actions):
                detected += self._detect(
                    user_id, ReconciliationDomain.CAPTURE, "proposal", proposal.proposal_id,
                    "completed_proposal_missing_result", ReconciliationSeverity.HIGH, False, now,
                )
        usage = self.assistant.list_entity_rows(user_id, "usage", limit=limit)
        request_ids: set[str] = set()
        for item in usage:
            request_id = str(item.get("provider_request_id") or "")
            if request_id and request_id in request_ids:
                detected += self._detect(
                    user_id, ReconciliationDomain.CAPTURE, "ai_usage", request_id,
                    "provider_request_charged_twice", ReconciliationSeverity.HIGH, False, now,
                )
            request_ids.add(request_id)
        return detected

    def _capture_result_exists(self, user_id: str, result) -> bool:
        if result.action_type in {
            ActionType.CREATE_ITEM,
            ActionType.UPDATE_ITEM_DETAIL,
            ActionType.ADD_SAFE_NOTE,
        }:
            return self.records.get_record(user_id, result.resulting_entity_id) is not None
        if result.action_type in {
            ActionType.CREATE_RESPONSIBILITY,
            ActionType.COMPLETE_RESPONSIBILITY,
            ActionType.RENEW_RESPONSIBILITY,
            ActionType.SNOOZE_RESPONSIBILITY,
        }:
            return self.reminders.get_reminder(user_id, result.resulting_entity_id) is not None
        if result.action_type == ActionType.CREATE_RELATIONSHIP:
            return self.relationships.get_link(user_id, result.resulting_entity_id) is not None
        return True

    def _check_projection(self, user_id, entity_type, entity_id, projection, *, archived, has_links, now):
        if projection is None:
            return self._detect(
                user_id,
                ReconciliationDomain.SEARCH,
                entity_type.value,
                entity_id,
                "missing_projection",
                ReconciliationSeverity.MEDIUM,
                True,
                now,
            )
        detected = 0
        if projection.projection_version != SEARCH_PROJECTION_VERSION:
            detected += self._detect(
                user_id, ReconciliationDomain.SEARCH, entity_type.value, entity_id,
                "stale_projection_version", ReconciliationSeverity.MEDIUM, True, now,
            )
        if projection.archived != archived:
            detected += self._detect(
                user_id, ReconciliationDomain.SEARCH, entity_type.value, entity_id,
                "incorrect_archived_status", ReconciliationSeverity.MEDIUM, True, now,
            )
        if projection.has_linked_items != has_links:
            detected += self._detect(
                user_id, ReconciliationDomain.SEARCH, entity_type.value, entity_id,
                "missing_linked_context", ReconciliationSeverity.MEDIUM, True, now,
            )
        return detected

    def _detect(self, user_id, domain, entity_type, entity_id, issue_type, severity, retryable, now):
        _, created = self.service.detect(
            user_id=user_id,
            domain=domain,
            entity_type=entity_type,
            entity_id=entity_id,
            issue_type=issue_type,
            severity=severity,
            retryable=retryable,
            now=now,
        )
        return int(created)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _expected_occurrence(reminder, events):
    if not events:
        return None
    latest = max(events, key=lambda item: (item.occurred_at, item.event_id))
    if latest.event_type in {
        ResponsibilityEventType.COMPLETED,
        ResponsibilityEventType.RENEWED,
        ResponsibilityEventType.DUE_DATE_CHANGED,
    } and latest.next_due_date:
        return new_occurrence_id(reminder.id, latest.next_due_date, latest.occurrence_id or "legacy")
    if latest.event_type == ResponsibilityEventType.REOPENED:
        return new_occurrence_id(
            reminder.id,
            reminder.due_date,
            f"reopen:{latest.occurrence_id or 'legacy'}",
        )
    return latest.occurrence_id
