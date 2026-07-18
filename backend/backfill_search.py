import argparse
import logging

from app.config import get_settings
from app.repository_factory import (
    create_linked_item_repository,
    create_record_attachment_repository,
    create_record_repository,
    create_repository,
    create_search_index_repository,
)
from app.schemas import LinkedEntityType
from app.search_service import SearchProjectionService


logger = logging.getLogger("lifeledger.search_backfill")


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill LifeLedger unified search projections for one user.")
    parser.add_argument("--user-id", required=True, help="LifeLedger user id to backfill.")
    parser.add_argument("--dry-run", action="store_true", help="Count projections without writing search index rows.")
    parser.add_argument("--entity-type", choices=[item.value for item in LinkedEntityType], help="Rebuild one item type.")
    parser.add_argument("--entity-id", help="Rebuild one item id; requires --entity-type.")
    parser.add_argument("--limit", type=int, default=1_000, help="Maximum source items of each type (default: 1000).")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = get_settings()
    attachment_repo = create_record_attachment_repository(settings)
    service = SearchProjectionService(
        create_search_index_repository(settings),
        create_record_repository(settings),
        create_repository(settings),
        attachment_repo,
        create_linked_item_repository(settings),
    )
    if bool(args.entity_type) != bool(args.entity_id):
        parser.error("--entity-type and --entity-id must be supplied together")
    if args.entity_type and args.entity_id:
        service.rebuild_one(
            args.user_id, LinkedEntityType(args.entity_type), args.entity_id, dry_run=args.dry_run
        )
        logger.info("search_reconcile_one_complete user_id=%s entity_type=%s entity_id=%s dry_run=%s", args.user_id, args.entity_type, args.entity_id, args.dry_run)
        return 0

    result = service.rebuild_user(args.user_id, dry_run=args.dry_run, limit=max(1, args.limit))

    logger.info(
        "search_backfill_complete user_id=%s dry_run=%s records=%s documents=%s reminders=%s skipped=%s deleted=%s failures_retried=%s failures_remaining=%s total=%s",
        result.user_id,
        result.dry_run,
        result.records_indexed,
        result.documents_indexed,
        result.reminders_indexed,
        result.skipped,
        result.projections_deleted,
        result.failures_retried,
        result.failures_remaining,
        result.total_indexed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
