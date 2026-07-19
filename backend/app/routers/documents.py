from fastapi import APIRouter

from app.route_support import *  # noqa: F403

router = APIRouter(tags=["documents"])
documents_router = router

@documents_router.get("/records/{record_id}/attachments", response_model=list[RecordAttachmentResponse])
def list_record_attachments(
    record_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    document_storage=Depends(get_document_storage_service),
    app_settings: Settings = Depends(get_app_settings),
) -> list[RecordAttachmentResponse]:
    set_attachment_no_store(response)
    require_record(record_repo, current_user.user_id, record_id)
    attachments = [
        maybe_reconcile_attachment(attachment, attachment_repo, document_storage, app_settings)
        for attachment in attachment_repo.list_for_record(current_user.user_id, record_id)
    ]
    return [to_attachment_response(attachment) for attachment in sort_attachments(attachments)]


@documents_router.post(
    "/records/{record_id}/attachments/upload-intent",
    response_model=RecordAttachmentUploadIntentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_record_attachment_upload_intent(
    record_id: str,
    payload: RecordAttachmentUploadIntentRequest,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    document_storage=Depends(get_document_storage_service),
    app_settings: Settings = Depends(get_app_settings),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> RecordAttachmentUploadIntentResponse:
    set_attachment_no_store(response)
    require_record(record_repo, current_user.user_id, record_id)
    require_document_storage_configured(document_storage)

    normalized_key = normalize_idempotency_key(idempotency_key)
    attachment_id = (
        str(uuid5(NAMESPACE_URL, f"lifeledger:document:{current_user.user_id}:{record_id}:{normalized_key}"))
        if normalized_key
        else None
    )
    try:
        attachment = new_record_attachment(
            user_id=current_user.user_id,
            record_id=record_id,
            filename=payload.filename,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
            settings=app_settings,
            now=utc_now(),
            attachment_id=attachment_id,
        )
    except AttachmentValidationError as exc:
        raise attachment_http_exception(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.safe_message) from exc

    existing_attachments = attachment_repo.list_for_record(current_user.user_id, record_id)
    existing_attachment = (
        attachment_repo.get_attachment(current_user.user_id, record_id, attachment.attachment_id)
        if normalized_key
        else None
    )
    created_new = existing_attachment is None
    if existing_attachment is not None:
        if (
            existing_attachment.display_name != attachment.display_name
            or existing_attachment.content_type != attachment.content_type
            or existing_attachment.size_bytes != attachment.size_bytes
        ):
            raise attachment_http_exception(status.HTTP_409_CONFLICT, "This document retry does not match the original file.")
        saved = attachment_repo.update_attachment(
            existing_attachment.model_copy(update={"upload_expires_at": attachment.upload_expires_at})
        )
    else:
        if active_attachment_count(existing_attachments) >= app_settings.attachment_max_per_record:
            raise attachment_http_exception(
                status.HTTP_409_CONFLICT,
                "Records can have up to 5 active attachments.",
            )
        saved = attachment_repo.create_attachment(attachment)
        document_entity_id = document_item_id(record_id, saved.attachment_id)
        sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.DOCUMENT, document_entity_id, "document_create")
        sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, record_id, "document_create")
    try:
        presigned_upload = document_storage.create_presigned_upload(
            saved,
            max_size_bytes=app_settings.attachment_max_size_bytes,
            expires_in_seconds=UPLOAD_INTENT_EXPIRATION_SECONDS,
        )
    except (DocumentStorageConfigurationError, DocumentStorageOperationError) as exc:
        if created_new:
            document_entity_id = document_item_id(record_id, saved.attachment_id)
            attachment_repo.delete_attachment_metadata(current_user.user_id, record_id, saved.attachment_id)
            delete_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.DOCUMENT, document_entity_id, "document_create_rollback")
            sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, record_id, "document_create_rollback")
        raise attachment_http_exception(status.HTTP_503_SERVICE_UNAVAILABLE, exc.safe_message) from exc

    log_security_event(
        "attachment_upload_intent_created",
        user_id=current_user.user_id,
        record_id=record_id,
        attachment_id=saved.attachment_id,
        content_type=saved.content_type,
        size=saved.size_bytes,
        result="created" if created_new else "reused",
    )
    return RecordAttachmentUploadIntentResponse(
        attachment_id=saved.attachment_id,
        upload=presigned_upload,
        expires_at=saved.upload_expires_at,
        max_size_bytes=app_settings.attachment_max_size_bytes,
    )


@documents_router.post("/records/{record_id}/attachments/{attachment_id}/complete", response_model=RecordAttachmentResponse)
def complete_record_attachment_upload(
    record_id: str,
    attachment_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    document_storage=Depends(get_document_storage_service),
    app_settings: Settings = Depends(get_app_settings),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> RecordAttachmentResponse:
    set_attachment_no_store(response)
    require_record(record_repo, current_user.user_id, record_id)
    require_document_storage_configured(document_storage)
    attachment = require_attachment(attachment_repo, current_user.user_id, record_id, attachment_id)

    try:
        completed = complete_attachment_upload(
            attachment=attachment,
            storage=document_storage,
            settings=app_settings,
            now=utc_now(),
        )
    except AttachmentValidationError as exc:
        reject_failed_upload(attachment, attachment_repo, document_storage)
        raise attachment_http_exception(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.safe_message) from exc
    except (DocumentStorageConfigurationError, DocumentStorageOperationError) as exc:
        raise attachment_http_exception(status.HTTP_503_SERVICE_UNAVAILABLE, exc.safe_message) from exc

    saved = attachment_repo.update_attachment(completed)
    document_entity_id = document_item_id(record_id, attachment_id)
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.DOCUMENT, document_entity_id, "document_upload_complete")
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, record_id, "document_upload_complete")
    log_security_event(
        "attachment_upload_completed",
        user_id=current_user.user_id,
        record_id=record_id,
        attachment_id=attachment_id,
        content_type=saved.content_type,
        size=saved.size_bytes,
        result="scanning",
    )
    return to_attachment_response(saved)


@documents_router.get("/records/{record_id}/attachments/{attachment_id}", response_model=RecordAttachmentResponse)
def get_record_attachment(
    record_id: str,
    attachment_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    document_storage=Depends(get_document_storage_service),
    app_settings: Settings = Depends(get_app_settings),
) -> RecordAttachmentResponse:
    set_attachment_no_store(response)
    require_record(record_repo, current_user.user_id, record_id)
    attachment = require_attachment(attachment_repo, current_user.user_id, record_id, attachment_id)
    return to_attachment_response(maybe_reconcile_attachment(attachment, attachment_repo, document_storage, app_settings))


@documents_router.post("/records/{record_id}/attachments/{attachment_id}/refresh-status", response_model=RecordAttachmentResponse)
def refresh_record_attachment_status(
    record_id: str,
    attachment_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    document_storage=Depends(get_document_storage_service),
    app_settings: Settings = Depends(get_app_settings),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> RecordAttachmentResponse:
    set_attachment_no_store(response)
    require_record(record_repo, current_user.user_id, record_id)
    attachment = require_attachment(attachment_repo, current_user.user_id, record_id, attachment_id)
    refreshed = maybe_reconcile_attachment(attachment, attachment_repo, document_storage, app_settings)
    document_entity_id = document_item_id(record_id, attachment_id)
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.DOCUMENT, document_entity_id, "document_refresh")
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, record_id, "document_refresh")
    return to_attachment_response(refreshed)


@documents_router.post("/records/{record_id}/attachments/{attachment_id}/download-url", response_model=RecordAttachmentDownloadUrlResponse)
def create_record_attachment_download_url(
    record_id: str,
    attachment_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    document_storage=Depends(get_document_storage_service),
    app_settings: Settings = Depends(get_app_settings),
) -> RecordAttachmentDownloadUrlResponse:
    set_attachment_no_store(response)
    require_record(record_repo, current_user.user_id, record_id)
    require_document_storage_configured(document_storage)
    attachment = require_attachment(attachment_repo, current_user.user_id, record_id, attachment_id)
    attachment = maybe_reconcile_attachment(attachment, attachment_repo, document_storage, app_settings)

    if attachment.status != AttachmentStatus.AVAILABLE or not attachment.clean_object_key:
        raise attachment_http_exception(status.HTTP_409_CONFLICT, ATTACHMENT_NOT_AVAILABLE)

    try:
        document_storage.head_clean_object(attachment.clean_object_key)
        url = document_storage.create_presigned_download(
            attachment,
            content_disposition=attachment_content_disposition(attachment),
            expires_in_seconds=DOWNLOAD_URL_EXPIRATION_SECONDS,
        )
    except (DocumentStorageConfigurationError, DocumentStorageOperationError) as exc:
        raise attachment_http_exception(status.HTTP_503_SERVICE_UNAVAILABLE, exc.safe_message) from exc

    log_security_event(
        "attachment_download_url_issued",
        user_id=current_user.user_id,
        record_id=record_id,
        attachment_id=attachment_id,
        content_type=attachment.content_type,
        size=attachment.size_bytes,
        result="issued",
    )
    return RecordAttachmentDownloadUrlResponse(
        url=url,
        expires_at=utc_now() + timedelta(seconds=DOWNLOAD_URL_EXPIRATION_SECONDS),
    )


@documents_router.post("/records/{record_id}/attachments/{attachment_id}/preview-url", response_model=RecordAttachmentDownloadUrlResponse)
def create_record_attachment_preview_url(
    record_id: str,
    attachment_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    document_storage=Depends(get_document_storage_service),
    app_settings: Settings = Depends(get_app_settings),
) -> RecordAttachmentDownloadUrlResponse:
    set_attachment_no_store(response)
    require_record(record_repo, current_user.user_id, record_id)
    require_document_storage_configured(document_storage)
    attachment = require_attachment(attachment_repo, current_user.user_id, record_id, attachment_id)
    attachment = maybe_reconcile_attachment(attachment, attachment_repo, document_storage, app_settings)

    if attachment.status != AttachmentStatus.AVAILABLE or not attachment.clean_object_key:
        raise attachment_http_exception(status.HTTP_409_CONFLICT, ATTACHMENT_NOT_AVAILABLE)

    try:
        document_storage.head_clean_object(attachment.clean_object_key)
        url = document_storage.create_presigned_download(
            attachment,
            content_disposition=attachment_content_disposition(attachment, "inline"),
            expires_in_seconds=DOWNLOAD_URL_EXPIRATION_SECONDS,
        )
    except (DocumentStorageConfigurationError, DocumentStorageOperationError) as exc:
        raise attachment_http_exception(status.HTTP_503_SERVICE_UNAVAILABLE, exc.safe_message) from exc

    log_security_event(
        "attachment_preview_url_issued",
        user_id=current_user.user_id,
        record_id=record_id,
        attachment_id=attachment_id,
        content_type=attachment.content_type,
        size=attachment.size_bytes,
        result="issued",
    )
    return RecordAttachmentDownloadUrlResponse(
        url=url,
        expires_at=utc_now() + timedelta(seconds=DOWNLOAD_URL_EXPIRATION_SECONDS),
    )


@documents_router.delete("/records/{record_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record_attachment(
    record_id: str,
    attachment_id: str,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    document_storage=Depends(get_document_storage_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> Response:
    require_record(record_repo, current_user.user_id, record_id)
    attachment = require_attachment(attachment_repo, current_user.user_id, record_id, attachment_id)
    document_entity_id = document_item_id(record_id, attachment_id)
    deleted_links = linked_repo.list_links_for_entity(current_user.user_id, LinkedEntityType.DOCUMENT, document_entity_id)
    cleanup_attachment_or_raise(attachment, attachment_repo, document_storage)
    linked_repo.delete_links_for_entity(
        current_user.user_id,
        LinkedEntityType.DOCUMENT,
        document_entity_id,
    )
    sync_linked_search_neighbors_safe(
        search_service,
        current_user.user_id,
        deleted_links,
        "document_delete_relationship_cleanup",
        excluded_entities={(LinkedEntityType.DOCUMENT, document_entity_id)},
    )
    delete_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.DOCUMENT, document_entity_id, "document_delete")
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, record_id, "document_delete")
    log_security_event(
        "attachment_deleted",
        user_id=current_user.user_id,
        record_id=record_id,
        attachment_id=attachment_id,
        content_type=attachment.content_type,
        size=attachment.size_bytes,
        result="deleted",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=no_store_headers())
