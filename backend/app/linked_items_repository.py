import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any, Protocol

from app.models import LinkedItem
from app.schemas import LinkedEntityType

SOURCE_LINKS_INDEX = "SourceLinksIndex"
TARGET_LINKS_INDEX = "TargetLinksIndex"
PAIR_MARKER_PREFIX = "PAIR#"
PAIR_MARKER_KIND = "linked_item_pair"


class DuplicateLinkedItemError(Exception):
    pass


def linked_item_lookup_key(entity_type: LinkedEntityType | str, entity_id: str, link_id: str) -> str:
    return f"{linked_entity_type_value(entity_type)}#{entity_id}#{link_id}"


def linked_item_lookup_prefix(entity_type: LinkedEntityType | str, entity_id: str) -> str:
    return f"{linked_entity_type_value(entity_type)}#{entity_id}#"


def linked_entity_type_value(entity_type: LinkedEntityType | str) -> str:
    return entity_type.value if isinstance(entity_type, LinkedEntityType) else entity_type


def linked_item_member_key(entity_type: LinkedEntityType | str, entity_id: str) -> str:
    return f"{linked_entity_type_value(entity_type)}#{entity_id}"


def canonical_pair_key(
    source_type: LinkedEntityType | str,
    source_id: str,
    target_type: LinkedEntityType | str,
    target_id: str,
) -> str:
    first = linked_item_member_key(source_type, source_id)
    second = linked_item_member_key(target_type, target_id)
    left, right = sorted([first, second])
    return f"{left}|{right}"


def canonical_pair_key_for_link(link: LinkedItem) -> str:
    return link.canonical_pair_key or canonical_pair_key(
        link.source_type,
        link.source_id,
        link.target_type,
        link.target_id,
    )


def duplicate_marker_link_id(pair_key: str) -> str:
    digest = hashlib.sha256(pair_key.encode("utf-8")).hexdigest()
    return f"{PAIR_MARKER_PREFIX}{digest}"


def with_canonical_pair_key(link: LinkedItem) -> LinkedItem:
    pair_key = canonical_pair_key_for_link(link)
    if link.canonical_pair_key == pair_key:
        return link
    return link.model_copy(update={"canonical_pair_key": pair_key})


def is_pair_marker(item: dict[str, Any]) -> bool:
    return item.get("entity_kind") == PAIR_MARKER_KIND or str(item.get("link_id", "")).startswith(PAIR_MARKER_PREFIX)


class LinkedItemRepository(Protocol):
    def create_link(self, link: LinkedItem) -> LinkedItem:
        ...

    def get_link(self, user_id: str, link_id: str) -> LinkedItem | None:
        ...

    def list_links_for_entity(
        self,
        user_id: str,
        entity_type: LinkedEntityType | str,
        entity_id: str,
    ) -> list[LinkedItem]:
        ...

    def link_exists(
        self,
        user_id: str,
        source_type: LinkedEntityType | str,
        source_id: str,
        target_type: LinkedEntityType | str,
        target_id: str,
    ) -> bool:
        ...

    def update_link(self, link: LinkedItem) -> LinkedItem | None:
        ...

    def delete_link(self, user_id: str, link_id: str) -> bool:
        ...

    def delete_links_for_entity(
        self,
        user_id: str,
        entity_type: LinkedEntityType | str,
        entity_id: str,
    ) -> int:
        ...

    def list_for_user(self, user_id: str, limit: int | None = 100) -> list[LinkedItem]:
        ...

    def delete_for_user(self, user_id: str, limit: int = 100) -> int:
        ...


class LocalLinkedItemRepository:
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

        if not self.file_path.exists():
            self._write_all_unlocked([])

    def create_link(self, link: LinkedItem) -> LinkedItem:
        link = with_canonical_pair_key(link)
        with self._lock:
            links = self._read_all_unlocked()
            if any(existing.user_id == link.user_id and existing.link_id == link.link_id for existing in links):
                raise DuplicateLinkedItemError()
            if any(
                existing.user_id == link.user_id
                and canonical_pair_key_for_link(existing) == link.canonical_pair_key
                for existing in links
            ):
                raise DuplicateLinkedItemError()
            links.append(link)
            self._write_all_unlocked(links)
            return link

    def list_for_user(self, user_id: str, limit: int | None = 100) -> list[LinkedItem]:
        with self._lock:
            items = [item for item in self._read_all_unlocked() if item.user_id == user_id]
            return items if limit is None else items[:limit]

    def delete_for_user(self, user_id: str, limit: int = 100) -> int:
        with self._lock:
            links = self._read_all_unlocked()
            targets = {item.link_id for item in links if item.user_id == user_id}
            targets = set(list(targets)[:limit])
            self._write_all_unlocked([item for item in links if item.link_id not in targets])
            return len(targets)

    def get_link(self, user_id: str, link_id: str) -> LinkedItem | None:
        with self._lock:
            return next(
                (link for link in self._read_all_unlocked() if link.user_id == user_id and link.link_id == link_id),
                None,
            )

    def list_links_for_entity(
        self,
        user_id: str,
        entity_type: LinkedEntityType | str,
        entity_id: str,
    ) -> list[LinkedItem]:
        source_prefix = linked_item_lookup_prefix(entity_type, entity_id)
        target_prefix = linked_item_lookup_prefix(entity_type, entity_id)
        with self._lock:
            return [
                with_canonical_pair_key(link)
                for link in self._read_all_unlocked()
                if link.user_id == user_id
                and (
                    link.source_link_key.startswith(source_prefix)
                    or link.target_link_key.startswith(target_prefix)
                )
            ]

    def link_exists(
        self,
        user_id: str,
        source_type: LinkedEntityType | str,
        source_id: str,
        target_type: LinkedEntityType | str,
        target_id: str,
    ) -> bool:
        pair_key = canonical_pair_key(source_type, source_id, target_type, target_id)
        with self._lock:
            return any(
                link.user_id == user_id and canonical_pair_key_for_link(link) == pair_key
                for link in self._read_all_unlocked()
            )

    def update_link(self, link: LinkedItem) -> LinkedItem | None:
        link = with_canonical_pair_key(link)
        with self._lock:
            links = self._read_all_unlocked()
            for index, existing in enumerate(links):
                if existing.user_id == link.user_id and existing.link_id == link.link_id:
                    links[index] = link
                    self._write_all_unlocked(links)
                    return link
            return None

    def delete_link(self, user_id: str, link_id: str) -> bool:
        with self._lock:
            links = self._read_all_unlocked()
            next_links = [link for link in links if not (link.user_id == user_id and link.link_id == link_id)]
            if len(next_links) == len(links):
                return False

            self._write_all_unlocked(next_links)
            return True

    def delete_links_for_entity(
        self,
        user_id: str,
        entity_type: LinkedEntityType | str,
        entity_id: str,
    ) -> int:
        source_prefix = linked_item_lookup_prefix(entity_type, entity_id)
        target_prefix = linked_item_lookup_prefix(entity_type, entity_id)
        with self._lock:
            links = self._read_all_unlocked()
            next_links = [
                link
                for link in links
                if not (
                    link.user_id == user_id
                    and (
                        link.source_link_key.startswith(source_prefix)
                        or link.target_link_key.startswith(target_prefix)
                    )
                )
            ]
            deleted_count = len(links) - len(next_links)
            if deleted_count:
                self._write_all_unlocked(next_links)
            return deleted_count

    def _read_all_unlocked(self) -> list[LinkedItem]:
        if not self.file_path.exists():
            return []

        raw_data = json.loads(self.file_path.read_text(encoding="utf-8") or "[]")
        return [with_canonical_pair_key(LinkedItem.model_validate(item)) for item in raw_data]

    def _write_all_unlocked(self, links: list[LinkedItem]) -> None:
        serialized = [with_canonical_pair_key(link).model_dump(mode="json") for link in links]
        temp_path = self.file_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
        os.replace(temp_path, self.file_path)


class DynamoLinkedItemRepository:
    def __init__(self, table_name: str, region_name: str, table: Any | None = None):
        self.table_name = table_name
        self.region_name = region_name
        self.table = table or self._build_table(table_name, region_name)

    def create_link(self, link: LinkedItem) -> LinkedItem:
        link = with_canonical_pair_key(link)
        marker = self._pair_marker_item(link)
        try:
            self.table.put_item(
                Item=marker,
                ConditionExpression="attribute_not_exists(user_id) AND attribute_not_exists(link_id)",
            )
        except Exception as exc:
            if self._is_conditional_check_failed(exc):
                raise DuplicateLinkedItemError() from exc
            raise

        try:
            self.table.put_item(
                Item=self._to_item(link),
                ConditionExpression="attribute_not_exists(user_id) AND attribute_not_exists(link_id)",
            )
        except Exception as exc:
            self.table.delete_item(Key={"user_id": link.user_id, "link_id": marker["link_id"]})
            if self._is_conditional_check_failed(exc):
                raise DuplicateLinkedItemError() from exc
            raise
        return link

    def list_for_user(self, user_id: str, limit: int | None = 100) -> list[LinkedItem]:
        items: list[dict[str, Any]] = []
        query_kwargs: dict[str, Any] = {
            "KeyConditionExpression": "user_id = :user_id",
            "ExpressionAttributeValues": {":user_id": user_id},
        }
        if limit is not None:
            query_kwargs["Limit"] = limit

        while True:
            response = self.table.query(**query_kwargs)
            items.extend(item for item in response.get("Items", []) if not is_pair_marker(item))
            if limit is not None and len(items) >= limit:
                items = items[:limit]
                break
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            query_kwargs["ExclusiveStartKey"] = last_key
            if limit is not None:
                query_kwargs["Limit"] = max(1, limit - len(items))
        return [self._from_item(item) for item in items]

    def delete_for_user(self, user_id: str, limit: int = 100) -> int:
        response = self.table.query(
            KeyConditionExpression="user_id = :user_id",
            ExpressionAttributeValues={":user_id": user_id},
            ProjectionExpression="user_id, link_id",
            Limit=limit,
        )
        for item in response.get("Items", []):
            self.table.delete_item(Key={"user_id": item["user_id"], "link_id": item["link_id"]})
        return len(response.get("Items", []))

    def get_link(self, user_id: str, link_id: str) -> LinkedItem | None:
        response = self.table.get_item(Key={"user_id": user_id, "link_id": link_id})
        item = response.get("Item")
        if item is None or is_pair_marker(item):
            return None

        return self._from_item(item)

    def list_links_for_entity(
        self,
        user_id: str,
        entity_type: LinkedEntityType | str,
        entity_id: str,
    ) -> list[LinkedItem]:
        links_by_id: dict[str, LinkedItem] = {}
        source_prefix = linked_item_lookup_prefix(entity_type, entity_id)
        target_prefix = linked_item_lookup_prefix(entity_type, entity_id)

        for item in self._query_lookup_index(user_id, SOURCE_LINKS_INDEX, "source_link_key", source_prefix):
            if is_pair_marker(item):
                continue
            link = self._from_item(item)
            links_by_id[link.link_id] = link

        for item in self._query_lookup_index(user_id, TARGET_LINKS_INDEX, "target_link_key", target_prefix):
            if is_pair_marker(item):
                continue
            link = self._from_item(item)
            links_by_id[link.link_id] = link

        return list(links_by_id.values())

    def link_exists(
        self,
        user_id: str,
        source_type: LinkedEntityType | str,
        source_id: str,
        target_type: LinkedEntityType | str,
        target_id: str,
    ) -> bool:
        pair_key = canonical_pair_key(source_type, source_id, target_type, target_id)
        marker_id = duplicate_marker_link_id(pair_key)
        response = self.table.get_item(Key={"user_id": user_id, "link_id": marker_id})
        if response.get("Item") is not None:
            return True

        for link in self.list_links_for_entity(user_id, source_type, source_id):
            if canonical_pair_key_for_link(link) == pair_key:
                return True

        return False

    def update_link(self, link: LinkedItem) -> LinkedItem | None:
        link = with_canonical_pair_key(link)
        try:
            self.table.put_item(
                Item=self._to_item(link),
                ConditionExpression="attribute_exists(user_id) AND attribute_exists(link_id)",
            )
        except Exception as exc:
            if self._is_conditional_check_failed(exc):
                return None
            raise
        return link

    def delete_link(self, user_id: str, link_id: str) -> bool:
        response = self.table.delete_item(Key={"user_id": user_id, "link_id": link_id}, ReturnValues="ALL_OLD")
        attributes = response.get("Attributes")
        if not attributes or is_pair_marker(attributes):
            return False

        pair_key = attributes.get("canonical_pair_key") or canonical_pair_key(
            attributes["source_type"],
            attributes["source_id"],
            attributes["target_type"],
            attributes["target_id"],
        )
        self.table.delete_item(Key={"user_id": user_id, "link_id": duplicate_marker_link_id(pair_key)})
        return True

    def delete_links_for_entity(
        self,
        user_id: str,
        entity_type: LinkedEntityType | str,
        entity_id: str,
    ) -> int:
        links = self.list_links_for_entity(user_id, entity_type, entity_id)
        for link in links:
            self.delete_link(user_id, link.link_id)
        return len(links)

    def _query_lookup_index(
        self,
        user_id: str,
        index_name: str,
        lookup_attribute: str,
        lookup_prefix: str,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        query_kwargs: dict[str, Any] = {
            "IndexName": index_name,
            "KeyConditionExpression": f"user_id = :user_id AND begins_with({lookup_attribute}, :lookup_prefix)",
            "ExpressionAttributeValues": {":user_id": user_id, ":lookup_prefix": lookup_prefix},
        }

        while True:
            response = self.table.query(**query_kwargs)
            items.extend(response.get("Items", []))

            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break

            query_kwargs["ExclusiveStartKey"] = last_key

        return items

    def _pair_marker_item(self, link: LinkedItem) -> dict[str, Any]:
        return {
            "user_id": link.user_id,
            "link_id": duplicate_marker_link_id(link.canonical_pair_key),
            "entity_kind": PAIR_MARKER_KIND,
            "canonical_pair_key": link.canonical_pair_key,
            "relationship_link_id": link.link_id,
            "created_at": link.created_at.isoformat(),
        }

    def _build_table(self, table_name: str, region_name: str) -> Any:
        import boto3

        return boto3.resource("dynamodb", region_name=region_name).Table(table_name)

    def _to_item(self, link: LinkedItem) -> dict[str, Any]:
        return with_canonical_pair_key(link).model_dump(mode="json")

    def _from_item(self, item: dict[str, Any]) -> LinkedItem:
        return with_canonical_pair_key(LinkedItem.model_validate(item))

    def _is_conditional_check_failed(self, exc: Exception) -> bool:
        response = getattr(exc, "response", {})
        error = response.get("Error", {}) if isinstance(response, dict) else {}
        return error.get("Code") == "ConditionalCheckFailedException"
