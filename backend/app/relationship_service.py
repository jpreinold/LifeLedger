from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.attachments_repository import RecordAttachmentRepository, record_attachment_key
from app.linked_items_repository import (
    DuplicateLinkedItemError,
    LinkedItemRepository,
    canonical_pair_key,
    linked_item_lookup_key,
)
from app.models import LinkedItem, Record, RecordAttachment, Reminder
from app.records_repository import RecordRepository
from app.recurrence import calculate_status
from app.repository import ReminderRepository
from app.schemas import (
    AttachmentStatus,
    LinkCreateRequest,
    LinkDirection,
    LinkedEntitySummary,
    LinkedEntityType,
    LinkedItemResponse,
    LinkedItemsResponse,
    RecordStatus,
    RelationshipCandidate,
    RelationshipCandidatesResponse,
    RelationshipCreateRequest,
    RelationshipResponse,
    RelationshipType,
    RelationshipUpdateRequest,
)


@dataclass(frozen=True)
class RelationshipRepositories:
    linked_repo: LinkedItemRepository
    record_repo: RecordRepository
    reminder_repo: ReminderRepository
    attachment_repo: RecordAttachmentRepository | None = None


class ItemResolver:
    def __init__(
        self,
        record_repo: RecordRepository,
        reminder_repo: ReminderRepository,
        attachment_repo: RecordAttachmentRepository | None = None,
    ):
        self.record_repo = record_repo
        self.reminder_repo = reminder_repo
        self.attachment_repo = attachment_repo

    def require_summary(self, user_id: str, entity_type: LinkedEntityType, entity_id: str) -> LinkedEntitySummary:
        summary = self.resolve_summary(user_id, entity_type, entity_id)
        if summary is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{item_type_label(entity_type)} not found")
        return summary

    def resolve_summary(self, user_id: str, entity_type: LinkedEntityType, entity_id: str) -> LinkedEntitySummary | None:
        if entity_type == LinkedEntityType.RECORD:
            record = self.record_repo.get_record(user_id, entity_id)
            return record_summary(record) if record is not None else None

        if entity_type == LinkedEntityType.REMINDER:
            reminder = self.reminder_repo.get_reminder(user_id, entity_id)
            return reminder_summary(reminder) if reminder is not None else None

        if entity_type == LinkedEntityType.DOCUMENT:
            attachment = self.resolve_document(user_id, entity_id)
            if attachment is None:
                return None
            record = self.record_repo.get_record(user_id, attachment.record_id)
            return document_summary(attachment, record)

        return None

    def resolve_document(self, user_id: str, document_id: str) -> RecordAttachment | None:
        if self.attachment_repo is None:
            return None
        parsed = parse_document_item_id(document_id)
        if parsed is None:
            return None
        record_id, attachment_id = parsed
        attachment = self.attachment_repo.get_attachment(user_id, record_id, attachment_id)
        if attachment is None or attachment.status == AttachmentStatus.DELETED or attachment.deleted_at is not None:
            return None
        return attachment

    def candidates(
        self,
        user_id: str,
        source_type: LinkedEntityType,
        source_id: str,
        linked_repo: LinkedItemRepository,
        *,
        item_type: LinkedEntityType | None = None,
        query: str = "",
        include_archived: bool = False,
        limit: int = 25,
    ) -> RelationshipCandidatesResponse:
        self.require_summary(user_id, source_type, source_id)
        linked_keys = linked_item_member_keys_for_links(
            linked_repo.list_links_for_entity(user_id, source_type, source_id),
            source_type,
            source_id,
        )
        source_key = linked_item_member_key(source_type, source_id)
        query_text = query.strip().casefold()
        candidates: list[RelationshipCandidate] = []

        if item_type in (None, LinkedEntityType.RECORD):
            for record in self.record_repo.list_records(user_id, include_archived=include_archived):
                key = linked_item_member_key(LinkedEntityType.RECORD, record.id)
                if key == source_key or key in linked_keys:
                    continue
                if not include_archived and record.status == RecordStatus.ARCHIVED:
                    continue
                candidate = candidate_from_summary(record_summary(record))
                if candidate_matches(candidate, query_text):
                    candidates.append(candidate)

        if item_type in (None, LinkedEntityType.REMINDER):
            for reminder in self.reminder_repo.list_reminders(user_id):
                key = linked_item_member_key(LinkedEntityType.REMINDER, reminder.id)
                if key == source_key or key in linked_keys:
                    continue
                if not include_archived and reminder.archived_at is not None:
                    continue
                candidate = candidate_from_summary(reminder_summary(reminder))
                if candidate_matches(candidate, query_text):
                    candidates.append(candidate)

        if item_type in (None, LinkedEntityType.DOCUMENT) and self.attachment_repo is not None:
            records_by_id = {
                record.id: record
                for record in self.record_repo.list_records(user_id, include_archived=True)
                if include_archived or record.status != RecordStatus.ARCHIVED
            }
            for attachment in self.attachment_repo.list_for_user(user_id):
                if attachment.status == AttachmentStatus.DELETED or attachment.deleted_at is not None:
                    continue
                if attachment.record_id not in records_by_id:
                    continue
                document_id = document_item_id(attachment.record_id, attachment.attachment_id)
                key = linked_item_member_key(LinkedEntityType.DOCUMENT, document_id)
                if key == source_key or key in linked_keys:
                    continue
                candidate = candidate_from_summary(document_summary(attachment, records_by_id.get(attachment.record_id)))
                if candidate_matches(candidate, query_text):
                    candidates.append(candidate)

        candidates.sort(key=lambda item: (item.item_type.value, item.title.casefold(), item.item_id))
        return RelationshipCandidatesResponse(items=candidates[: max(1, min(limit, 50))])


def get_entity_neighborhood(
    user_id: str,
    entity_type: LinkedEntityType,
    entity_id: str,
    linked_repo: LinkedItemRepository,
    record_repo: RecordRepository,
    reminder_repo: ReminderRepository,
    attachment_repo: RecordAttachmentRepository | None = None,
    *,
    include_records: bool = True,
    include_reminders: bool = True,
    include_documents: bool = True,
) -> LinkedItemsResponse:
    resolver = ItemResolver(record_repo, reminder_repo, attachment_repo)
    links = linked_repo.list_links_for_entity(user_id, entity_type, entity_id)
    responses: list[LinkedItemResponse] = []

    for link in sorted(links, key=lambda item: item.created_at):
        response = resolve_link_response(user_id, entity_type, entity_id, link, resolver)
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
        documents=[
            response
            for response in responses
            if include_documents and response.linked_entity.entity_type == LinkedEntityType.DOCUMENT
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
    attachment_repo: RecordAttachmentRepository | None = None,
) -> LinkedItemResponse:
    relationship = create_relationship(
        user_id,
        RelationshipCreateRequest(
            source_item_type=LinkedEntityType.RECORD,
            source_item_id=source_record.id,
            target_item_type=payload.target_type,
            target_item_id=payload.target_id,
            relationship_type=payload.relationship_type,
            custom_label=payload.label,
        ),
        linked_repo,
        record_repo,
        reminder_repo,
        now,
        attachment_repo,
    )
    link = require_link(linked_repo, user_id, relationship.relationship_id)
    target_summary = relationship.target_item
    return to_link_response(link, LinkDirection.OUTBOUND, target_summary)


def create_relationship(
    user_id: str,
    payload: RelationshipCreateRequest,
    linked_repo: LinkedItemRepository,
    record_repo: RecordRepository,
    reminder_repo: ReminderRepository,
    now: datetime,
    attachment_repo: RecordAttachmentRepository | None = None,
) -> RelationshipResponse:
    if payload.source_item_type == payload.target_item_type and payload.source_item_id == payload.target_item_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An item cannot be linked to itself")

    resolver = ItemResolver(record_repo, reminder_repo, attachment_repo)
    source_summary = resolver.require_summary(user_id, payload.source_item_type, payload.source_item_id)
    target_summary = resolver.require_summary(user_id, payload.target_item_type, payload.target_item_id)

    if linked_repo.link_exists(
        user_id,
        payload.source_item_type,
        payload.source_item_id,
        payload.target_item_type,
        payload.target_item_id,
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This item is already linked")

    link_id = str(uuid4())
    pair_key = canonical_pair_key(
        payload.source_item_type,
        payload.source_item_id,
        payload.target_item_type,
        payload.target_item_id,
    )
    link = LinkedItem(
        user_id=user_id,
        link_id=link_id,
        source_type=payload.source_item_type,
        source_id=payload.source_item_id,
        target_type=payload.target_item_type,
        target_id=payload.target_item_id,
        relationship_type=payload.relationship_type,
        label=payload.custom_label,
        canonical_pair_key=pair_key,
        source_link_key=linked_item_lookup_key(payload.source_item_type, payload.source_item_id, link_id),
        target_link_key=linked_item_lookup_key(payload.target_item_type, payload.target_item_id, link_id),
        created_at=now,
        updated_at=now,
        created_by="user",
    )
    try:
        saved = linked_repo.create_link(link)
    except DuplicateLinkedItemError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This item is already linked") from exc

    return to_relationship_response(saved, source_summary, target_summary)


def read_relationship(
    user_id: str,
    relationship_id: str,
    linked_repo: LinkedItemRepository,
    record_repo: RecordRepository,
    reminder_repo: ReminderRepository,
    attachment_repo: RecordAttachmentRepository | None = None,
) -> RelationshipResponse:
    link = require_link(linked_repo, user_id, relationship_id)
    resolver = ItemResolver(record_repo, reminder_repo, attachment_repo)
    source_summary = resolver.require_summary(user_id, link.source_type, link.source_id)
    target_summary = resolver.require_summary(user_id, link.target_type, link.target_id)
    return to_relationship_response(link, source_summary, target_summary)


def update_relationship(
    user_id: str,
    relationship_id: str,
    payload: RelationshipUpdateRequest,
    linked_repo: LinkedItemRepository,
    record_repo: RecordRepository,
    reminder_repo: ReminderRepository,
    now: datetime,
    attachment_repo: RecordAttachmentRepository | None = None,
) -> RelationshipResponse:
    link = require_link(linked_repo, user_id, relationship_id)
    if payload.relationship_type is None and "custom_label" not in payload.model_fields_set:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No relationship updates supplied")

    updates: dict[str, object] = {"updated_at": now}
    if payload.relationship_type is not None:
        updates["relationship_type"] = payload.relationship_type
    if "custom_label" in payload.model_fields_set:
        updates["label"] = payload.custom_label

    updated = link.model_copy(update=updates)
    saved = linked_repo.update_link(updated)
    if saved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found")

    resolver = ItemResolver(record_repo, reminder_repo, attachment_repo)
    source_summary = resolver.require_summary(user_id, saved.source_type, saved.source_id)
    target_summary = resolver.require_summary(user_id, saved.target_type, saved.target_id)
    return to_relationship_response(saved, source_summary, target_summary)


def delete_relationship(user_id: str, relationship_id: str, linked_repo: LinkedItemRepository) -> LinkedItem:
    link = require_link(linked_repo, user_id, relationship_id)
    linked_repo.delete_link(user_id, relationship_id)
    return link


def resolve_link_response(
    user_id: str,
    current_type: LinkedEntityType,
    current_id: str,
    link: LinkedItem,
    resolver: ItemResolver,
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

    summary = resolver.resolve_summary(user_id, linked_type, linked_id)
    if summary is None:
        return None

    return to_link_response(link, direction, summary)


def require_link_for_entity(
    user_id: str,
    link_id: str,
    entity_type: LinkedEntityType,
    entity_id: str,
    linked_repo: LinkedItemRepository,
) -> LinkedItem:
    link = require_link(linked_repo, user_id, link_id)
    if not link_involves_entity(link, entity_type, entity_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    return link


def require_link(linked_repo: LinkedItemRepository, user_id: str, link_id: str) -> LinkedItem:
    link = linked_repo.get_link(user_id, link_id)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found")
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
        item_date=reminder.due_date,
    )


def document_summary(attachment: RecordAttachment, record: Record | None) -> LinkedEntitySummary:
    return LinkedEntitySummary(
        entity_type=LinkedEntityType.DOCUMENT,
        id=document_item_id(attachment.record_id, attachment.attachment_id),
        title=attachment.display_name,
        subtitle=record.title if record is not None else "Document",
        status=attachment.status,
        item_date=attachment.available_at.date() if attachment.available_at is not None else attachment.created_at.date(),
        document_record_id=attachment.record_id,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
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


def to_relationship_response(
    link: LinkedItem,
    source_summary: LinkedEntitySummary,
    target_summary: LinkedEntitySummary,
) -> RelationshipResponse:
    return RelationshipResponse(
        relationship_id=link.link_id,
        relationship_type=link.relationship_type,
        custom_label=link.label,
        source_item=source_summary,
        target_item=target_summary,
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


def assert_supported_record_link(payload: LinkCreateRequest) -> None:
    if payload.target_type not in {LinkedEntityType.RECORD, LinkedEntityType.REMINDER, LinkedEntityType.DOCUMENT}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported linked item type")


def document_item_id(record_id: str, attachment_id: str) -> str:
    return record_attachment_key(record_id, attachment_id)


def parse_document_item_id(document_id: str) -> tuple[str, str] | None:
    if "#" not in document_id:
        return None
    record_id, attachment_id = document_id.split("#", 1)
    if not record_id or not attachment_id:
        return None
    return record_id, attachment_id


def linked_item_member_key(entity_type: LinkedEntityType, entity_id: str) -> str:
    return f"{entity_type.value}#{entity_id}"


def linked_item_member_keys_for_links(
    links: list[LinkedItem],
    source_type: LinkedEntityType,
    source_id: str,
) -> set[str]:
    keys: set[str] = set()
    for link in links:
        if link.source_type == source_type and link.source_id == source_id:
            keys.add(linked_item_member_key(link.target_type, link.target_id))
        elif link.target_type == source_type and link.target_id == source_id:
            keys.add(linked_item_member_key(link.source_type, link.source_id))
    return keys


def candidate_from_summary(summary: LinkedEntitySummary) -> RelationshipCandidate:
    return RelationshipCandidate(
        item_type=summary.entity_type,
        item_id=summary.id,
        title=summary.title,
        subtitle=summary.subtitle,
        status=summary.status,
        item_date=summary.item_date or summary.due_date,
        record_type=summary.record_type,
        reminder_type=summary.reminder_type,
        document_record_id=summary.document_record_id,
    )


def candidate_matches(candidate: RelationshipCandidate, query: str) -> bool:
    if not query:
        return True
    values = [candidate.title, candidate.subtitle, candidate.status, candidate.item_type.value]
    return any(value and query in value.casefold() for value in values)


def item_type_label(entity_type: LinkedEntityType) -> str:
    labels = {
        LinkedEntityType.RECORD: "Record",
        LinkedEntityType.REMINDER: "Reminder",
        LinkedEntityType.DOCUMENT: "Document",
    }
    return labels.get(entity_type, "Item")