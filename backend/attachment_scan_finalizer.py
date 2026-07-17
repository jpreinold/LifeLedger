from typing import Any

from app.attachments import (
    DocumentStorageConfigurationError,
    DocumentStorageOperationError,
    create_document_storage_service,
    reconcile_attachment_scan_status,
)
from app.config import get_settings
from app.repository_factory import (
    create_linked_item_repository,
    create_record_attachment_repository,
    create_record_repository,
    create_repository,
    create_search_index_repository,
)
from app.relationship_service import document_item_id
from app.schemas import LinkedEntityType
from app.search_service import SearchProjectionService
from app.security_audit import log_security_event


def handler(event: dict[str, Any], _context) -> dict[str, str]:
    if event.get("source") != "aws.guardduty":
        return {"status": "ignored"}
    if event.get("detail-type") != "GuardDuty Malware Protection Object Scan Result":
        return {"status": "ignored"}

    settings = get_settings()
    if not settings.document_storage_configured:
        return {"status": "storage_not_configured"}

    detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
    object_details = detail.get("s3ObjectDetails") if isinstance(detail.get("s3ObjectDetails"), dict) else {}
    bucket_name = object_details.get("bucketName")
    object_key = object_details.get("objectKey")
    if bucket_name != settings.documents_quarantine_bucket or not isinstance(object_key, str):
        return {"status": "ignored"}

    parsed = parse_attachment_key(object_key)
    if parsed is None:
        return {"status": "ignored"}

    owner_hash, record_id, attachment_id = parsed
    repo = create_record_attachment_repository(settings)
    attachment = repo.get_attachment_by_owner_hash(owner_hash, record_id, attachment_id)
    if attachment is None:
        return {"status": "missing_metadata"}

    try:
        storage = create_document_storage_service(settings)
        attachment = reconcile_attachment_scan_status(
            attachment=attachment,
            repo=repo,
            storage=storage,
            settings=settings,
        )
    except (DocumentStorageConfigurationError, DocumentStorageOperationError):
        log_security_event(
            "attachment_cleanup_failed",
            user_id=attachment.user_id,
            record_id=attachment.record_id,
            attachment_id=attachment.attachment_id,
            content_type=attachment.content_type,
            size=attachment.size_bytes,
            result="finalizer_storage_error",
        )
        return {"status": "storage_error"}

    sync_search_projection(settings, repo, attachment)
    return {"status": "processed"}


def parse_attachment_key(object_key: str) -> tuple[str, str, str] | None:
    parts = object_key.split("/")
    if len(parts) != 5:
        return None
    prefix, owner_hash, record_id, attachment_id, leaf = parts
    if prefix != "quarantine" or leaf != "object":
        return None
    if not owner_hash or not record_id or not attachment_id:
        return None
    return owner_hash, record_id, attachment_id


def sync_search_projection(settings, attachment_repo, attachment) -> None:
    try:
        service = SearchProjectionService(
            create_search_index_repository(settings),
            create_record_repository(settings),
            create_repository(settings),
            attachment_repo,
            create_linked_item_repository(settings),
        )
        service.sync_entity(
            attachment.user_id,
            LinkedEntityType.DOCUMENT,
            document_item_id(attachment.record_id, attachment.attachment_id),
        )
        service.sync_entity(attachment.user_id, LinkedEntityType.RECORD, attachment.record_id)
    except Exception:
        log_security_event(
            "attachment_search_projection_sync_failed",
            user_id=attachment.user_id,
            record_id=attachment.record_id,
            attachment_id=attachment.attachment_id,
            content_type=attachment.content_type,
            size=attachment.size_bytes,
            result="search_sync_failed",
        )
