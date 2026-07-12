from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.linked_items_repository import LinkedItemRepository, linked_item_lookup_key
from app.models import LinkedItem, Record, Reminder
from app.records_repository import RecordRepository
from app.recurrence import calculate_status
from app.repository import ReminderRepository
from app.schemas import (
    LinkCreateRequest,
    LinkDirection,
    LinkedEntitySummary,
    LinkedEntityType,
    LinkedItemResponse,
    LinkedItemsResponse,
)


def get_entity_neighborhood(
    user_id: str,
    entity_type: LinkedEntityType,
    entity_id: str,
    linked_repo: LinkedItemRepository,
    record_repo: RecordRepository,
    reminder_repo: ReminderRepository,
    *,
    include_records: bool = True,
    include_reminders: bool = True,
) -> LinkedItemsResponse:
    links = linked_repo.list_links_for_entity(user_id, entity_type, entity_id)
    responses: list[LinkedItemResponse] = []

    for link in sorted(links, key=lambda item: item.created_at):
        response = resolve_link_response(
            user_id,
            entity_type,
            entity_id,
            link,
            record_repo,
            reminder_repo,
        )
        if response is not None:
            responses.append(response)

    return LinkedItemsResponse(
        records=[
            response
            for response in responses
            if include_records and response.linked_entity.entity_type == LinkedEntityType.RECORD
        ],
        reminders=[
            response
            for response in responses
            if include_reminders and response.linked_entity.entity_type == LinkedEntityType.REMINDER
        ],
    )


def create_record_link(
    user_id: str,
    source_record: Record,
    payload: LinkCreateRequest,
    linked_repo: LinkedItemRepository,
    record_repo: RecordRepository,
    reminder_repo: ReminderRepository,
    now: datetime,
) -> LinkedItemResponse:
    if payload.target_type == LinkedEntityType.RECORD:
        target_record = record_repo.get_record(user_id, payload.target_id)
        if target_record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target record not found")
        if target_record.id == source_record.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A record cannot be linked to itself")
        ensure_record_pair_not_linked(user_id, source_record.id, target_record.id, linked_repo)
        target_summary = record_summary(target_record)
    elif payload.target_type == LinkedEntityType.REMINDER:
        target_reminder = reminder_repo.get_reminder(user_id, payload.target_id)
        if target_reminder is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target reminder not found")
        if linked_repo.link_exists(
            user_id,
            LinkedEntityType.RECORD,
            source_record.id,
            LinkedEntityType.REMINDER,
            target_reminder.id,
        ):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This item is already linked")
        target_summary = reminder_summary(target_reminder)
    else:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported linked item type")

    link_id = str(uuid4())
    link = LinkedItem(
        user_id=user_id,
        link_id=link_id,
        source_type=LinkedEntityType.RECORD,
        source_id=source_record.id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        relationship_type=payload.relationship_type,
        label=payload.label,
        source_link_key=linked_item_lookup_key(LinkedEntityType.RECORD, source_record.id, link_id),
        target_link_key=linked_item_lookup_key(payload.target_type, payload.target_id, link_id),
        created_at=now,
        updated_at=now,
        created_by="user",
    )
    saved = linked_repo.create_link(link)
    return to_link_response(saved, LinkDirection.OUTBOUND, target_summary)


def resolve_link_response(
    user_id: str,
    current_type: LinkedEntityType,
    current_id: str,
    link: LinkedItem,
    record_repo: RecordRepository,
    reminder_repo: ReminderRepository,
) -> LinkedItemResponse | None:
    if link.source_type == current_type and link.source_id == current_id:
        direction = LinkDirection.OUTBOUND
        linked_type = link.target_type
        linked_id = link.target_id
    elif link.target_type == current_type and link.target_id == current_id:
        direction = LinkDirection.INBOUND
        linked_type = link.source_type
        linked_id = link.source_id
    else:
        return None

    summary = resolve_entity_summary(user_id, linked_type, linked_id, record_repo, reminder_repo)
    if summary is None:
        return None

    return to_link_response(link, direction, summary)


def resolve_entity_summary(
    user_id: str,
    entity_type: LinkedEntityType,
    entity_id: str,
    record_repo: RecordRepository,
    reminder_repo: ReminderRepository,
) -> LinkedEntitySummary | None:
    if entity_type == LinkedEntityType.RECORD:
        record = record_repo.get_record(user_id, entity_id)
        return record_summary(record) if record is not None else None

    if entity_type == LinkedEntityType.REMINDER:
        reminder = reminder_repo.get_reminder(user_id, entity_id)
        return reminder_summary(reminder) if reminder is not None else None

    return None


def ensure_record_pair_not_linked(
    user_id: str,
    source_record_id: str,
    target_record_id: str,
    linked_repo: LinkedItemRepository,
) -> None:
    for link in linked_repo.list_links_for_entity(user_id, LinkedEntityType.RECORD, source_record_id):
        same_direction = (
            link.source_type == LinkedEntityType.RECORD
            and link.source_id == source_record_id
            and link.target_type == LinkedEntityType.RECORD
            and link.target_id == target_record_id
        )
        reverse_direction = (
            link.source_type == LinkedEntityType.RECORD
            and link.source_id == target_record_id
            and link.target_type == LinkedEntityType.RECORD
            and link.target_id == source_record_id
        )
        if same_direction or reverse_direction:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This item is already linked")


def require_link_for_entity(
    user_id: str,
    link_id: str,
    entity_type: LinkedEntityType,
    entity_id: str,
    linked_repo: LinkedItemRepository,
) -> LinkedItem:
    link = linked_repo.get_link(user_id, link_id)
    if link is None or not link_involves_entity(link, entity_type, entity_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

    return link


def link_involves_entity(link: LinkedItem, entity_type: LinkedEntityType, entity_id: str) -> bool:
    return (
        (link.source_type == entity_type and link.source_id == entity_id)
        or (link.target_type == entity_type and link.target_id == entity_id)
    )


def record_summary(record: Record) -> LinkedEntitySummary:
    return LinkedEntitySummary(
        entity_type=LinkedEntityType.RECORD,
        id=record.id,
        title=record.title,
        subtitle=record.subtitle or record.provider_or_brand or record.owner_name or record.category,
        record_type=record.record_type,
        status=record.status,
    )


def reminder_summary(reminder: Reminder) -> LinkedEntitySummary:
    return LinkedEntitySummary(
        entity_type=LinkedEntityType.REMINDER,
        id=reminder.id,
        title=reminder.title,
        subtitle=reminder.category,
        reminder_type=reminder.reminder_type,
        status=calculate_status(reminder),
        due_date=reminder.due_date,
    )


def to_link_response(
    link: LinkedItem,
    direction: LinkDirection,
    linked_entity: LinkedEntitySummary,
) -> LinkedItemResponse:
    return LinkedItemResponse(
        link_id=link.link_id,
        relationship_type=link.relationship_type,
        label=link.label,
        direction=direction,
        linked_entity=linked_entity,
        created_at=link.created_at,
    )


def assert_supported_record_link(payload: LinkCreateRequest) -> None:
    if payload.target_type not in {LinkedEntityType.RECORD, LinkedEntityType.REMINDER}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported linked item type")
