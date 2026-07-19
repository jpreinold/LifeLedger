from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from app.reconciliation import ReconciliationDomain, ReconciliationSeverity, ReconciliationStatus
from app.reconciliation_repository import LocalReconciliationRepository
from app.reconciliation_service import ReconciliationService
from app.reconciliation_detector import ReconciliationDetector, _expected_occurrence
from app.responsibility_lifecycle_service import new_occurrence_id
from app.models import Record, RecordAttachment
from app.schemas import AttachmentStatus, RecordStatus, RecordType, ResponsibilityEventType


NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)


def make_service(tmp_path, repairers=None, **overrides):
    repository = LocalReconciliationRepository(tmp_path / "reconciliation.json")
    service = ReconciliationService(repository, repairers=repairers, **overrides)
    return service, repository


def detect(service, *, user_id="user-a", entity_id="record-1", issue_type="missing_projection"):
    return service.detect(
        user_id=user_id,
        domain=ReconciliationDomain.SEARCH,
        entity_type="record",
        entity_id=entity_id,
        issue_type=issue_type,
        severity=ReconciliationSeverity.HIGH,
        now=NOW,
    )


def test_missing_projection_creates_one_durable_issue_and_duplicate_detection_is_idempotent(tmp_path):
    service, repository = make_service(tmp_path)

    first, first_created = detect(service)
    second, second_created = detect(service)

    assert first_created is True
    assert second_created is False
    assert second.reconciliation_id == first.reconciliation_id
    assert repository.list_by_status(ReconciliationStatus.PENDING) == [first]


def test_due_issue_is_retried_and_remains_resolved(tmp_path):
    calls = []

    def repair(issue):
        calls.append(issue.reconciliation_id)
        return "Projection rebuilt and verified."

    service, repository = make_service(
        tmp_path,
        {(ReconciliationDomain.SEARCH, "missing_projection"): repair},
    )
    issue, _ = detect(service)

    first = service.retry_one(issue.reconciliation_id, now=NOW)
    second = service.retry_one(issue.reconciliation_id, now=NOW + timedelta(hours=1))

    assert first.status == ReconciliationStatus.RESOLVED
    assert second.status == ReconciliationStatus.RESOLVED
    assert calls == [issue.reconciliation_id]
    assert repository.get(issue.reconciliation_id).expires_at is not None


def test_persistent_failure_escalates_after_bounded_attempts(tmp_path):
    def fail(_issue):
        raise RuntimeError("private payload must never be persisted")

    service, _ = make_service(
        tmp_path,
        {(ReconciliationDomain.SEARCH, "missing_projection"): fail},
        max_attempts=2,
        base_backoff_seconds=1,
    )
    issue, _ = detect(service)

    first = service.retry_one(issue.reconciliation_id, now=NOW)
    second = service.retry_one(issue.reconciliation_id, now=NOW + timedelta(seconds=2))

    assert first.status == ReconciliationStatus.RETRYING
    assert second.status == ReconciliationStatus.REQUIRES_ATTENTION
    assert second.next_retry_at is None
    assert "private payload" not in (second.resolution or "")


def test_dry_run_is_bounded_and_does_not_mutate(tmp_path):
    service, repository = make_service(tmp_path)
    for index in range(3):
        detect(service, entity_id=f"record-{index}")

    result = service.process_due(now=NOW, limit=2, dry_run=True)

    assert result.model_dump() == {
        "considered": 2,
        "attempted": 0,
        "resolved": 0,
        "failed": 0,
        "requires_attention": 0,
        "dry_run": True,
    }
    assert len(repository.list_by_status(ReconciliationStatus.PENDING)) == 3


def test_one_failed_issue_does_not_block_the_batch(tmp_path):
    def repair(issue):
        if issue.entity_id == "bad":
            raise RuntimeError("failure")
        return "Projection rebuilt."

    service, repository = make_service(
        tmp_path,
        {(ReconciliationDomain.SEARCH, "missing_projection"): repair},
    )
    detect(service, entity_id="bad")
    good, _ = detect(service, entity_id="good")

    result = service.process_due(now=NOW, limit=10)

    assert result.considered == 2
    assert result.failed == 1
    assert result.resolved == 1
    assert repository.get(good.reconciliation_id).status == ReconciliationStatus.RESOLVED


def test_user_scoped_queries_and_retry_cannot_cross_users(tmp_path):
    service, repository = make_service(tmp_path)
    first, _ = detect(service, user_id="user-a")
    detect(service, user_id="user-b")

    assert [issue.user_id for issue in repository.list_by_user("user-a")] == ["user-a"]
    try:
        service.retry_one(first.reconciliation_id, expected_user_id="user-b", now=NOW)
    except KeyError:
        pass
    else:
        raise AssertionError("Cross-user retry should not be allowed")


def test_user_issue_pagination_uses_an_opaque_existing_issue_cursor(tmp_path):
    service, repository = make_service(tmp_path)
    for index in range(3):
        detect(service, entity_id=f"record-{index}")
    first_page = repository.list_by_user("user-a", limit=2)
    second_page = repository.list_by_user(
        "user-a", limit=2, cursor=first_page[-1].reconciliation_id
    )

    assert len(first_page) == 2
    assert len(second_page) == 1
    assert second_page[0].reconciliation_id not in {item.reconciliation_id for item in first_page}


def test_issue_summary_is_generated_and_never_accepts_protected_content(tmp_path):
    service, _ = make_service(tmp_path)
    secret = "social-security-number-1234"

    issue, _ = service.detect(
        user_id="user-a",
        domain=ReconciliationDomain.DOCUMENT,
        entity_type="attachment",
        entity_id="attachment-1",
        issue_type="stuck_scanning",
        correlation_id=secret,
        now=NOW,
    )

    assert secret not in issue.safe_summary
    assert secret != issue.correlation_id
    assert "filename" not in issue.safe_summary


class DetectorRecords:
    def __init__(self, records):
        self.records = records

    def list_records(self, user_id, include_archived=False, limit=None):
        records = [item for item in self.records if item.user_id == user_id]
        return records[:limit] if limit is not None else records

    def get_record(self, user_id, record_id):
        return next((item for item in self.records if item.user_id == user_id and item.id == record_id), None)


class DetectorReminders:
    def list_reminders(self, _user_id, limit=None):
        return []

    def get_reminder(self, _user_id, _reminder_id):
        return None


class DetectorAttachments:
    def __init__(self, attachments=None):
        self.attachments = attachments or []

    def list_for_user(self, user_id, limit=None):
        attachments = [item for item in self.attachments if item.user_id == user_id]
        return attachments[:limit] if limit is not None else attachments

    def get_attachment(self, user_id, record_id, attachment_id):
        return next(
            (
                item
                for item in self.attachments
                if item.user_id == user_id and item.record_id == record_id and item.attachment_id == attachment_id
            ),
            None,
        )


class DetectorEmpty:
    def list_for_user(self, _user_id, limit=100):
        return []

    def list_links_for_entity(self, *_args):
        return []


class DetectorHistory:
    def list_for_user(self, _user_id, limit=100):
        return []


class DetectorSearch:
    def get_projection(self, *_args):
        return None

    def list_projection_ids_for_user(self, *_args):
        return []


class DetectorStorage:
    def __init__(self, *, missing_clean=False, objects=None):
        self.missing_clean = missing_clean
        self.objects = objects or []

    def head_clean_object(self, _key):
        if self.missing_clean:
            raise RuntimeError("storage detail must not enter the issue")

    def list_user_objects(self, _user_id, limit=100):
        return self.objects[:limit]


def test_detector_creates_one_issue_for_missing_projection(tmp_path):
    service, repository = make_service(tmp_path)
    record = Record(
        id="record-1",
        user_id="user-a",
        record_type=RecordType.GENERAL,
        title="Safe title is never copied to issue",
        status=RecordStatus.ACTIVE,
        created_at=NOW,
        updated_at=NOW,
    )
    detector = ReconciliationDetector(
        service,
        DetectorRecords([record]),
        DetectorReminders(),
        DetectorHistory(),
        DetectorAttachments(),
        DetectorEmpty(),
        DetectorSearch(),
    )

    assert detector.detect_user("user-a", now=NOW) == 1
    assert detector.detect_user("user-a", now=NOW) == 0
    issue = repository.list_by_user("user-a")[0]
    assert issue.issue_type == "missing_projection"
    assert record.title not in issue.safe_summary


def test_detector_marks_old_scanning_document_without_filename(tmp_path):
    service, repository = make_service(tmp_path)
    attachment = RecordAttachment(
        attachment_id="attachment-1",
        user_id="user-a",
        owner_hash="owner",
        record_id="record-1",
        record_attachment_key="record-1#attachment-1",
        display_name="private-filename.pdf",
        content_type="application/pdf",
        size_bytes=100,
        status=AttachmentStatus.SCANNING,
        created_at=NOW - timedelta(hours=1),
    )
    detector = ReconciliationDetector(
        service,
        DetectorRecords([]),
        DetectorReminders(),
        DetectorHistory(),
        DetectorAttachments([attachment]),
        DetectorEmpty(),
        DetectorSearch(),
    )

    detector.detect_user("user-a", now=NOW)

    issue = next(item for item in repository.list_by_user("user-a") if item.issue_type == "stuck_scanning")
    assert attachment.display_name not in issue.safe_summary


def test_detector_marks_missing_clean_and_orphan_objects_without_object_keys(tmp_path):
    service, repository = make_service(tmp_path)
    attachment = RecordAttachment(
        attachment_id="attachment-1",
        user_id="user-a",
        owner_hash="owner",
        record_id="record-1",
        record_attachment_key="record-1#attachment-1",
        display_name="private.pdf",
        content_type="application/pdf",
        size_bytes=100,
        status=AttachmentStatus.AVAILABLE,
        clean_object_key="clean/owner/record-1/attachment-1/object",
        created_at=NOW,
    )
    orphan_key = "quarantine/owner/orphan/private-name.pdf"
    detector = ReconciliationDetector(
        service,
        DetectorRecords([]),
        DetectorReminders(),
        DetectorHistory(),
        DetectorAttachments([attachment]),
        DetectorEmpty(),
        DetectorSearch(),
        DetectorStorage(missing_clean=True, objects=[("quarantine", orphan_key)]),
    )

    detector.detect_user("user-a", now=NOW)

    issues = repository.list_by_user("user-a")
    assert {item.issue_type for item in issues} >= {"clean_object_missing", "orphaned_user_object"}
    assert all(orphan_key not in item.safe_summary and orphan_key not in item.entity_id for item in issues)


def test_detector_skips_orphan_object_claim_when_attachment_page_is_truncated(tmp_path):
    service, repository = make_service(tmp_path)
    attachment = RecordAttachment(
        attachment_id="attachment-1",
        user_id="user-a",
        owner_hash="owner",
        record_id="record-1",
        record_attachment_key="record-1#attachment-1",
        display_name="private.pdf",
        content_type="application/pdf",
        size_bytes=100,
        status=AttachmentStatus.AVAILABLE,
        clean_object_key="clean/owner/record-1/attachment-1/object",
        created_at=NOW,
    )
    detector = ReconciliationDetector(
        service,
        DetectorRecords([]),
        DetectorReminders(),
        DetectorHistory(),
        DetectorAttachments([attachment]),
        DetectorEmpty(),
        DetectorSearch(),
        DetectorStorage(objects=[("quarantine", "quarantine/owner/unverified/object")]),
    )

    detector.detect_user("user-a", limit=1, now=NOW)

    assert all(issue.issue_type != "orphaned_user_object" for issue in repository.list_by_user("user-a"))


def test_recurring_transition_current_occurrence_is_not_a_false_mismatch():
    next_due = date(2027, 7, 18)
    event = SimpleNamespace(
        event_id="event-1",
        event_type=ResponsibilityEventType.RENEWED,
        occurrence_id="prior-occurrence",
        next_due_date=next_due,
        occurred_at=NOW,
    )
    reminder = SimpleNamespace(id="reminder-1", due_date=next_due)

    assert _expected_occurrence(reminder, [event]) == new_occurrence_id(
        "reminder-1", next_due, "prior-occurrence"
    )
