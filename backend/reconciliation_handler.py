import json
import logging
from datetime import datetime, timezone

from app.account_runtime import get_account_operations_repository, get_reconciliation_service
from app.account_runtime import get_account_deletion_service
from app.account_models import AccountOperationStatus, AccountState
from app.reconciliation import ReconciliationDomain, ReconciliationStatus
from app.repository_factory import (
    create_linked_item_repository,
    create_record_attachment_repository,
    create_record_repository,
    create_repository,
    create_search_index_repository,
    create_responsibility_history_repository,
)
from app.attachments import create_document_storage_service, reconcile_attachment_scan_status
from app.reconciliation_detector import ReconciliationDetector
from app.config import DYNAMODB_PERSISTENCE
from app.schemas import AttachmentStatus, LinkedEntityType
from app.search_service import SearchProjectionService
from app.responsibility_lifecycle_service import ResponsibilityLifecycleService
from app.responsibility_sync import resolve_date_target_for_key, synchronize_item_date
from app.config import get_settings


logger = logging.getLogger(__name__)


def handler(event, _context):
    settings = get_settings()
    reconciliation = get_reconciliation_service()
    account_operations = get_account_operations_repository()
    search_repo = create_search_index_repository(settings)
    record_repo = create_record_repository(settings)
    reminder_repo = create_repository(settings)
    attachment_repo = create_record_attachment_repository(settings)
    linked_repo = create_linked_item_repository(settings)
    history_repo = create_responsibility_history_repository(settings)
    search_service = SearchProjectionService(search_repo, record_repo, reminder_repo, attachment_repo, linked_repo)
    lifecycle_service = ResponsibilityLifecycleService(
        reminder_repo,
        history_repo,
        record_repo,
        linked_repo,
        attachment_repo,
        search_service,
    )
    document_storage = create_document_storage_service(settings)

    def deletion_active(user_id):
        return account_operations.get_lifecycle(user_id).state in {
            AccountState.DELETION_REQUESTED,
            AccountState.DELETING,
            AccountState.DELETION_REQUIRES_ATTENTION,
            AccountState.DELETED,
        }

    def repair_search(issue):
        if deletion_active(issue.user_id):
            return "Verified idempotent repair completed."
        search_service.rebuild_one(
            issue.user_id,
            LinkedEntityType(issue.entity_type),
            issue.entity_id,
        )
        return "Search projection was rebuilt and verified."

    def repair_account_deletion(issue):
        result = get_account_deletion_service().process_deletion(issue.user_id, issue.entity_id)
        if result.status != AccountOperationStatus.COMPLETE:
            raise RuntimeError("Account deletion remains incomplete.")
        return "Account deletion cleanup was resumed and verified."

    def repair_orphaned_projection(issue):
        if deletion_active(issue.user_id):
            return "Verified idempotent repair completed."
        search_repo.delete_projection(issue.user_id, issue.entity_id)
        return "Verified idempotent repair completed."

    def repair_document_state(issue):
        if deletion_active(issue.user_id):
            return "Verified idempotent repair completed."
        attachment = next(
            (
                item
                for item in attachment_repo.list_for_user(issue.user_id, limit=100)
                if item.attachment_id == issue.entity_id
            ),
            None,
        )
        if attachment is None:
            return "Verified idempotent repair completed."
        if issue.issue_type == "stuck_scanning":
            attachment = reconcile_attachment_scan_status(
                attachment=attachment,
                repo=attachment_repo,
                storage=document_storage,
                settings=settings,
            )
            if attachment.status in {AttachmentStatus.UPLOADED, AttachmentStatus.SCANNING}:
                raise RuntimeError("Document scanning has not reached a terminal state.")
        search_service.upsert_document(attachment)
        return "Verified idempotent repair completed."

    def repair_lifecycle(issue):
        if deletion_active(issue.user_id):
            return "Verified idempotent repair completed."
        event = history_repo.get_event(issue.user_id, issue.entity_id)
        if event is None:
            return "Verified idempotent repair completed."
        reminder = reminder_repo.get_reminder(issue.user_id, event.reminder_id)
        if reminder is None:
            raise RuntimeError("Responsibility is unavailable for lifecycle reconciliation.")
        result = lifecycle_service.reconcile_reminder(issue.user_id, reminder)
        if result.remaining:
            raise RuntimeError("Lifecycle reconciliation remains incomplete.")
        return "Verified idempotent repair completed."

    def repair_item_sync(issue):
        if deletion_active(issue.user_id):
            return "Verified idempotent repair completed."
        event = history_repo.get_event(issue.user_id, issue.entity_id)
        if (
            event is None
            or not event.item_id
            or not event.item_date_sync_key
            or not event.previous_due_date
            or not event.next_due_date
        ):
            raise RuntimeError("Accepted lifecycle evidence is incomplete.")
        record = record_repo.get_record(issue.user_id, event.item_id)
        target = resolve_date_target_for_key(event.item_date_sync_key)
        if record is None or target is None:
            raise RuntimeError("Item date target is unavailable.")
        synchronize_item_date(
            record_repo,
            record,
            target,
            previous_due_date=event.previous_due_date,
            next_due_date=event.next_due_date,
            now=datetime.now(timezone.utc),
        )
        search_service.sync_entity_observed(
            issue.user_id,
            LinkedEntityType.RECORD,
            record.id,
            operation="scheduled_item_date_reconciliation",
        )
        return "Verified idempotent repair completed."

    reconciliation.repairers.update(
        {
            (ReconciliationDomain.SEARCH, "projection_sync_failure"): repair_search,
            (ReconciliationDomain.SEARCH, "missing_projection"): repair_search,
            (ReconciliationDomain.SEARCH, "stale_projection_version"): repair_search,
            (ReconciliationDomain.SEARCH, "incorrect_archived_status"): repair_search,
            (ReconciliationDomain.SEARCH, "missing_document_projection"): repair_search,
            (ReconciliationDomain.SEARCH, "missing_linked_context"): repair_search,
            (ReconciliationDomain.SEARCH, "orphaned_projection"): repair_orphaned_projection,
            (ReconciliationDomain.DOCUMENT, "stuck_scanning"): repair_document_state,
            (ReconciliationDomain.DOCUMENT, "rejected_document_projected_as_usable"): repair_document_state,
            (ReconciliationDomain.LIFECYCLE, "lifecycle_reconciliation_flag"): repair_lifecycle,
            (ReconciliationDomain.ITEM_SYNC, "accepted_item_date_mismatch"): repair_item_sync,
        }
    )
    for issue in reconciliation.repository.list_by_domain(ReconciliationDomain.ACCOUNT_DELETION, limit=100):
        reconciliation.repairers[(ReconciliationDomain.ACCOUNT_DELETION, issue.issue_type)] = repair_account_deletion
    limit = max(1, min(int(event.get("limit", 25)), 100)) if isinstance(event, dict) else 25
    dry_run = bool(event.get("dry_run", False)) if isinstance(event, dict) else False
    expired_exports_deleted = _cleanup_expired_exports(settings, limit=25) if not dry_run else 0
    detected = 0
    if isinstance(event, dict) and event.get("mode") == "deep" and not dry_run:
        detector = ReconciliationDetector(
            reconciliation,
            record_repo,
            reminder_repo,
            history_repo,
            attachment_repo,
            linked_repo,
            search_repo,
            document_storage,
        )
        user_ids = event.get("user_ids") or _discover_user_ids(settings, max(1, min(limit, 100)))
        for user_id in list(dict.fromkeys(user_ids))[:limit]:
            if deletion_active(user_id):
                continue
            detected += detector.detect_user(user_id, limit=100)
    result = reconciliation.process_due(limit=limit, dry_run=dry_run)
    _emit_metrics(reconciliation, result)
    logger.info(
        json.dumps(
            {
                "event": "scheduled_reconciliation_complete",
                "considered": result.considered,
                "attempted": result.attempted,
                "resolved": result.resolved,
                "failed": result.failed,
                "requires_attention": result.requires_attention,
                "dry_run": result.dry_run,
                "detected": detected,
                "expired_exports_deleted": expired_exports_deleted,
            }
        )
    )
    return {
        **result.model_dump(mode="json"),
        "detected": detected,
        "expired_exports_deleted": expired_exports_deleted,
    }


def _discover_user_ids(settings, limit):
    if settings.persistence_mode != DYNAMODB_PERSISTENCE:
        return []
    import boto3

    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    state_table = dynamodb.Table(settings.account_operations_table_name)
    table_names = [
        settings.records_table_name,
        settings.reminders_table_name,
        settings.record_attachments_table_name,
        settings.preferences_table_name,
    ]
    per_table = max(1, limit // len(table_names))
    user_ids = []
    for table_name in table_names:
        state_key = {"user_id": "__SYSTEM__", "operation_key": f"SWEEP#{table_name}"}
        state = state_table.get_item(Key=state_key).get("Item", {})
        kwargs = {"Limit": per_table, "ProjectionExpression": "user_id"}
        if state.get("cursor"):
            kwargs["ExclusiveStartKey"] = state["cursor"]
        response = dynamodb.Table(table_name).scan(**kwargs)
        user_ids.extend(item["user_id"] for item in response.get("Items", []) if item.get("user_id"))
        cursor = response.get("LastEvaluatedKey")
        if cursor:
            state_table.put_item(Item={**state_key, "cursor": cursor})
        else:
            state_table.delete_item(Key=state_key)
    return list(dict.fromkeys(user_ids))[:limit]


def _cleanup_expired_exports(settings, limit):
    if settings.persistence_mode != DYNAMODB_PERSISTENCE:
        return 0
    import boto3

    now = datetime.now(timezone.utc).isoformat()
    table = boto3.resource("dynamodb", region_name=settings.aws_region).Table(settings.account_operations_table_name)
    response = table.query(
        IndexName="ExportExpiryIndex",
        KeyConditionExpression="expiry_partition = :export AND expires_at <= :now",
        ExpressionAttributeValues={":export": "EXPORT", ":now": now},
        Limit=limit,
    )
    s3 = boto3.client("s3", region_name=settings.aws_region)
    deleted = 0
    for item in response.get("Items", []):
        artifact_key = item.get("artifact_key")
        if artifact_key:
            s3.delete_object(Bucket=settings.account_exports_bucket, Key=artifact_key)
        table.update_item(
            Key={"user_id": item["user_id"], "operation_key": item["operation_key"]},
            UpdateExpression="SET #status = :expired, updated_at = :now REMOVE artifact_key, expiry_partition",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":expired": "expired", ":now": now},
        )
        deleted += 1
    return deleted


def _emit_metrics(service, result):
    now = datetime.now(timezone.utc)
    statuses = {
        status.value: service.repository.list_by_status(status, limit=100)
        for status in (
            ReconciliationStatus.PENDING,
            ReconciliationStatus.RETRYING,
            ReconciliationStatus.REQUIRES_ATTENTION,
        )
    }
    unresolved = [issue for issues in statuses.values() for issue in issues]
    oldest_age = max((now - issue.detected_at).total_seconds() for issue in unresolved) if unresolved else 0
    metrics = [
        {"Name": "PendingReconciliationCount", "Unit": "Count"},
        {"Name": "RetryingReconciliationCount", "Unit": "Count"},
        {"Name": "RequiresAttentionCount", "Unit": "Count"},
        {"Name": "OldestUnresolvedAgeSeconds", "Unit": "Seconds"},
        {"Name": "DocumentStuckScanningCount", "Unit": "Count"},
        {"Name": "AccountDeletionIncompleteCount", "Unit": "Count"},
        {"Name": "ReconciliationResolutions", "Unit": "Count"},
        {"Name": "ReconciliationFailedRetries", "Unit": "Count"},
    ]
    document_stuck = len(
        [issue for issue in unresolved if issue.domain == ReconciliationDomain.DOCUMENT and issue.issue_type == "stuck_scanning"]
    )
    account_incomplete = len(
        [issue for issue in unresolved if issue.domain == ReconciliationDomain.ACCOUNT_DELETION]
    )
    print(
        json.dumps(
            {
                "_aws": {
                    "Timestamp": int(now.timestamp() * 1000),
                    "CloudWatchMetrics": [
                        {
                            "Namespace": "LifeLedger/Operations",
                            "Dimensions": [["Environment"]],
                            "Metrics": metrics,
                        }
                    ],
                },
                "Environment": get_settings().app_env,
                "PendingReconciliationCount": len(statuses["pending"]),
                "RetryingReconciliationCount": len(statuses["retrying"]),
                "RequiresAttentionCount": len(statuses["requires_attention"]),
                "OldestUnresolvedAgeSeconds": oldest_age,
                "DocumentStuckScanningCount": document_stuck,
                "AccountDeletionIncompleteCount": account_incomplete,
                "ReconciliationResolutions": result.resolved,
                "ReconciliationFailedRetries": result.failed,
            }
        )
    )
    for domain in ReconciliationDomain:
        count = len(service.repository.list_by_domain(domain, limit=100))
        print(
            json.dumps(
                {
                    "_aws": {
                        "Timestamp": int(now.timestamp() * 1000),
                        "CloudWatchMetrics": [
                            {
                                "Namespace": "LifeLedger/Operations",
                                "Dimensions": [["Environment", "Domain"]],
                                "Metrics": [{"Name": "ReconciliationIssueCount", "Unit": "Count"}],
                            }
                        ],
                    },
                    "Environment": get_settings().app_env,
                    "Domain": domain.value,
                    "ReconciliationIssueCount": count,
                }
            )
        )
