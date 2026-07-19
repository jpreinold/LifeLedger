from fastapi import APIRouter

from app.route_support import *  # noqa: F403

router = APIRouter(tags=["relationships"])
relationships_router = router

@relationships_router.get("/records/{record_id}/links", response_model=LinkedItemsResponse)
def list_record_links(
    record_id: str,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    reminder_repo: ReminderRepository = Depends(get_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
) -> LinkedItemsResponse:
    require_record(record_repo, current_user.user_id, record_id)
    return get_entity_neighborhood(
        current_user.user_id,
        LinkedEntityType.RECORD,
        record_id,
        linked_repo,
        record_repo,
        reminder_repo,
        attachment_repo,
    )

@relationships_router.post("/records/{record_id}/links", response_model=LinkedItemResponse, status_code=status.HTTP_201_CREATED)
def add_record_link(
    record_id: str,
    payload: LinkCreateRequest,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    reminder_repo: ReminderRepository = Depends(get_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> LinkedItemResponse:
    source_record = require_record(record_repo, current_user.user_id, record_id)
    assert_supported_record_link(payload)
    response = create_record_link(
        current_user.user_id,
        source_record,
        payload,
        linked_repo,
        record_repo,
        reminder_repo,
        utc_now(),
        attachment_repo,
    )
    log_security_event(
        "linked_item_created",
        user_id=current_user.user_id,
        source_type=LinkedEntityType.RECORD.value,
        source_id=record_id,
        target_type=payload.target_type.value,
        target_id=payload.target_id,
        relationship_type=payload.relationship_type.value,
        result="created",
    )
    sync_search_entity_safe(search_service, current_user.user_id, LinkedEntityType.RECORD, record_id, "relationship_create")
    sync_search_entity_safe(search_service, current_user.user_id, payload.target_type, payload.target_id, "relationship_create")
    return response

@relationships_router.delete("/records/{record_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_record_link(
    record_id: str,
    link_id: str,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> Response:
    require_record(record_repo, current_user.user_id, record_id)
    link = require_link_for_entity(current_user.user_id, link_id, LinkedEntityType.RECORD, record_id, linked_repo)
    linked_repo.delete_link(current_user.user_id, link_id)
    log_security_event(
        "linked_item_removed",
        user_id=current_user.user_id,
        source_type=link.source_type.value,
        source_id=link.source_id,
        target_type=link.target_type.value,
        target_id=link.target_id,
        relationship_type=link.relationship_type.value,
        result="removed",
    )
    sync_search_entity_safe(search_service, current_user.user_id, link.source_type, link.source_id, "relationship_delete")
    sync_search_entity_safe(search_service, current_user.user_id, link.target_type, link.target_id, "relationship_delete")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@relationships_router.get("/relationships/candidates", response_model=RelationshipCandidatesResponse)
def list_relationship_candidates(
    source_item_type: LinkedEntityType = Query(...),
    source_item_id: str = Query(..., min_length=1, max_length=240),
    item_type: LinkedEntityType | None = Query(default=None),
    q: str = Query(default="", max_length=120),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=25, ge=1, le=50),
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    reminder_repo: ReminderRepository = Depends(get_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
) -> RelationshipCandidatesResponse:
    resolver = ItemResolver(record_repo, reminder_repo, attachment_repo)
    return resolver.candidates(
        current_user.user_id,
        source_item_type,
        source_item_id,
        linked_repo,
        item_type=item_type,
        query=q,
        include_archived=include_archived,
        limit=limit,
    )

@relationships_router.post("/relationships", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED)
def create_relationship_route(
    payload: RelationshipCreateRequest,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    reminder_repo: ReminderRepository = Depends(get_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> RelationshipResponse:
    response = create_relationship(
        current_user.user_id,
        payload,
        linked_repo,
        record_repo,
        reminder_repo,
        utc_now(),
        attachment_repo,
    )
    log_security_event(
        "relationship_created",
        user_id=current_user.user_id,
        relationship_id=response.relationship_id,
        source_type=payload.source_item_type.value,
        target_type=payload.target_item_type.value,
        relationship_type=payload.relationship_type.value,
        result="created",
    )
    sync_search_entity_safe(search_service, current_user.user_id, payload.source_item_type, payload.source_item_id, "relationship_create")
    sync_search_entity_safe(search_service, current_user.user_id, payload.target_item_type, payload.target_item_id, "relationship_create")
    return response

@relationships_router.get("/relationships/{relationship_id}", response_model=RelationshipResponse)
def get_relationship_route(
    relationship_id: str,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    reminder_repo: ReminderRepository = Depends(get_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
) -> RelationshipResponse:
    return read_relationship(
        current_user.user_id,
        relationship_id,
        linked_repo,
        record_repo,
        reminder_repo,
        attachment_repo,
    )

@relationships_router.patch("/relationships/{relationship_id}", response_model=RelationshipResponse)
def update_relationship_route(
    relationship_id: str,
    payload: RelationshipUpdateRequest,
    current_user: UserContext = Depends(get_current_user),
    record_repo: RecordRepository = Depends(get_record_repository),
    reminder_repo: ReminderRepository = Depends(get_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> RelationshipResponse:
    response = update_relationship(
        current_user.user_id,
        relationship_id,
        payload,
        linked_repo,
        record_repo,
        reminder_repo,
        utc_now(),
        attachment_repo,
    )
    log_security_event(
        "relationship_updated",
        user_id=current_user.user_id,
        relationship_id=relationship_id,
        relationship_type=response.relationship_type.value,
        result="updated",
    )
    sync_search_entity_safe(search_service, current_user.user_id, response.source_item.entity_type, response.source_item.id, "relationship_update")
    sync_search_entity_safe(search_service, current_user.user_id, response.target_item.entity_type, response.target_item.id, "relationship_update")
    return response

@relationships_router.delete("/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relationship_route(
    relationship_id: str,
    current_user: UserContext = Depends(get_current_user),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> Response:
    link = delete_relationship(current_user.user_id, relationship_id, linked_repo)
    log_security_event(
        "relationship_removed",
        user_id=current_user.user_id,
        relationship_id=relationship_id,
        source_type=link.source_type.value,
        target_type=link.target_type.value,
        relationship_type=link.relationship_type.value,
        result="removed",
    )
    sync_search_entity_safe(search_service, current_user.user_id, link.source_type, link.source_id, "relationship_delete")
    sync_search_entity_safe(search_service, current_user.user_id, link.target_type, link.target_id, "relationship_delete")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@relationships_router.get("/reminders/{reminder_id}/links", response_model=LinkedItemsResponse)
def list_reminder_links(
    reminder_id: str,
    current_user: UserContext = Depends(get_current_user),
    reminder_repo: ReminderRepository = Depends(get_repository),
    record_repo: RecordRepository = Depends(get_record_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    attachment_repo: RecordAttachmentRepository = Depends(get_record_attachment_repository),
) -> LinkedItemsResponse:
    require_reminder(reminder_repo, current_user.user_id, reminder_id)
    return get_entity_neighborhood(
        current_user.user_id,
        LinkedEntityType.REMINDER,
        reminder_id,
        linked_repo,
        record_repo,
        reminder_repo,
        attachment_repo,
        include_reminders=False,
    )

@relationships_router.delete("/reminders/{reminder_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_reminder_link(
    reminder_id: str,
    link_id: str,
    current_user: UserContext = Depends(get_current_user),
    reminder_repo: ReminderRepository = Depends(get_repository),
    linked_repo: LinkedItemRepository = Depends(get_linked_item_repository),
    search_service: SearchProjectionService = Depends(get_search_projection_service),
) -> Response:
    require_reminder(reminder_repo, current_user.user_id, reminder_id)
    link = require_link_for_entity(current_user.user_id, link_id, LinkedEntityType.REMINDER, reminder_id, linked_repo)
    linked_repo.delete_link(current_user.user_id, link_id)
    log_security_event(
        "linked_item_removed",
        user_id=current_user.user_id,
        source_type=link.source_type.value,
        source_id=link.source_id,
        target_type=link.target_type.value,
        target_id=link.target_id,
        relationship_type=link.relationship_type.value,
        result="removed",
    )
    sync_search_entity_safe(search_service, current_user.user_id, link.source_type, link.source_id, "relationship_delete")
    sync_search_entity_safe(search_service, current_user.user_id, link.target_type, link.target_id, "relationship_delete")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
