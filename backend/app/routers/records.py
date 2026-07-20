from fastapi import APIRouter

from app.route_support import *  # noqa: F403

router = APIRouter(tags=["records"])
records_router = router

@records_router.get("/records", response_model=list[RecordResponse])
def list_records(
    include_archived: bool = Query(default=False),
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
) -> list[RecordResponse]:
    records = repo.list_records(current_user.user_id, include_archived=include_archived)
    sorted_records = sorted(records, key=lambda item: (item.status == RecordStatus.ARCHIVED, item.title.lower(), item.created_at))
    return [to_record_response(record) for record in sorted_records]

@records_router.post("/records", response_model=RecordResponse, status_code=status.HTTP_201_CREATED)
def create_record(
    payload: RecordCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
    birthdays: PersonBirthdayService = Depends(get_person_birthday_service),
) -> RecordResponse:
    normalized_key = normalize_idempotency_key(idempotency_key)
    record_id = (
        str(uuid5(NAMESPACE_URL, f"lifeledger:record:{current_user.user_id}:{normalized_key}"))
        if normalized_key
        else str(uuid4())
    )
    existing = repo.get_record(current_user.user_id, record_id)
    if existing is not None:
        birthdays.synchronize(existing, now=existing.updated_at)
        sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, existing.id, "record_create_retry")
        return to_record_response(existing)

    now = utc_now()
    record_fields = payload.model_dump()
    record_fields["status"] = RecordStatus.ACTIVE
    record = Record(
        id=record_id,
        user_id=current_user.user_id,
        **record_fields,
        created_at=now,
        updated_at=now,
    )

    saved = repo.create_record(record)
    birthdays.synchronize(saved, now=saved.updated_at)
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, saved.id, "record_create")
    return to_record_response(saved)

@records_router.get("/records/{record_id}", response_model=RecordResponse)
def get_record(
    record_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
) -> RecordResponse:
    return to_record_response(require_record(repo, current_user.user_id, record_id))

@records_router.put("/records/{record_id}", response_model=RecordResponse)
def update_record(
    record_id: str,
    payload: RecordUpdate,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
    birthdays: PersonBirthdayService = Depends(get_person_birthday_service),
) -> RecordResponse:
    record = require_record(repo, current_user.user_id, record_id)
    updates = payload.model_dump(exclude_unset=True)
    for required_field in ("record_type", "title", "category", "status"):
        if updates.get(required_field) is None:
            updates.pop(required_field, None)
    if "tags" in updates and updates["tags"] is None:
        updates["tags"] = []
    updated = Record.model_validate({**record.model_dump(), **updates, "updated_at": utc_now()})
    saved = repo.update_record(updated)
    birthdays.synchronize(saved, now=saved.updated_at)
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, saved.id, "record_update")
    return to_record_response(saved)

@records_router.post("/records/{record_id}/fields", response_model=RecordResponse, status_code=status.HTTP_201_CREATED)
def add_record_field(
    record_id: str,
    payload: DynamicRecordFieldCreate,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    encryption_service: EncryptionService = Depends(get_encryption_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
    birthdays: PersonBirthdayService = Depends(get_person_birthday_service),
) -> RecordResponse:
    record = require_record(repo, current_user.user_id, record_id)
    if len(record.dynamic_fields) >= 30:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Records can have up to 30 custom fields.")

    field_id = str(uuid4())
    field_key = normalize_dynamic_field_key(payload.key or payload.label, field_id)
    if any(existing.key == field_key for existing in record.dynamic_fields):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A detail with this name already exists.")

    now = utc_now()
    field_value = payload.value
    field = DynamicRecordField(
        field_id=field_id,
        key=field_key,
        label=payload.label,
        field_type=payload.field_type,
        value=None if payload.is_sensitive else field_value,
        is_sensitive=payload.is_sensitive,
        has_value=dynamic_value_has_content(field_value),
        display_order=payload.display_order if payload.display_order is not None else next_dynamic_field_order(record),
        select_options=payload.select_options,
        created_at=now,
        updated_at=now,
    )
    try:
        validate_person_birthday_field(
            record,
            field_key=field.key,
            value=field_value,
            is_sensitive=field.is_sensitive,
            has_value=field.has_value,
            today=now.date(),
        )
    except PersonBirthdayValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    updated_record = record.model_copy(update={"dynamic_fields": sorted_dynamic_fields([*record.dynamic_fields, field]), "updated_at": now})
    if field.is_sensitive and dynamic_value_has_content(field_value):
        updated_record = set_dynamic_sensitive_value(record, updated_record, field.field_id, field_value, encryption_service, now)

    saved = repo.update_record(updated_record)
    birthdays.synchronize(saved, now=now)
    log_security_event(
        "record_dynamic_field_created",
        user_id=current_user.user_id,
        record_id=record.id,
        field_id=field.field_id,
        field_type=field.field_type.value,
        is_sensitive=field.is_sensitive,
        result="success",
    )
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, saved.id, "record_field_create")
    return to_record_response(saved)

@records_router.put("/records/{record_id}/fields/{field_id}", response_model=RecordResponse)
def update_record_field(
    record_id: str,
    field_id: str,
    payload: DynamicRecordFieldUpdate,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    encryption_service: EncryptionService = Depends(get_encryption_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
    birthdays: PersonBirthdayService = Depends(get_person_birthday_service),
) -> RecordResponse:
    record = require_record(repo, current_user.user_id, record_id)
    existing = find_dynamic_field(record, field_id)
    updates = payload.model_dump(exclude_unset=True)
    now = utc_now()

    next_type = updates.get("field_type", existing.field_type)
    next_select_options = updates.get("select_options", existing.select_options)
    if "value" in updates:
        updates["value"] = normalize_dynamic_field_value(next_type, updates["value"], next_select_options)

    if next_type != existing.field_type and existing.has_value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Remove and recreate this field to change its type without losing data.",
        )

    next_sensitive = updates.get("is_sensitive", existing.is_sensitive)
    if next_sensitive != existing.is_sensitive and existing.has_value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Remove and recreate this populated field to change its sensitivity.",
        )

    next_value = updates.pop("value", existing.value)
    if next_sensitive:
        next_value_for_model = None
        next_has_value = existing.has_value
        if "value" in payload.model_fields_set:
            next_has_value = dynamic_value_has_content(next_value)
    else:
        next_value_for_model = next_value
        next_has_value = dynamic_value_has_content(next_value)

    updated_field = existing.model_copy(
        update={
            **updates,
            "field_type": next_type,
            "is_sensitive": next_sensitive,
            "select_options": next_select_options,
            "value": next_value_for_model,
            "has_value": next_has_value,
            "updated_at": now,
        }
    )
    try:
        validate_person_birthday_field(
            record,
            field_key=existing.key,
            value=updated_field.value,
            is_sensitive=updated_field.is_sensitive,
            has_value=updated_field.has_value,
            today=now.date(),
        )
    except PersonBirthdayValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    updated_record = record.model_copy(
        update={
            "dynamic_fields": sorted_dynamic_fields(replace_dynamic_field(record.dynamic_fields, updated_field)),
            "updated_at": now,
        }
    )

    if updated_field.is_sensitive and "value" in payload.model_fields_set:
        updated_record = set_dynamic_sensitive_value(record, updated_record, field_id, next_value, encryption_service, now)
    elif existing.is_sensitive and not updated_field.is_sensitive:
        updated_record = remove_dynamic_sensitive_value(record, updated_record, field_id, encryption_service, now)

    saved = repo.update_record(updated_record)
    birthdays.synchronize(saved, now=now)
    log_security_event(
        "record_dynamic_field_updated",
        user_id=current_user.user_id,
        record_id=record.id,
        field_id=field_id,
        field_type=updated_field.field_type.value,
        is_sensitive=updated_field.is_sensitive,
        result="success",
    )
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, saved.id, "record_field_update")
    return to_record_response(saved)

@records_router.get("/records/{record_id}/fields/{field_id}/reveal", response_model=DynamicRecordFieldRevealResponse)
def reveal_record_field(
    record_id: str,
    field_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    encryption_service: EncryptionService = Depends(get_encryption_service),
) -> DynamicRecordFieldRevealResponse:
    for header, value in no_store_headers().items():
        response.headers[header] = value
    record = require_record(repo, current_user.user_id, record_id)
    field = find_dynamic_field(record, field_id)
    if not field.is_sensitive:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only sensitive fields require reveal.")
    if not field.has_value:
        return DynamicRecordFieldRevealResponse(field_id=field_id, value=None)

    values = decrypt_record_private_payload(record, encryption_service)
    dynamic_values = protected_dynamic_values(values)
    if field_id not in dynamic_values:
        return DynamicRecordFieldRevealResponse(field_id=field_id, value=None)

    log_security_event(
        "record_dynamic_field_revealed",
        user_id=current_user.user_id,
        record_id=record.id,
        field_id=field_id,
        result="success",
    )
    return DynamicRecordFieldRevealResponse(field_id=field_id, value=dynamic_values[field_id])

@records_router.delete("/records/{record_id}/fields/{field_id}", response_model=RecordResponse)
def delete_record_field(
    record_id: str,
    field_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    encryption_service: EncryptionService = Depends(get_encryption_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
    birthdays: PersonBirthdayService = Depends(get_person_birthday_service),
) -> RecordResponse:
    record = require_record(repo, current_user.user_id, record_id)
    existing = find_dynamic_field(record, field_id)
    now = utc_now()
    updated_record = record.model_copy(
        update={
            "dynamic_fields": [field for field in record.dynamic_fields if field.field_id != field_id],
            "updated_at": now,
        }
    )
    if existing.is_sensitive:
        updated_record = remove_dynamic_sensitive_value(record, updated_record, field_id, encryption_service, now)

    saved = repo.update_record(updated_record)
    birthdays.synchronize(saved, now=now)
    log_security_event(
        "record_dynamic_field_deleted",
        user_id=current_user.user_id,
        record_id=record.id,
        field_id=field_id,
        result="success",
    )
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, saved.id, "record_field_delete")
    return to_record_response(saved)

@records_router.post("/records/{record_id}/archive", response_model=RecordResponse)
def archive_record(
    record_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
    birthdays: PersonBirthdayService = Depends(get_person_birthday_service),
) -> RecordResponse:
    archived = repo.archive_record(current_user.user_id, record_id)
    if archived is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    birthdays.synchronize(archived, now=archived.updated_at)
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, archived.id, "record_archive")
    return to_record_response(archived)

@records_router.post("/records/{record_id}/restore", response_model=RecordResponse)
def restore_record(
    record_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
    birthdays: PersonBirthdayService = Depends(get_person_birthday_service),
) -> RecordResponse:
    restored = repo.unarchive_record(current_user.user_id, record_id)
    if restored is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    birthdays.synchronize(restored, now=restored.updated_at)
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, restored.id, "record_restore")
    return to_record_response(restored)

@records_router.delete("/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(
    record_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    document_storage=Depends(get_document_storage_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
    birthdays: PersonBirthdayService = Depends(get_person_birthday_service),
) -> Response:
    record = require_record(repo, current_user.user_id, record_id)
    birthdays.retire(record, now=utc_now())
    deleted_links = linked_repo.list_links_for_entity(current_user.user_id, LinkedEntityType.RECORD, record_id)
    cleanup_record_attachments_before_delete(
        current_user.user_id,
        record_id,
        attachment_repo,
        document_storage,
        linked_repo,
    )
    linked_repo.delete_links_for_entity(current_user.user_id, LinkedEntityType.RECORD, record_id)
    deleted = repo.delete_record(current_user.user_id, record_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    sync_linked_search_neighbors_safe(
        search_service,
        current_user.user_id,
        deleted_links,
        "record_delete_relationship_cleanup",
        excluded_entities={(LinkedEntityType.RECORD, record_id)},
    )
    delete_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, record_id, "record_delete")

    return Response(status_code=status.HTTP_204_NO_CONTENT)

@records_router.get("/records/{record_id}/protected/status", response_model=ProtectedRecordStatusResponse)
def get_protected_record_status(
    record_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
) -> ProtectedRecordStatusResponse:
    record = require_record(repo, current_user.user_id, record_id)
    return to_protected_record_status(record)

@records_router.put("/records/{record_id}/protected", response_model=ProtectedRecordStatusResponse)
def set_protected_record_payload(
    record_id: str,
    payload: ProtectedRecordPayload,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    encryption_service: EncryptionService = Depends(get_encryption_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> ProtectedRecordStatusResponse:
    record = require_record(repo, current_user.user_id, record_id)
    values = payload.safe_values()
    validate_protected_record_fields(record, values)
    now = utc_now()
    current_payload = decrypt_record_private_payload(record, encryption_service) if record_has_protected_data(record) else {}
    dynamic_values = protected_dynamic_values(current_payload)

    if not values and not dynamic_values:
        cleared = repo.update_record(clear_record_protected_fields(record, now))
        log_security_event(
            "protected_record_cleared",
            user_id=current_user.user_id,
            record_id=record.id,
            record_type=record.record_type.value,
            result="success",
        )
        sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, record.id, "protected_record_clear_via_put")
        return to_protected_record_status(cleared)

    next_payload = {**values}
    if dynamic_values:
        next_payload[DYNAMIC_PROTECTED_VALUES_KEY] = dynamic_values

    updated = encrypt_record_private_payload(record, next_payload, sorted(values.keys()), encryption_service, now)
    saved = repo.update_record(updated)
    log_security_event(
        "protected_record_set",
        user_id=current_user.user_id,
        record_id=record.id,
        record_type=record.record_type.value,
        result="success",
    )
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, record.id, "protected_record_set")
    return to_protected_record_status(saved)

@records_router.patch("/records/{record_id}/protected", response_model=ProtectedRecordStatusResponse)
def update_protected_record_payload(
    record_id: str,
    payload: ProtectedRecordPayload,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    encryption_service: EncryptionService = Depends(get_encryption_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> ProtectedRecordStatusResponse:
    record = require_record(repo, current_user.user_id, record_id)
    requested_fields = payload.model_fields_set
    if not requested_fields:
        return to_protected_record_status(record)

    current_payload = decrypt_record_private_payload(record, encryption_service) if record_has_protected_data(record) else {}
    allowed = protected_fields_for_record(record)
    legacy_values = {field: value for field, value in current_payload.items() if field in allowed and isinstance(value, str) and value}
    for field in requested_fields:
        if field not in allowed:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="This protected detail is not supported for this record type.")
        value = getattr(payload, field)
        if value is None:
            legacy_values.pop(field, None)
        else:
            legacy_values[field] = value

    validate_protected_record_fields(record, legacy_values)
    dynamic_values = protected_dynamic_values(current_payload)
    next_payload: dict[str, object] = {**legacy_values}
    if dynamic_values:
        next_payload[DYNAMIC_PROTECTED_VALUES_KEY] = dynamic_values
    now = utc_now()
    if next_payload:
        updated = encrypt_record_private_payload(record, next_payload, sorted(legacy_values.keys()), encryption_service, now)
    else:
        updated = clear_record_protected_fields(record, now)
    saved = repo.update_record(updated)
    log_security_event(
        "protected_record_updated",
        user_id=current_user.user_id,
        record_id=record.id,
        record_type=record.record_type.value,
        result="success",
    )
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, record.id, "protected_record_update")
    return to_protected_record_status(saved)

@records_router.get("/records/{record_id}/protected", response_model=ProtectedRecordPayload)
def reveal_protected_record_payload(
    record_id: str,
    response: Response,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    encryption_service: EncryptionService = Depends(get_encryption_service),
) -> ProtectedRecordPayload:
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    record = require_record(repo, current_user.user_id, record_id)

    if not record_has_protected_data(record):
        return ProtectedRecordPayload()

    try:
        decrypted = encryption_service.decrypt_json(record_encrypted_payload(record), record_encryption_context(record.user_id, record.id))
    except EncryptionConfigurationError as exc:
        log_security_event(
            "protected_record_decrypt_failed",
            user_id=current_user.user_id,
            record_id=record.id,
            record_type=record.record_type.value,
            result="configuration_missing",
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.safe_message) from exc
    except EncryptionOperationError as exc:
        log_security_event(
            "protected_record_decrypt_failed",
            user_id=current_user.user_id,
            record_id=record.id,
            record_type=record.record_type.value,
            result="decrypt_failed",
        )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.safe_message) from exc

    allowed = protected_fields_for_record(record)
    safe_payload = {field: value for field, value in decrypted.items() if field in allowed}
    log_security_event(
        "protected_record_revealed",
        user_id=current_user.user_id,
        record_id=record.id,
        record_type=record.record_type.value,
        result="success",
    )
    return ProtectedRecordPayload.model_validate(safe_payload)

@records_router.delete("/records/{record_id}/protected", response_model=ProtectedRecordStatusResponse)
def clear_protected_record_payload(
    record_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: RecordRepository = Depends(get_record_repository),
    encryption_service: EncryptionService = Depends(get_encryption_service),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> ProtectedRecordStatusResponse:
    record = require_record(repo, current_user.user_id, record_id)
    now = utc_now()
    current_payload = decrypt_record_private_payload(record, encryption_service) if record_has_protected_data(record) else {}
    dynamic_values = protected_dynamic_values(current_payload)
    if dynamic_values:
        updated = encrypt_record_private_payload(
            record,
            {DYNAMIC_PROTECTED_VALUES_KEY: dynamic_values},
            [],
            encryption_service,
            now,
        )
    else:
        updated = clear_record_protected_fields(record, now)

    cleared = repo.update_record(updated)
    log_security_event(
        "protected_record_cleared",
        user_id=current_user.user_id,
        record_id=record.id,
        record_type=record.record_type.value,
        result="success",
    )
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, record.id, "protected_record_clear")
    return to_protected_record_status(cleared)
