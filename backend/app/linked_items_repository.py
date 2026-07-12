import json
import os
import threading
from pathlib import Path
from typing import Any, Protocol

from app.models import LinkedItem
from app.schemas import LinkedEntityType

SOURCE_LINKS_INDEX = "SourceLinksIndex"
TARGET_LINKS_INDEX = "TargetLinksIndex"


def linked_item_lookup_key(entity_type: LinkedEntityType | str, entity_id: str, link_id: str) -> str:
    return f"{linked_entity_type_value(entity_type)}#{entity_id}#{link_id}"


def linked_item_lookup_prefix(entity_type: LinkedEntityType | str, entity_id: str) -> str:
    return f"{linked_entity_type_value(entity_type)}#{entity_id}#"


def linked_entity_type_value(entity_type: LinkedEntityType | str) -> str:
    return entity_type.value if isinstance(entity_type, LinkedEntityType) else entity_type


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

    def delete_link(self, user_id: str, link_id: str) -> bool:
        ...

    def delete_links_for_entity(
        self,
        user_id: str,
        entity_type: LinkedEntityType | str,
        entity_id: str,
    ) -> int:
        ...


class LocalLinkedItemRepository:
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

        if not self.file_path.exists():
            self._write_all_unlocked([])

    def create_link(self, link: LinkedItem) -> LinkedItem:
        with self._lock:
            links = self._read_all_unlocked()
            links.append(link)
            self._write_all_unlocked(links)
            return link

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
                link
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
        with self._lock:
            return any(
                link.user_id == user_id
                and link.source_type == source_type
                and link.source_id == source_id
                and link.target_type == target_type
                and link.target_id == target_id
                for link in self._read_all_unlocked()
            )

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
        return [LinkedItem.model_validate(item) for item in raw_data]

    def _write_all_unlocked(self, links: list[LinkedItem]) -> None:
        serialized = [link.model_dump(mode="json") for link in links]
        temp_path = self.file_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
        os.replace(temp_path, self.file_path)


class DynamoLinkedItemRepository:
    def __init__(self, table_name: str, region_name: str, table: Any | None = None):
        self.table_name = table_name
        self.region_name = region_name
        self.table = table or self._build_table(table_name, region_name)

    def create_link(self, link: LinkedItem) -> LinkedItem:
        self.table.put_item(Item=self._to_item(link))
        return link

    def get_link(self, user_id: str, link_id: str) -> LinkedItem | None:
        response = self.table.get_item(Key={"user_id": user_id, "link_id": link_id})
        item = response.get("Item")
        if item is None:
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
            link = self._from_item(item)
            links_by_id[link.link_id] = link

        for item in self._query_lookup_index(user_id, TARGET_LINKS_INDEX, "target_link_key", target_prefix):
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
        for link in self.list_links_for_entity(user_id, source_type, source_id):
            if (
                link.source_type == source_type
                and link.source_id == source_id
                and link.target_type == target_type
                and link.target_id == target_id
            ):
                return True

        return False

    def delete_link(self, user_id: str, link_id: str) -> bool:
        response = self.table.delete_item(Key={"user_id": user_id, "link_id": link_id}, ReturnValues="ALL_OLD")
        return "Attributes" in response

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

    def _build_table(self, table_name: str, region_name: str) -> Any:
        import boto3

        return boto3.resource("dynamodb", region_name=region_name).Table(table_name)

    def _to_item(self, link: LinkedItem) -> dict[str, Any]:
        return link.model_dump(mode="json")

    def _from_item(self, item: dict[str, Any]) -> LinkedItem:
        return LinkedItem.model_validate(item)
