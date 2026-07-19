from __future__ import annotations

from datetime import date
import re
import unicodedata

from app.capture_models import ActionProposal, EntityCandidate, ProposalStatus
from app.linked_items_repository import LinkedItemRepository
from app.records_repository import RecordRepository
from app.repository import ReminderRepository
from app.schemas import LinkedEntityType, RecordStatus, RecordType
from app.search_service import SearchQueryService, SearchRequest


class EntityResolutionService:
    def __init__(
        self,
        records: RecordRepository,
        reminders: ReminderRepository,
        relationships: LinkedItemRepository,
        assistant=None,
        search: SearchQueryService | None = None,
    ):
        self.records = records
        self.reminders = reminders
        self.relationships = relationships
        self.assistant = assistant
        self.search = search

    def retrieve(
        self,
        user_id: str,
        text: str,
        *,
        item_types: set[RecordType] | None = None,
        include_responsibilities: bool = True,
        limit: int = 10,
    ) -> list[EntityCandidate]:
        normalized_text = normalize_entity_text(text)
        search_ids = self._search_candidate_ids(user_id, normalized_text)
        candidates: list[EntityCandidate] = []
        active_records = [
            item
            for item in self.records.list_records(user_id, include_archived=False, limit=500)
            if item.status == RecordStatus.ACTIVE and (not item_types or item.record_type in item_types)
        ]
        reminders = self.reminders.list_reminders(user_id, limit=500)
        recent_ids = self._recent_confirmed_ids(user_id)

        for item in active_records:
            aliases = _safe_aliases(item)
            score, reasons = _score(normalized_text, item.title, aliases)
            related = _related_responsibility(user_id, item.id, reminders, self.relationships)
            if related and normalize_entity_text(related.title) in normalized_text:
                score = max(score, 80)
                reasons.append("linked responsibility")
            if item.id in recent_ids:
                score = min(100, score + 8)
                reasons.append("recent confirmed usage")
            if item.id in search_ids:
                score = min(100, score + 5)
                reasons.append("current search match")
            if score == 0 and not _type_context_match(normalized_text, item.record_type, related is not None):
                continue
            candidates.append(
                EntityCandidate(
                    entity_type="item",
                    entity_id=item.id,
                    display_title=item.title,
                    item_type=item.record_type,
                    safe_aliases=aliases,
                    relationship_context=_safe_dynamic_text(item, "relationship_context"),
                    relevant_responsibility_id=related.id if related else None,
                    relevant_responsibility_title=related.title if related else None,
                    relevant_dates=_safe_record_dates(item, related),
                    match_reasons=list(dict.fromkeys(reasons or ["item type context"])),
                    score=max(score, 25),
                )
            )

        if include_responsibilities:
            for reminder in reminders:
                if reminder.archived_at is not None:
                    continue
                score, reasons = _score(normalized_text, reminder.title, [])
                if score == 0:
                    continue
                if reminder.id in recent_ids:
                    score = min(100, score + 8)
                    reasons.append("recent confirmed usage")
                if reminder.id in search_ids:
                    score = min(100, score + 5)
                    reasons.append("current search match")
                candidates.append(
                    EntityCandidate(
                        entity_type="responsibility",
                        entity_id=reminder.id,
                        display_title=reminder.title,
                        relevant_responsibility_id=reminder.id,
                        relevant_responsibility_title=reminder.title,
                        relevant_dates={"due_date": reminder.due_date},
                        match_reasons=reasons,
                        score=score,
                    )
                )

        candidates.sort(key=lambda item: (-item.score, item.display_title.casefold(), item.entity_id))
        return candidates[:limit]

    def _search_candidate_ids(self, user_id: str, text: str) -> set[str]:
        if self.search is None:
            return set()
        identifiers: set[str] = set()
        tokens = [token for token in text.split() if len(token) >= 4][:6]
        for token in tokens:
            try:
                response = self.search.search(user_id, SearchRequest(query=token, page_size=10))
            except Exception:
                continue
            identifiers.update(item.source_item_id for item in response.items if not item.archived)
        return identifiers

    def _recent_confirmed_ids(self, user_id: str) -> set[str]:
        if self.assistant is None:
            return set()
        try:
            values = [
                ActionProposal.model_validate(item)
                for item in self.assistant.list_entity_rows(user_id, "proposal", limit=50)
            ]
        except Exception:
            return set()
        values.sort(key=lambda item: item.updated_at, reverse=True)
        identifiers: set[str] = set()
        for proposal in values:
            if proposal.status not in {ProposalStatus.COMPLETED, ProposalStatus.PARTIALLY_COMPLETED}:
                continue
            for action in proposal.proposed_actions:
                if action.target_item_id:
                    identifiers.add(action.target_item_id)
                if action.target_responsibility_id:
                    identifiers.add(action.target_responsibility_id)
            for result in proposal.action_results:
                if result.resulting_entity_id:
                    identifiers.add(result.resulting_entity_id)
        return identifiers

    @staticmethod
    def strong_matches(candidates: list[EntityCandidate], entity_type: str) -> list[EntityCandidate]:
        relevant = [item for item in candidates if item.entity_type == entity_type]
        if not relevant:
            return []
        top = relevant[0].score
        return [item for item in relevant if item.score >= max(60, top - 5)]


def normalize_entity_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    without_marks = "".join(character for character in normalized if not unicodedata.combining(character))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", without_marks.casefold()).split())


def _score(text: str, title: str, aliases: list[str]) -> tuple[int, list[str]]:
    title_value = normalize_entity_text(title)
    if not title_value:
        return 0, []
    if text == title_value:
        return 100, ["exact normalized title"]
    if _contains_phrase(text, title_value):
        return 95, ["title appears in capture"]
    for alias in aliases:
        alias_value = normalize_entity_text(alias)
        if alias_value and _contains_phrase(text, alias_value):
            return 90, ["safe alias appears in capture"]
    title_tokens = set(title_value.split())
    text_tokens = set(text.split())
    if title_tokens and title_tokens <= text_tokens:
        return 75, ["title tokens match"]
    if title_tokens & text_tokens and any(len(token) >= 4 for token in title_tokens & text_tokens):
        return 40, ["partial title match"]
    return 0, []


def _contains_phrase(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def _safe_aliases(item) -> list[str]:
    raw = _safe_dynamic_text(item, "aliases")
    if not raw:
        return []
    return [part.strip()[:80] for part in re.split(r"[,;\n]", raw) if part.strip()][:10]


def _safe_dynamic_text(item, key: str) -> str | None:
    field = next(
        (field for field in item.dynamic_fields if field.key == key and not field.is_sensitive and field.has_value),
        None,
    )
    return field.value if field and isinstance(field.value, str) else None


def _safe_record_dates(item, reminder) -> dict[str, date]:
    values = {
        "start_date": item.start_date,
        "issue_date": item.issue_date,
        "expiration_date": item.expiration_date,
        "purchase_date": item.purchase_date,
        "renewal_date": item.renewal_date,
        "responsibility_due_date": reminder.due_date if reminder else None,
    }
    for field in item.dynamic_fields:
        if field.is_sensitive or not field.has_value or not isinstance(field.value, str):
            continue
        if field.key in {"birthday", "registration_expiration", "next_vaccination_due_date"}:
            try:
                values[field.key] = date.fromisoformat(field.value)
            except ValueError:
                continue
    return {key: value for key, value in values.items() if value is not None}


def _related_responsibility(user_id: str, item_id: str, reminders, relationships):
    links = relationships.list_links_for_entity(user_id, LinkedEntityType.RECORD, item_id)
    reminder_ids = {
        link.target_id if link.source_type == LinkedEntityType.RECORD else link.source_id
        for link in links
        if link.source_type == LinkedEntityType.REMINDER or link.target_type == LinkedEntityType.REMINDER
    }
    return next((item for item in reminders if item.id in reminder_ids and item.archived_at is None), None)


def _type_context_match(text: str, item_type: RecordType, has_responsibility: bool) -> bool:
    words = {
        RecordType.PERSON: {"friend", "family", "coworker", "neighbor", "birthday", "person"},
        RecordType.PET: {"pet", "vaccination", "rabies", "vet"},
        RecordType.VEHICLE: {"vehicle", "car", "registration", "license plate"},
        RecordType.HOME: {"home", "house", "hvac", "filter"},
        RecordType.APPLIANCE: {"appliance", "hvac", "filter"},
        RecordType.SUBSCRIPTION: {"subscription", "canceled", "cancelled", "renewal"},
        RecordType.PASSPORT: {"passport"},
    }.get(item_type, set())
    return has_responsibility and any(_contains_phrase(text, normalize_entity_text(word)) for word in words)
