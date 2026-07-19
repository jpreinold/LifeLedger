import argparse
import json
from dataclasses import asdict

from app.account_runtime import get_reconciliation_service
from app.attachments import create_document_storage_service
from app.config import get_settings
from app.reconciliation import ReconciliationDomain
from app.reconciliation_detector import ReconciliationDetector
from app.repository_factory import (
    create_linked_item_repository,
    create_record_attachment_repository,
    create_record_repository,
    create_repository,
    create_responsibility_history_repository,
    create_search_index_repository,
)
from app.schemas import LinkedEntityType
from app.search_service import SearchProjectionService
from reconciliation_handler import handler as scheduled_handler


def main() -> int:
    parser = argparse.ArgumentParser(description="IAM-authenticated LifeLedger reconciliation maintenance command.")
    commands = parser.add_subparsers(dest="command", required=True)
    retry = commands.add_parser("retry", help="Retry one reconciliation issue.")
    retry.add_argument("reconciliation_id")
    resolve = commands.add_parser("resolve", help="Resolve one issue after verified repair.")
    resolve.add_argument("reconciliation_id")
    resolve.add_argument("--reason", required=True)
    ignore = commands.add_parser("ignore", help="Ignore one verified non-actionable issue.")
    ignore.add_argument("reconciliation_id")
    ignore.add_argument("--reason", required=True)
    report = commands.add_parser("report", help="List safe issue metadata for one user or domain.")
    report.add_argument("--user-id")
    report.add_argument("--domain", choices=[item.value for item in ReconciliationDomain])
    report.add_argument("--limit", type=int, default=50)
    sweep = commands.add_parser("sweep", help="Run a bounded due-issue pass.")
    sweep.add_argument("--limit", type=int, default=25)
    sweep.add_argument("--dry-run", action="store_true")
    detect_user = commands.add_parser("detect-user", help="Detect verified issues for one user in a bounded page.")
    detect_user.add_argument("--user-id", required=True)
    detect_user.add_argument("--limit", type=int, default=100)
    reconcile_user = commands.add_parser("reconcile-user", help="Rebuild one user's bounded search set and detect issues.")
    reconcile_user.add_argument("--user-id", required=True)
    reconcile_user.add_argument("--limit", type=int, default=100)
    reconcile_user.add_argument("--dry-run", action="store_true")
    reconcile_entity = commands.add_parser("reconcile-entity", help="Rebuild one entity's search projection.")
    reconcile_entity.add_argument("--user-id", required=True)
    reconcile_entity.add_argument("--entity-type", required=True, choices=[item.value for item in LinkedEntityType])
    reconcile_entity.add_argument("--entity-id", required=True)
    reconcile_entity.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    service = get_reconciliation_service()

    if args.command == "retry":
        output = service.retry_one(args.reconciliation_id)
    elif args.command == "resolve":
        output = service.resolve(args.reconciliation_id, args.reason)
    elif args.command == "ignore":
        output = service.ignore(args.reconciliation_id, args.reason)
    elif args.command == "sweep":
        print(json.dumps(scheduled_handler({"limit": args.limit, "dry_run": args.dry_run}, None), indent=2))
        return 0
    elif args.command in {"detect-user", "reconcile-user", "reconcile-entity"}:
        bounded_limit = max(1, min(args.limit, 500)) if hasattr(args, "limit") else 100
        detector, search_service = _maintenance_services(service)
        if args.command == "detect-user":
            print(json.dumps({"detected": detector.detect_user(args.user_id, limit=bounded_limit)}, indent=2))
        elif args.command == "reconcile-user":
            result = search_service.rebuild_user(args.user_id, limit=bounded_limit, dry_run=args.dry_run)
            detected = 0 if args.dry_run else detector.detect_user(args.user_id, limit=bounded_limit)
            print(json.dumps({**asdict(result), "detected": detected}, indent=2))
        else:
            search_service.rebuild_one(
                args.user_id,
                LinkedEntityType(args.entity_type),
                args.entity_id,
                dry_run=args.dry_run,
            )
            print(json.dumps({"entity_type": args.entity_type, "entity_id": args.entity_id, "dry_run": args.dry_run}, indent=2))
        return 0
    else:
        limit = max(1, min(args.limit, 100))
        if bool(args.user_id) == bool(args.domain):
            parser.error("report requires exactly one of --user-id or --domain")
        issues = (
            service.repository.list_by_user(args.user_id, limit=limit)
            if args.user_id
            else service.repository.list_by_domain(ReconciliationDomain(args.domain), limit=limit)
        )
        print(json.dumps([safe_issue(item) for item in issues], indent=2))
        return 0
    print(json.dumps(safe_issue(output), indent=2))
    return 0


def safe_issue(issue):
    return {
        "reconciliation_id": issue.reconciliation_id,
        "domain": issue.domain.value,
        "entity_type": issue.entity_type,
        "entity_id": issue.entity_id,
        "issue_type": issue.issue_type,
        "status": issue.status.value,
        "severity": issue.severity.value,
        "retryable": issue.retryable,
        "attempt_count": issue.attempt_count,
        "detected_at": issue.detected_at.isoformat(),
        "last_attempt_at": issue.last_attempt_at.isoformat() if issue.last_attempt_at else None,
        "next_retry_at": issue.next_retry_at.isoformat() if issue.next_retry_at else None,
        "safe_summary": issue.safe_summary,
        "resolution": issue.resolution,
    }


def _maintenance_services(reconciliation):
    settings = get_settings()
    records = create_record_repository(settings)
    reminders = create_repository(settings)
    attachments = create_record_attachment_repository(settings)
    links = create_linked_item_repository(settings)
    history = create_responsibility_history_repository(settings)
    search = create_search_index_repository(settings)
    search_service = SearchProjectionService(search, records, reminders, attachments, links)
    detector = ReconciliationDetector(
        reconciliation,
        records,
        reminders,
        history,
        attachments,
        links,
        search,
        create_document_storage_service(settings),
    )
    return detector, search_service


if __name__ == "__main__":
    raise SystemExit(main())
