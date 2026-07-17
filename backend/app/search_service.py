from __future__ import annotations

import base64
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from app.attachments_repository import RecordAttachmentRepository
from app.models import Record, RecordAttachment, Reminder, SavedSearchView, SearchProjection
from app.records_repository import RecordRepository
from app.recurrence import calculate_status, get_effective_attention_date
from app.relationship_service import ItemResolver, document_item_id, parse_document_item_id
from app.repository import ReminderRepository
from app.schemas import AttachmentStatus, DynamicFieldType, LinkedEntityType, RecordStatus, SearchResponse, SearchResultItem, SearchSort
from app.search_repository import SavedSearchViewRepository, SearchIndexRepository

SEARCH_PROJECTION_VERSION = 1
MAX_QUERY_LENGTH = 120
MAX_QUERY_TOKENS = 8
MAX_TOKEN_LENGTH = 32
MAX_PROJECTION_TOKENS = 80
MAX_TOKEN_CANDIDATES = 300
MAX_FILTER_CANDIDATES = 600
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
DUE_SOON_DAYS = 30
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
PRIVATE_DYNAMIC_VALUE_TYPES = {
    DynamicFieldType.LONG_TEXT,
    DynamicFieldType.PHONE,
    DynamicFieldType.EMAIL,
    DynamicFieldType.URL,
    DynamicFieldType.NUMBER,
    DynamicFieldType.MONEY,
}


class SearchValidationError(ValueError):
    pass


@dataclass(frozen=True)
class SearchRequest:
    query: str = ""
    item_types: tuple[LinkedEntityType, ...] = ()
    statuses: tuple[str, ...] = ()
    include_archived: bool = False
    date_from: date | None = None
    date_to: date | None = None
    category: str | None = None
    owner: str | None = None
    has_documents: bool | None = None
    has_linked_items: bool | None = None
    sort: SearchSort = SearchSort.RELEVANCE
    page_size: int = DEFAULT_PAGE_SIZE
    cursor: str | None = None


@dataclass(frozen=True)
class BackfillResult:
    user_id: str
    records_indexed: int = 0
    documents_indexed: int = 0
    reminders_indexed: int = 0
    skipped: int = 0
    dry_run: bool = False

    @property
    def total_indexed(self) -> int:
        return self.records_indexed + self.documents_indexed + self.reminders_indexed


def normalize_search_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).casefold().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize_search_text(value: object, *, max_tokens: int = MAX_PROJECTION_TOKENS) -> list[str]:
    normalized = normalize_search_text(value)
    if not normalized:
        return []
    tokens: list[str] = []
    seen: set[str] = set()
    for match in TOKEN_PATTERN.finditer(normalized):
        token = match.group(0)[:MAX_TOKEN_LENGTH]
        if not token or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
        if len(tokens) >= max_tokens:
            break
    return tokens


def record_search_item_id(record_id: str) -> str:
    return f"record#{record_id}"


def reminder_search_item_id(reminder_id: str) -> str:
    return f"reminder#{reminder_id}"


def document_search_item_id(record_id: str, attachment_id: str) -> str:
    return f"document#{record_id}#{attachment_id}"


def parse_csv_values(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    values: list[str] = []
    seen: set[str] = set()
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        values.append(item)
    return tuple(values)


def parse_item_types(value: str | None) -> tuple[LinkedEntityType, ...]:
    item_types: list[LinkedEntityType] = []
    for item in parse_csv_values(value):
        try:
            item_types.append(LinkedEntityType(item))
        except ValueError as exc:
            raise SearchValidationError(f"Unsupported item type: {item}") from exc
    return tuple(item_types)


def normalize_status_values(value: str | None) -> tuple[str, ...]:
    return tuple(normalize_status_value(item) for item in parse_csv_values(value))


def normalize_status_value(value: str | None) -> str:
    normalized = normalize_search_text(value).replace(" ", "_")
    aliases = {
        "due_today": "due_today",
        "due_soon": "due_soon",
        "upcoming": "due_soon",
        "scheduled": "scheduled",
        "overdue": "overdue",
        "active": "active",
        "archived": "archived",
        "completed": "completed",
        "available": "available",
        "scanning": "scanning",
        "pending_upload": "pending_upload",
        "uploaded": "uploaded",
        "rejected": "rejected",
        "scan_failed": "scan_failed",
    }
    if normalized not in aliases:
        raise SearchValidationError(f"Unsupported status filter: {value}")
    return aliases[normalized]


def validate_search_request(
    *,
    query: str = "",
    item_types: str | None = None,
    statuses: str | None = None,
    include_archived: bool = False,
    date_from: date | None = None,
    date_to: date | None = None,
    category: str | None = None,
    owner: str | None = None,
    has_documents: bool | None = None,
    has_linked_items: bool | None = None,
    sort: SearchSort = SearchSort.RELEVANCE,
    page_size: int = DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
) -> SearchRequest:
    normalized_query = (query or "").strip()[:MAX_QUERY_LENGTH]
    if date_from is not None and date_to is not None and date_from > date_to:
        raise SearchValidationError("dateFrom must be before dateTo")
    return SearchRequest(
        query=normalized_query,
        item_types=parse_item_types(item_types),
        statuses=normalize_status_values(statuses),
        include_archived=include_archived,
        date_from=date_from,
        date_to=date_to,
        category=category.strip() if category and category.strip() else None,
        owner=owner.strip() if owner and owner.strip() else None,
        has_documents=has_documents,
        has_linked_items=has_linked_items,
        sort=sort,
        page_size=max(1, min(page_size, MAX_PAGE_SIZE)),
        cursor=cursor,
    )


class ProjectionTokenCollector:
    def __init__(self):
        self.title_tokens: list[str] = []
        self.metadata_tokens: list[str] = []
        self.custom_field_name_tokens: list[str] = []
        self.relationship_tokens: list[str] = []
        self.linked_context_tokens: list[str] = []
        self.token_contexts: dict[str, list[str]] = {}

    @property
    def all_tokens(self) -> list[str]:
        tokens: list[str] = []
        seen: set[str] = set()
        for bucket in (self.title_tokens, self.metadata_tokens, self.custom_field_name_tokens, self.relationship_tokens, self.linked_context_tokens):
            for token in bucket:
                if token in seen:
                    continue
                seen.add(token)
                tokens.append(token)
                if len(tokens) >= MAX_PROJECTION_TOKENS:
                    return tokens
        return tokens

    def add_title(self, value: object) -> None:
        self._add(value, self.title_tokens, "Matched title")

    def add_metadata(self, value: object, context: str | None = None) -> None:
        self._add(value, self.metadata_tokens, context)

    def add_custom_field_name(self, value: object, label: str) -> None:
        self._add(value, self.custom_field_name_tokens, f"Matched field: {label}")

    def add_relationship(self, value: object, label: str) -> None:
        self._add(value, self.relationship_tokens, f"Matched relationship: {label}")

    def add_linked_context(self, value: object, title: str) -> None:
        self._add(value, self.linked_context_tokens, f"Linked to {title}")

    def _add(self, value: object, bucket: list[str], context: str | None) -> None:
        for token in tokenize_search_text(value):
            if token not in bucket:
                bucket.append(token)
            if context:
                contexts = self.token_contexts.setdefault(token, [])
                if context not in contexts:
                    contexts.append(context)


class SearchProjectionService:
    def __init__(self, index_repo: SearchIndexRepository, record_repo: RecordRepository, reminder_repo: ReminderRepository, attachment_repo: RecordAttachmentRepository, linked_repo):
        self.index_repo = index_repo
        self.record_repo = record_repo
        self.reminder_repo = reminder_repo
        self.attachment_repo = attachment_repo
        self.linked_repo = linked_repo

    def build_record_projection(self, record: Record) -> SearchProjection:
        collector = ProjectionTokenCollector()
        collector.add_title(record.title)
        collector.add_metadata(record.subtitle, "Matched subtitle")
        collector.add_metadata(record.category, f"Matched category: {record.category}")
        collector.add_metadata(record.record_type.value.replace("_", " "), "Matched record type")
        collector.add_metadata(record.owner_name, "Matched owner")
        collector.add_metadata(record.provider_or_brand, "Matched provider")
        collector.add_metadata(record.location_hint, "Matched location")
        for tag in record.tags:
            collector.add_metadata(tag, f"Matched tag: {tag}")
        for field in record.dynamic_fields:
            collector.add_custom_field_name(field.label, field.label)
            if is_safe_dynamic_field_value(field):
                collector.add_metadata(field.value, f"Matched field: {field.label}")
        has_links = self._add_relationship_context(record.user_id, LinkedEntityType.RECORD, record.id, collector)
        attachments = self.attachment_repo.list_for_record(record.user_id, record.id)
        has_documents = any(is_searchable_attachment(attachment) for attachment in attachments)
        relevant_date = first_date(record.expiration_date, record.renewal_date, record.purchase_date, record.issue_date, record.start_date)
        subtitle = record.subtitle or record.provider_or_brand or record.owner_name or record.category
        return SearchProjection(
            user_id=record.user_id,
            search_item_id=record_search_item_id(record.id),
            source_item_id=record.id,
            source_item_type=LinkedEntityType.RECORD,
            normalized_title=normalize_search_text(record.title),
            display_title=record.title,
            normalized_search_tokens=collector.all_tokens,
            title_tokens=collector.title_tokens,
            metadata_tokens=collector.metadata_tokens,
            custom_field_name_tokens=collector.custom_field_name_tokens,
            relationship_tokens=collector.relationship_tokens,
            linked_context_tokens=collector.linked_context_tokens,
            token_contexts=collector.token_contexts,
            safe_display_metadata=compact_metadata(type="Record", subtitle=subtitle, category=record.category, owner=record.owner_name, provider=record.provider_or_brand),
            category=record.category,
            status=record.status.value,
            owner_or_person=record.owner_name,
            relevant_date=relevant_date,
            has_documents=has_documents,
            has_linked_items=has_links,
            archived=record.status == RecordStatus.ARCHIVED,
            created_at=record.created_at,
            updated_at=record.updated_at,
            navigation_metadata={"record_id": record.id},
            projection_version=SEARCH_PROJECTION_VERSION,
        )

    def build_reminder_projection(self, reminder: Reminder) -> SearchProjection:
        collector = ProjectionTokenCollector()
        collector.add_title(reminder.title)
        collector.add_metadata(reminder.category.value, f"Matched category: {reminder.category.value}")
        collector.add_metadata(reminder.reminder_type.value.replace("_", " "), "Matched reminder type")
        owner_or_person = reminder_owner_or_person(reminder)
        collector.add_metadata(owner_or_person, "Matched person")
        for value, context in reminder_safe_metadata(reminder):
            collector.add_metadata(value, context)
        has_links = self._add_relationship_context(reminder.user_id, LinkedEntityType.REMINDER, reminder.id, collector)
        links = self.linked_repo.list_links_for_entity(reminder.user_id, LinkedEntityType.REMINDER, reminder.id)
        has_documents = any(link_involves_type(link, LinkedEntityType.DOCUMENT) for link in links)
        status_value = normalize_status_value(calculate_status(reminder).value)
        relevant_date = get_effective_attention_date(reminder)
        return SearchProjection(
            user_id=reminder.user_id,
            search_item_id=reminder_search_item_id(reminder.id),
            source_item_id=reminder.id,
            source_item_type=LinkedEntityType.REMINDER,
            normalized_title=normalize_search_text(reminder.title),
            display_title=reminder.title,
            normalized_search_tokens=collector.all_tokens,
            title_tokens=collector.title_tokens,
            metadata_tokens=collector.metadata_tokens,
            custom_field_name_tokens=collector.custom_field_name_tokens,
            relationship_tokens=collector.relationship_tokens,
            linked_context_tokens=collector.linked_context_tokens,
            token_contexts=collector.token_contexts,
            safe_display_metadata=compact_metadata(type="Reminder", subtitle=reminder.category.value, category=reminder.category.value, owner=owner_or_person),
            category=reminder.category.value,
            status=status_value,
            owner_or_person=owner_or_person,
            relevant_date=relevant_date,
            has_documents=has_documents,
            has_linked_items=has_links,
            archived=reminder.archived_at is not None,
            created_at=reminder.created_at,
            updated_at=reminder.updated_at,
            navigation_metadata={"reminder_id": reminder.id},
            projection_version=SEARCH_PROJECTION_VERSION,
        )

    def build_document_projection(self, attachment: RecordAttachment) -> SearchProjection | None:
        if not is_searchable_attachment(attachment):
            return None
        record = self.record_repo.get_record(attachment.user_id, attachment.record_id)
        if record is None:
            return None
        collector = ProjectionTokenCollector()
        collector.add_title(attachment.display_name)
        collector.add_metadata("document", "Matched item type")
        collector.add_metadata(attachment.content_type, "Matched content type")
        collector.add_metadata(record.title, f"Linked to {record.title}")
        collector.add_metadata(record.category, f"Matched category: {record.category}")
        source_item_id = document_item_id(attachment.record_id, attachment.attachment_id)
        has_links = self._add_relationship_context(attachment.user_id, LinkedEntityType.DOCUMENT, source_item_id, collector)
        relevant_date = attachment.available_at.date() if attachment.available_at else attachment.created_at.date()
        return SearchProjection(
            user_id=attachment.user_id,
            search_item_id=document_search_item_id(attachment.record_id, attachment.attachment_id),
            source_item_id=source_item_id,
            source_item_type=LinkedEntityType.DOCUMENT,
            normalized_title=normalize_search_text(attachment.display_name),
            display_title=attachment.display_name,
            normalized_search_tokens=collector.all_tokens,
            title_tokens=collector.title_tokens,
            metadata_tokens=collector.metadata_tokens,
            custom_field_name_tokens=collector.custom_field_name_tokens,
            relationship_tokens=collector.relationship_tokens,
            linked_context_tokens=collector.linked_context_tokens,
            token_contexts=collector.token_contexts,
            safe_display_metadata=compact_metadata(type="Document", subtitle=record.title, category=record.category, content_type=attachment.content_type),
            category=record.category,
            status=attachment.status.value,
            owner_or_person=record.owner_name,
            relevant_date=relevant_date,
            has_documents=False,
            has_linked_items=has_links,
            archived=record.status == RecordStatus.ARCHIVED,
            created_at=attachment.created_at,
            updated_at=attachment.available_at or attachment.uploaded_at or attachment.created_at,
            navigation_metadata={"record_id": attachment.record_id, "attachment_id": attachment.attachment_id, "document_id": source_item_id},
            projection_version=SEARCH_PROJECTION_VERSION,
        )

    def upsert_record(self, record: Record) -> SearchProjection:
        return self.index_repo.upsert_projection(self.build_record_projection(record))

    def upsert_reminder(self, reminder: Reminder) -> SearchProjection:
        return self.index_repo.upsert_projection(self.build_reminder_projection(reminder))

    def upsert_document(self, attachment: RecordAttachment) -> SearchProjection | None:
        projection = self.build_document_projection(attachment)
        if projection is None:
            self.delete_document(attachment.user_id, attachment.record_id, attachment.attachment_id)
            return None
        return self.index_repo.upsert_projection(projection)

    def sync_entity(self, user_id: str, entity_type: LinkedEntityType, entity_id: str) -> None:
        if entity_type == LinkedEntityType.RECORD:
            record = self.record_repo.get_record(user_id, entity_id)
            self.upsert_record(record) if record else self.delete_record(user_id, entity_id)
            return
        if entity_type == LinkedEntityType.REMINDER:
            reminder = self.reminder_repo.get_reminder(user_id, entity_id)
            self.upsert_reminder(reminder) if reminder else self.delete_reminder(user_id, entity_id)
            return
        parsed = parse_document_item_id(entity_id)
        if parsed is None:
            return
        record_id, attachment_id = parsed
        attachment = self.attachment_repo.get_attachment(user_id, record_id, attachment_id)
        self.upsert_document(attachment) if attachment else self.delete_document(user_id, record_id, attachment_id)

    def delete_record(self, user_id: str, record_id: str) -> None:
        for attachment in self.attachment_repo.list_for_record(user_id, record_id):
            self.delete_document(user_id, record_id, attachment.attachment_id)
        self.index_repo.delete_projection(user_id, record_search_item_id(record_id))

    def delete_reminder(self, user_id: str, reminder_id: str) -> None:
        self.index_repo.delete_projection(user_id, reminder_search_item_id(reminder_id))

    def delete_document(self, user_id: str, record_id: str, attachment_id: str) -> None:
        self.index_repo.delete_projection(user_id, document_search_item_id(record_id, attachment_id))

    def rebuild_user(self, user_id: str, *, dry_run: bool = False) -> BackfillResult:
        records_indexed = documents_indexed = reminders_indexed = skipped = 0
        for record in self.record_repo.list_records(user_id, include_archived=True):
            records_indexed += 1
            if not dry_run:
                self.upsert_record(record)
        for attachment in self.attachment_repo.list_for_user(user_id):
            projection = self.build_document_projection(attachment)
            if projection is None:
                skipped += 1
                continue
            documents_indexed += 1
            if not dry_run:
                self.index_repo.upsert_projection(projection)
        for reminder in self.reminder_repo.list_reminders(user_id):
            reminders_indexed += 1
            if not dry_run:
                self.upsert_reminder(reminder)
        return BackfillResult(user_id, records_indexed, documents_indexed, reminders_indexed, skipped, dry_run)

    def _add_relationship_context(self, user_id: str, entity_type: LinkedEntityType, entity_id: str, collector: ProjectionTokenCollector) -> bool:
        links = self.linked_repo.list_links_for_entity(user_id, entity_type, entity_id)
        if not links:
            return False
        resolver = ItemResolver(self.record_repo, self.reminder_repo, self.attachment_repo)
        for link in links:
            relationship_label = link.label or relationship_type_label(link.relationship_type.value)
            collector.add_relationship(relationship_label, relationship_label)
            linked_type, linked_id = opposite_link_endpoint(link, entity_type, entity_id)
            if linked_type is None or linked_id is None:
                continue
            summary = resolver.resolve_summary(user_id, linked_type, linked_id)
            if summary is not None:
                collector.add_linked_context(summary.title, summary.title)
        return True


class SearchQueryService:
    def __init__(self, index_repo: SearchIndexRepository):
        self.index_repo = index_repo

    def search(self, user_id: str, request: SearchRequest) -> SearchResponse:
        query_tokens = tokenize_search_text(request.query, max_tokens=MAX_QUERY_TOKENS)
        candidate_ids = self._candidate_ids(user_id, query_tokens)
        projections = self.index_repo.batch_get_projections(user_id, candidate_ids)
        filtered = [projection for projection in projections if projection_matches_request(projection, request)]
        scored = [(projection_score(projection, request.query, query_tokens), projection) for projection in filtered]
        scored.sort(key=lambda item: projection_sort_key(item[1], item[0], request.sort))
        offset = decode_cursor(request.cursor, request_fingerprint(request)) if request.cursor else 0
        page = scored[offset : offset + request.page_size]
        next_offset = offset + request.page_size
        next_cursor = encode_cursor(next_offset, request_fingerprint(request)) if next_offset < len(scored) else None
        return SearchResponse(
            items=[projection_to_result(projection, request.query, query_tokens) for _score, projection in page],
            next_cursor=next_cursor,
            applied_filters=applied_filters(request),
            result_count=len(filtered),
        )

    def _candidate_ids(self, user_id: str, query_tokens: list[str]) -> list[str]:
        if not query_tokens:
            return self.index_repo.list_projection_ids_for_user(user_id, MAX_FILTER_CANDIDATES)
        token_matches = [self.index_repo.list_projection_ids_for_token_prefix(user_id, token, MAX_TOKEN_CANDIDATES) for token in query_tokens]
        if not token_matches or any(not matches for matches in token_matches):
            return []
        common = set(token_matches[0])
        for matches in token_matches[1:]:
            common.intersection_update(matches)
        ordered: list[str] = []
        for search_item_id in token_matches[0]:
            if search_item_id in common and search_item_id not in ordered:
                ordered.append(search_item_id)
        return ordered


class SavedSearchViewService:
    def __init__(self, repo: SavedSearchViewRepository):
        self.repo = repo

    def list_views(self, user_id: str) -> list[SavedSearchView]:
        return sorted(self.repo.list_views(user_id), key=lambda view: (not view.is_pinned, view.name.casefold(), view.created_at))

    def get_view(self, user_id: str, saved_view_id: str) -> SavedSearchView | None:
        return self.repo.get_view(user_id, saved_view_id)

    def create_view(self, *, user_id: str, saved_view_id: str, name: str, query: str, filters: dict[str, object], sort: SearchSort, icon: str | None, is_pinned: bool, now: datetime) -> SavedSearchView:
        view = SavedSearchView(
            saved_view_id=saved_view_id,
            user_id=user_id,
            name=name.strip(),
            query=query.strip(),
            filters=validated_saved_view_filters(filters),
            sort=sort.value,
            icon=icon.strip() if icon and icon.strip() else None,
            is_pinned=is_pinned,
            created_at=now,
            updated_at=now,
        )
        return self.repo.create_view(view)

    def update_view(self, view: SavedSearchView, *, name: str | None = None, query: str | None = None, filters: dict[str, object] | None = None, sort: SearchSort | None = None, icon: str | None = None, is_pinned: bool | None = None, now: datetime) -> SavedSearchView | None:
        updates: dict[str, object] = {"updated_at": now}
        if name is not None:
            updates["name"] = name.strip()
        if query is not None:
            updates["query"] = query.strip()
        if filters is not None:
            updates["filters"] = validated_saved_view_filters(filters)
        if sort is not None:
            updates["sort"] = sort.value
        if icon is not None:
            updates["icon"] = icon.strip() or None
        if is_pinned is not None:
            updates["is_pinned"] = is_pinned
        return self.repo.update_view(view.model_copy(update=updates))

    def delete_view(self, user_id: str, saved_view_id: str) -> bool:
        return self.repo.delete_view(user_id, saved_view_id)


def projection_matches_request(projection: SearchProjection, request: SearchRequest) -> bool:
    if request.item_types and projection.source_item_type not in request.item_types:
        return False
    if request.statuses:
        if not any(projection_matches_status(projection, status_value) for status_value in request.statuses):
            return False
    elif projection.archived and not request.include_archived:
        return False
    if projection.archived and not request.include_archived and "archived" not in request.statuses:
        return False
    if request.date_from is not None and (projection.relevant_date is None or projection.relevant_date < request.date_from):
        return False
    if request.date_to is not None and (projection.relevant_date is None or projection.relevant_date > request.date_to):
        return False
    if request.category and normalize_search_text(projection.category) != normalize_search_text(request.category):
        return False
    if request.owner and normalize_search_text(projection.owner_or_person) != normalize_search_text(request.owner):
        return False
    if request.has_documents is not None and projection.has_documents != request.has_documents:
        return False
    if request.has_linked_items is not None and projection.has_linked_items != request.has_linked_items:
        return False
    return True


def projection_matches_status(projection: SearchProjection, status_value: str) -> bool:
    today = date.today()
    if status_value == "archived":
        return projection.archived
    if status_value == "active":
        return not projection.archived and projection.status not in {"completed", "deleted", "rejected"}
    if status_value == "due_soon":
        return bool(projection.relevant_date is not None and today <= projection.relevant_date <= today + timedelta(days=DUE_SOON_DAYS) and not projection.archived)
    if status_value == "overdue":
        return bool(projection.status == "overdue" or (projection.relevant_date is not None and projection.relevant_date < today and not projection.archived))
    return projection.status == status_value


def projection_score(projection: SearchProjection, query: str, query_tokens: list[str]) -> int:
    if not query_tokens:
        return 0
    normalized_query = normalize_search_text(query)
    if projection.normalized_title == normalized_query:
        return 0
    if normalized_query and projection.normalized_title.startswith(normalized_query):
        return 1
    if all_tokens_match(projection.title_tokens, query_tokens):
        return 2
    if all_tokens_match(projection.metadata_tokens, query_tokens):
        return 3
    if all_tokens_match(projection.custom_field_name_tokens, query_tokens):
        return 4
    if all_tokens_match([*projection.relationship_tokens, *projection.linked_context_tokens], query_tokens):
        return 5
    return 6


def all_tokens_match(candidate_tokens: list[str], query_tokens: list[str]) -> bool:
    return all(any(token.startswith(query_token) for token in candidate_tokens) for query_token in query_tokens)


def projection_sort_key(projection: SearchProjection, score: int, sort: SearchSort):
    title = projection.normalized_title or projection.display_title.casefold()
    updated_ts = projection.updated_at.timestamp()
    created_ts = projection.created_at.timestamp()
    relevant = projection.relevant_date.toordinal() if projection.relevant_date else 99_999_999
    if sort == SearchSort.UPDATED_DESC:
        return (-updated_ts, title, projection.search_item_id)
    if sort == SearchSort.CREATED_DESC:
        return (-created_ts, title, projection.search_item_id)
    if sort == SearchSort.RELEVANT_DATE_ASC:
        return (relevant, title, projection.search_item_id)
    if sort == SearchSort.RELEVANT_DATE_DESC:
        return (-relevant if projection.relevant_date else 99_999_999, title, projection.search_item_id)
    if sort == SearchSort.TITLE_ASC:
        return (title, -updated_ts, projection.search_item_id)
    return (score, -updated_ts, title, projection.search_item_id)


def projection_to_result(projection: SearchProjection, query: str, query_tokens: list[str]) -> SearchResultItem:
    contexts: list[str] = []
    linked_context: list[str] = []
    if query_tokens:
        for token in query_tokens:
            for projection_token, token_contexts in projection.token_contexts.items():
                if not projection_token.startswith(token):
                    continue
                for context in token_contexts:
                    target = linked_context if context.startswith("Linked to ") else contexts
                    if context not in target:
                        target.append(context)
    if query.strip() and not contexts:
        contexts.append("Matched title")
    subtitle = projection.safe_display_metadata.get("subtitle") or projection.safe_display_metadata.get("type")
    return SearchResultItem(
        source_item_id=projection.source_item_id,
        source_item_type=projection.source_item_type,
        title=projection.display_title,
        subtitle=subtitle,
        status=projection.status,
        category=projection.category,
        relevant_date=projection.relevant_date,
        archived=projection.archived,
        match_context=contexts[:3],
        linked_context=linked_context[:2],
        navigation_metadata=projection.navigation_metadata,
        updated_at=projection.updated_at,
    )


def applied_filters(request: SearchRequest) -> dict[str, object]:
    return {
        "q": request.query,
        "itemTypes": [item.value for item in request.item_types],
        "statuses": list(request.statuses),
        "archived": request.include_archived,
        "dateFrom": request.date_from.isoformat() if request.date_from else None,
        "dateTo": request.date_to.isoformat() if request.date_to else None,
        "category": request.category,
        "owner": request.owner,
        "hasDocuments": request.has_documents,
        "hasLinkedItems": request.has_linked_items,
        "sort": request.sort.value,
        "pageSize": request.page_size,
    }


def request_fingerprint(request: SearchRequest) -> str:
    payload = {key: value for key, value in applied_filters(request).items() if key != "pageSize"}
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:24]


def encode_cursor(offset: int, fingerprint: str) -> str:
    payload = json.dumps({"v": 1, "offset": offset, "fingerprint": fingerprint}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str, expected_fingerprint: str) -> int:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8"))
    except Exception as exc:
        raise SearchValidationError("Invalid cursor") from exc
    if payload.get("v") != 1 or payload.get("fingerprint") != expected_fingerprint:
        raise SearchValidationError("Invalid cursor")
    offset = payload.get("offset")
    if not isinstance(offset, int) or offset < 0:
        raise SearchValidationError("Invalid cursor")
    return offset


def is_safe_dynamic_field_value(field) -> bool:
    if field.is_sensitive or field.value is None:
        return False
    if field.field_type in PRIVATE_DYNAMIC_VALUE_TYPES:
        return False
    if field.field_type == DynamicFieldType.SHORT_TEXT and any(character.isdigit() for character in str(field.value)):
        return False
    return True


def is_searchable_attachment(attachment: RecordAttachment) -> bool:
    return attachment.status != AttachmentStatus.DELETED and attachment.deleted_at is None


def compact_metadata(**values: str | None) -> dict[str, str]:
    return {key: value for key, value in values.items() if value}


def first_date(*values: date | None) -> date | None:
    return next((value for value in values if value is not None), None)


def relationship_type_label(value: str) -> str:
    return value.replace("_", " ").strip().title() or "Related"


def opposite_link_endpoint(link, entity_type: LinkedEntityType, entity_id: str) -> tuple[LinkedEntityType | None, str | None]:
    if link.source_type == entity_type and link.source_id == entity_id:
        return link.target_type, link.target_id
    if link.target_type == entity_type and link.target_id == entity_id:
        return link.source_type, link.source_id
    return None, None


def link_involves_type(link, entity_type: LinkedEntityType) -> bool:
    return link.source_type == entity_type or link.target_type == entity_type


def reminder_owner_or_person(reminder: Reminder) -> str | None:
    if reminder.birthday_details is not None:
        return reminder.birthday_details.person_name
    if reminder.renewal_details is not None:
        return reminder.renewal_details.owner_name
    return None


def reminder_safe_metadata(reminder: Reminder) -> list[tuple[str | None, str]]:
    values: list[tuple[str | None, str]] = []
    if reminder.birthday_details is not None:
        values.append((reminder.birthday_details.person_name, "Matched person"))
        values.append((reminder.birthday_details.relationship, "Matched relationship"))
    if reminder.renewal_details is not None:
        values.append((reminder.renewal_details.item_name, "Matched renewal item"))
        values.append((reminder.renewal_details.provider, "Matched provider"))
        values.append((reminder.renewal_details.frequency, "Matched frequency"))
        values.append((reminder.renewal_details.renewal_kind.value, "Matched renewal type"))
    if reminder.maintenance_details is not None:
        values.append((reminder.maintenance_details.item_name, "Matched maintenance item"))
        values.append((reminder.maintenance_details.maintenance_area.value, "Matched maintenance area"))
    return values


def validated_saved_view_filters(filters: dict[str, object]) -> dict[str, object]:
    allowed = {"itemTypes", "statuses", "archived", "dateFrom", "dateTo", "category", "owner", "hasDocuments", "hasLinkedItems"}
    sanitized: dict[str, object] = {}
    for key, value in filters.items():
        if key not in allowed:
            continue
        if isinstance(value, str):
            sanitized[key] = value.strip()[:120]
        elif isinstance(value, bool) or value is None:
            sanitized[key] = value
        elif isinstance(value, list):
            sanitized[key] = [str(item).strip()[:80] for item in value[:12] if str(item).strip()]
    return sanitized


def to_saved_view_response(view: SavedSearchView):
    from app.schemas import SavedSearchViewResponse
    return SavedSearchViewResponse(
        saved_view_id=view.saved_view_id,
        name=view.name,
        query=view.query,
        filters=view.filters,
        sort=SearchSort(view.sort),
        icon=view.icon,
        is_pinned=view.is_pinned,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
