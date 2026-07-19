import base64
import hashlib
import json
import os
import threading
from datetime import timezone
from pathlib import Path
from typing import Any, Protocol

from app.models import Reminder, ResponsibilityEvent
from app.schemas import LifecycleReconciliationStatus


REMINDER_HISTORY_INDEX = "ReminderHistoryIndex"
ITEM_ACTIVITY_INDEX = "ItemActivityIndex"
IDEMPOTENCY_INDEX = "HistoryIdempotencyIndex"


class DuplicateLifecycleOperation(Exception):
    pass


class LifecycleWriteConflict(Exception):
    pass


class ResponsibilityHistoryRepository(Protocol):
    def get_event(self, user_id: str, event_id: str) -> ResponsibilityEvent | None:
        ...

    def get_by_idempotency(self, user_id: str, idempotency_key: str) -> ResponsibilityEvent | None:
        ...

    def list_for_reminder(
        self,
        user_id: str,
        reminder_id: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[ResponsibilityEvent], str | None]:
        ...

    def list_for_item(
        self,
        user_id: str,
        item_id: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[ResponsibilityEvent], str | None]:
        ...

    def append_event(self, event: ResponsibilityEvent) -> ResponsibilityEvent:
        ...

    def commit_reminder_event(
        self,
        reminder_repo: Any,
        previous: Reminder | None,
        updated: Reminder,
        event: ResponsibilityEvent,
    ) -> Reminder:
        ...

    def update_operation_status(
        self,
        event: ResponsibilityEvent,
        *,
        reconciliation_status: LifecycleReconciliationStatus,
        search_sync_status: LifecycleReconciliationStatus,
        document_reference_status: LifecycleReconciliationStatus | None = None,
    ) -> ResponsibilityEvent:
        ...

    def delete_for_reminder(self, user_id: str, reminder_id: str) -> int:
        ...

    def delete_for_item(self, user_id: str, item_id: str) -> int:
        ...

    def list_for_user(self, user_id: str, limit: int | None = 100) -> list[ResponsibilityEvent]:
        ...

    def delete_for_user(self, user_id: str, limit: int = 100) -> int:
        ...


class LocalResponsibilityHistoryRepository:
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if not self.file_path.exists():
            self._write_all_unlocked([])

    def get_event(self, user_id: str, event_id: str) -> ResponsibilityEvent | None:
        with self._lock:
            return next(
                (event for event in self._read_all_unlocked() if event.user_id == user_id and event.event_id == event_id),
                None,
            )

    def list_for_user(self, user_id: str, limit: int | None = 100) -> list[ResponsibilityEvent]:
        with self._lock:
            items = [item for item in self._read_all_unlocked() if item.user_id == user_id]
            return items if limit is None else items[:limit]

    def delete_for_user(self, user_id: str, limit: int = 100) -> int:
        with self._lock:
            events = self._read_all_unlocked()
            targets = {item.event_id for item in events if item.user_id == user_id}
            targets = set(list(targets)[:limit])
            self._write_all_unlocked([item for item in events if item.event_id not in targets])
            return len(targets)

    def get_by_idempotency(self, user_id: str, idempotency_key: str) -> ResponsibilityEvent | None:
        with self._lock:
            return next(
                (
                    event
                    for event in self._read_all_unlocked()
                    if event.user_id == user_id and event.idempotency_key == idempotency_key
                ),
                None,
            )

    def list_for_reminder(
        self,
        user_id: str,
        reminder_id: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[ResponsibilityEvent], str | None]:
        return self._list(
            lambda event: event.user_id == user_id and event.reminder_id == reminder_id,
            limit=limit,
            cursor=cursor,
        )

    def list_for_item(
        self,
        user_id: str,
        item_id: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[ResponsibilityEvent], str | None]:
        return self._list(
            lambda event: event.user_id == user_id and event.item_id == item_id,
            limit=limit,
            cursor=cursor,
        )

    def append_event(self, event: ResponsibilityEvent) -> ResponsibilityEvent:
        with self._lock:
            events = self._read_all_unlocked()
            if any(existing.event_id == event.event_id for existing in events):
                raise DuplicateLifecycleOperation(event.idempotency_key)
            if any(
                existing.user_id == event.user_id and existing.idempotency_key == event.idempotency_key
                for existing in events
            ):
                raise DuplicateLifecycleOperation(event.idempotency_key)
            events.append(event)
            self._write_all_unlocked(events)
            return event

    def commit_reminder_event(
        self,
        reminder_repo: Any,
        previous: Reminder | None,
        updated: Reminder,
        event: ResponsibilityEvent,
    ) -> Reminder:
        with self._lock:
            if self.get_by_idempotency(event.user_id, event.idempotency_key) is not None:
                existing = reminder_repo.get_reminder(event.user_id, event.reminder_id)
                if existing is None:
                    raise LifecycleWriteConflict("The responsibility no longer exists.")
                return existing
            if previous is not None:
                current = reminder_repo.get_reminder(previous.user_id, previous.id)
                if current is None or current.version != previous.version:
                    raise LifecycleWriteConflict("The responsibility changed before this action could be saved.")
            try:
                saved = reminder_repo.create_reminder(updated) if previous is None else reminder_repo.update_reminder(updated)
                self.append_event(event)
                return saved
            except Exception:
                if previous is None:
                    reminder_repo.delete_reminder(updated.user_id, updated.id)
                else:
                    reminder_repo.update_reminder(previous)
                raise

    def update_operation_status(
        self,
        event: ResponsibilityEvent,
        *,
        reconciliation_status: LifecycleReconciliationStatus,
        search_sync_status: LifecycleReconciliationStatus,
        document_reference_status: LifecycleReconciliationStatus | None = None,
    ) -> ResponsibilityEvent:
        with self._lock:
            events = self._read_all_unlocked()
            for index, existing in enumerate(events):
                if existing.user_id == event.user_id and existing.event_id == event.event_id:
                    updated = existing.model_copy(
                        update={
                            "reconciliation_status": reconciliation_status,
                            "search_sync_status": search_sync_status,
                            "document_reference_status": document_reference_status or existing.document_reference_status,
                        }
                    )
                    events[index] = updated
                    self._write_all_unlocked(events)
                    return updated
            raise LifecycleWriteConflict("Lifecycle event no longer exists.")

    def delete_for_reminder(self, user_id: str, reminder_id: str) -> int:
        return self._delete(lambda event: event.user_id == user_id and event.reminder_id == reminder_id)

    def delete_for_item(self, user_id: str, item_id: str) -> int:
        return self._delete(lambda event: event.user_id == user_id and event.item_id == item_id)

    def _list(self, predicate, *, limit: int, cursor: str | None) -> tuple[list[ResponsibilityEvent], str | None]:
        safe_limit = max(1, min(limit, 50))
        marker = decode_cursor(cursor)
        with self._lock:
            events = sorted(
                (event for event in self._read_all_unlocked() if predicate(event)),
                key=event_sort_key,
                reverse=True,
            )
        if marker:
            events = [event for event in events if event_sort_key(event) < marker]
        page = events[:safe_limit]
        next_cursor = encode_cursor(event_sort_key(page[-1])) if len(events) > safe_limit and page else None
        return page, next_cursor

    def _delete(self, predicate) -> int:
        with self._lock:
            events = self._read_all_unlocked()
            remaining = [event for event in events if not predicate(event)]
            deleted = len(events) - len(remaining)
            if deleted:
                self._write_all_unlocked(remaining)
            return deleted

    def _read_all_unlocked(self) -> list[ResponsibilityEvent]:
        if not self.file_path.exists():
            return []
        raw = json.loads(self.file_path.read_text(encoding="utf-8") or "[]")
        return [ResponsibilityEvent.model_validate(item) for item in raw]

    def _write_all_unlocked(self, events: list[ResponsibilityEvent]) -> None:
        serialized = [event.model_dump(mode="json") for event in events]
        temp_path = self.file_path.with_suffix(self.file_path.suffix + ".tmp")
        temp_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
        os.replace(temp_path, self.file_path)


class DynamoResponsibilityHistoryRepository:
    def __init__(
        self,
        table_name: str,
        reminder_table_name: str,
        region_name: str,
        *,
        table: Any | None = None,
        client: Any | None = None,
    ):
        self.table_name = table_name
        self.reminder_table_name = reminder_table_name
        self.region_name = region_name
        self.table = table or self._build_table(table_name, region_name)
        self.client = client or self._build_client(region_name)

    def get_event(self, user_id: str, event_id: str) -> ResponsibilityEvent | None:
        item = self.table.get_item(
            Key={"user_id": user_id, "event_id": event_id},
            ConsistentRead=True,
        ).get("Item")
        return self._from_item(item) if item else None

    def list_for_user(self, user_id: str, limit: int | None = 100) -> list[ResponsibilityEvent]:
        items: list[dict[str, Any]] = []
        query_kwargs: dict[str, Any] = {
            "KeyConditionExpression": "user_id = :user_id",
            "ExpressionAttributeValues": {":user_id": user_id},
        }
        if limit is not None:
            query_kwargs["Limit"] = limit

        while True:
            response = self.table.query(**query_kwargs)
            items.extend(response.get("Items", []))
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
        events = self.list_for_user(user_id, limit=limit)
        for event in events:
            self.table.delete_item(Key={"user_id": user_id, "event_id": event.event_id})
        return len(events)

    def get_by_idempotency(self, user_id: str, idempotency_key: str) -> ResponsibilityEvent | None:
        response = self.table.query(
            IndexName=IDEMPOTENCY_INDEX,
            KeyConditionExpression="idempotency_hash = :value",
            ExpressionAttributeValues={":value": idempotency_hash(user_id, idempotency_key)},
            Limit=1,
        )
        items = response.get("Items", [])
        return self._from_item(items[0]) if items else None

    def list_for_reminder(
        self,
        user_id: str,
        reminder_id: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[ResponsibilityEvent], str | None]:
        return self._query_index(
            REMINDER_HISTORY_INDEX,
            "reminder_partition",
            f"{user_id}#{reminder_id}",
            "event_sort",
            limit,
            cursor,
        )

    def list_for_item(
        self,
        user_id: str,
        item_id: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[ResponsibilityEvent], str | None]:
        return self._query_index(
            ITEM_ACTIVITY_INDEX,
            "item_partition",
            f"{user_id}#{item_id}",
            "event_sort",
            limit,
            cursor,
        )

    def append_event(self, event: ResponsibilityEvent) -> ResponsibilityEvent:
        try:
            self.table.put_item(
                Item=self._to_item(event),
                ConditionExpression="attribute_not_exists(user_id) AND attribute_not_exists(event_id)",
            )
        except Exception as exc:
            if self.get_by_idempotency(event.user_id, event.idempotency_key) is not None:
                raise DuplicateLifecycleOperation(event.idempotency_key) from exc
            raise
        return event

    def commit_reminder_event(
        self,
        reminder_repo: Any,
        previous: Reminder | None,
        updated: Reminder,
        event: ResponsibilityEvent,
    ) -> Reminder:
        from boto3.dynamodb.types import TypeSerializer

        serializer = TypeSerializer()
        reminder_item = {key: serializer.serialize(value) for key, value in updated.model_dump(mode="json").items()}
        event_item = {key: serializer.serialize(value) for key, value in self._to_item(event).items()}
        if previous is None:
            reminder_condition = "attribute_not_exists(user_id) AND attribute_not_exists(id)"
            reminder_names = None
            reminder_values = None
        else:
            reminder_condition = "attribute_exists(user_id) AND (attribute_not_exists(#version) OR #version = :expected)"
            reminder_names = {"#version": "version"}
            reminder_values = {":expected": serializer.serialize(previous.version)}

        reminder_put: dict[str, Any] = {
            "TableName": self.reminder_table_name,
            "Item": reminder_item,
            "ConditionExpression": reminder_condition,
        }
        if reminder_names:
            reminder_put["ExpressionAttributeNames"] = reminder_names
        if reminder_values:
            reminder_put["ExpressionAttributeValues"] = reminder_values

        try:
            self.client.transact_write_items(
                TransactItems=[
                    {"Put": reminder_put},
                    {
                        "Put": {
                            "TableName": self.table_name,
                            "Item": event_item,
                            "ConditionExpression": "attribute_not_exists(user_id) AND attribute_not_exists(event_id)",
                        }
                    },
                ]
            )
        except Exception as exc:
            existing_event = self.get_event(event.user_id, event.event_id)
            if existing_event is not None:
                existing_reminder = reminder_repo.get_reminder(event.user_id, event.reminder_id)
                if existing_reminder is not None:
                    return existing_reminder
            raise LifecycleWriteConflict("The responsibility changed before this action could be saved.") from exc
        return updated

    def update_operation_status(
        self,
        event: ResponsibilityEvent,
        *,
        reconciliation_status: LifecycleReconciliationStatus,
        search_sync_status: LifecycleReconciliationStatus,
        document_reference_status: LifecycleReconciliationStatus | None = None,
    ) -> ResponsibilityEvent:
        values: dict[str, Any] = {
            ":reconciliation": reconciliation_status.value,
            ":search": search_sync_status.value,
        }
        expression = "SET reconciliation_status = :reconciliation, search_sync_status = :search"
        if document_reference_status is not None:
            expression += ", document_reference_status = :document"
            values[":document"] = document_reference_status.value
        self.table.update_item(
            Key={"user_id": event.user_id, "event_id": event.event_id},
            UpdateExpression=expression,
            ExpressionAttributeValues=values,
            ConditionExpression="attribute_exists(user_id) AND attribute_exists(event_id)",
        )
        return event.model_copy(
            update={
                "reconciliation_status": reconciliation_status,
                "search_sync_status": search_sync_status,
                "document_reference_status": document_reference_status or event.document_reference_status,
            }
        )

    def delete_for_reminder(self, user_id: str, reminder_id: str) -> int:
        return self._delete_query(self.list_for_reminder, user_id, reminder_id)

    def delete_for_item(self, user_id: str, item_id: str) -> int:
        return self._delete_query(self.list_for_item, user_id, item_id)

    def _query_index(
        self,
        index_name: str,
        partition_name: str,
        partition_value: str,
        sort_name: str,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[ResponsibilityEvent], str | None]:
        safe_limit = max(1, min(limit, 50))
        marker = decode_cursor(cursor)
        values: dict[str, Any] = {":partition": partition_value}
        names = {"#partition": partition_name}
        condition = "#partition = :partition"
        if marker:
            condition += " AND #sort < :cursor"
            values[":cursor"] = marker
            names["#sort"] = sort_name
        response = self.table.query(
            IndexName=index_name,
            KeyConditionExpression=condition,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ScanIndexForward=False,
            Limit=safe_limit + 1,
        )
        items = response.get("Items", [])
        page_items = items[:safe_limit]
        events = [self._from_item(item) for item in page_items]
        next_cursor = encode_cursor(page_items[-1][sort_name]) if len(items) > safe_limit and page_items else None
        return events, next_cursor

    def _delete_query(self, query, user_id: str, entity_id: str) -> int:
        deleted = 0
        cursor: str | None = None
        with self.table.batch_writer() as batch:
            while True:
                events, cursor = query(user_id, entity_id, limit=50, cursor=cursor)
                for event in events:
                    batch.delete_item(Key={"user_id": user_id, "event_id": event.event_id})
                    deleted += 1
                if not cursor:
                    break
        return deleted

    def _to_item(self, event: ResponsibilityEvent) -> dict[str, Any]:
        item = event.model_dump(mode="json")
        item["reminder_partition"] = f"{event.user_id}#{event.reminder_id}"
        item["event_sort"] = event_sort_key(event)
        item["idempotency_hash"] = idempotency_hash(event.user_id, event.idempotency_key)
        if event.item_id:
            item["item_partition"] = f"{event.user_id}#{event.item_id}"
        return item

    def _from_item(self, item: dict[str, Any]) -> ResponsibilityEvent:
        return ResponsibilityEvent.model_validate(
            {key: value for key, value in item.items() if key not in {"reminder_partition", "event_sort", "idempotency_hash", "item_partition"}}
        )

    @staticmethod
    def _build_table(table_name: str, region_name: str) -> Any:
        import boto3

        return boto3.resource("dynamodb", region_name=region_name).Table(table_name)

    @staticmethod
    def _build_client(region_name: str) -> Any:
        import boto3

        return boto3.client("dynamodb", region_name=region_name)


def event_sort_key(event: ResponsibilityEvent) -> str:
    occurred_at = event.occurred_at
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    occurred_at = occurred_at.astimezone(timezone.utc)
    return f"{occurred_at.isoformat(timespec='microseconds')}#{event.event_id}"


def idempotency_hash(user_id: str, idempotency_key: str) -> str:
    return hashlib.sha256(f"{user_id}\0{idempotency_key}".encode("utf-8")).hexdigest()


def encode_cursor(marker: str) -> str:
    return base64.urlsafe_b64encode(marker.encode("utf-8")).decode("ascii").rstrip("=")


def decode_cursor(cursor: str | None) -> str | None:
    if not cursor:
        return None
    try:
        padding = "=" * (-len(cursor) % 4)
        return base64.urlsafe_b64decode(cursor + padding).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Invalid history cursor") from exc
