import json
import os
import threading
from pathlib import Path
from typing import Any, Protocol

from app.models import RecordAttachment


def record_attachment_key(record_id: str, attachment_id: str) -> str:
    return f"{record_id}#{attachment_id}"


class RecordAttachmentRepository(Protocol):
    def list_for_record(self, user_id: str, record_id: str) -> list[RecordAttachment]:
        ...

    def list_for_user(self, user_id: str, limit: int | None = None) -> list[RecordAttachment]:
        ...

    def get_attachment(self, user_id: str, record_id: str, attachment_id: str) -> RecordAttachment | None:
        ...

    def get_attachment_by_owner_hash(
        self,
        owner_hash: str,
        record_id: str,
        attachment_id: str,
    ) -> RecordAttachment | None:
        ...

    def create_attachment(self, attachment: RecordAttachment) -> RecordAttachment:
        ...

    def update_attachment(self, attachment: RecordAttachment) -> RecordAttachment:
        ...

    def delete_attachment_metadata(self, user_id: str, record_id: str, attachment_id: str) -> bool:
        ...


class LocalRecordAttachmentRepository:
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

        if not self.file_path.exists():
            self._write_all_unlocked([])

    def list_for_record(self, user_id: str, record_id: str) -> list[RecordAttachment]:
        prefix = f"{record_id}#"
        with self._lock:
            return [
                attachment
                for attachment in self._read_all_unlocked()
                if attachment.user_id == user_id
                and attachment.record_attachment_key.startswith(prefix)
            ]

    def list_for_user(self, user_id: str, limit: int | None = None) -> list[RecordAttachment]:
        with self._lock:
            attachments = [attachment for attachment in self._read_all_unlocked() if attachment.user_id == user_id]
        return attachments[:limit] if limit is not None else attachments

    def get_attachment(self, user_id: str, record_id: str, attachment_id: str) -> RecordAttachment | None:
        key = record_attachment_key(record_id, attachment_id)
        with self._lock:
            return next(
                (
                    attachment
                    for attachment in self._read_all_unlocked()
                    if attachment.user_id == user_id and attachment.record_attachment_key == key
                ),
                None,
            )

    def get_attachment_by_owner_hash(
        self,
        owner_hash: str,
        record_id: str,
        attachment_id: str,
    ) -> RecordAttachment | None:
        key = record_attachment_key(record_id, attachment_id)
        with self._lock:
            return next(
                (
                    attachment
                    for attachment in self._read_all_unlocked()
                    if attachment.owner_hash == owner_hash and attachment.record_attachment_key == key
                ),
                None,
            )

    def create_attachment(self, attachment: RecordAttachment) -> RecordAttachment:
        with self._lock:
            attachments = self._read_all_unlocked()
            attachments.append(attachment)
            self._write_all_unlocked(attachments)
            return attachment

    def update_attachment(self, attachment: RecordAttachment) -> RecordAttachment:
        with self._lock:
            attachments = self._read_all_unlocked()
            for index, existing in enumerate(attachments):
                if (
                    existing.user_id == attachment.user_id
                    and existing.record_attachment_key == attachment.record_attachment_key
                ):
                    attachments[index] = attachment
                    self._write_all_unlocked(attachments)
                    return attachment

            attachments.append(attachment)
            self._write_all_unlocked(attachments)
            return attachment

    def delete_attachment_metadata(self, user_id: str, record_id: str, attachment_id: str) -> bool:
        key = record_attachment_key(record_id, attachment_id)
        with self._lock:
            attachments = self._read_all_unlocked()
            next_attachments = [
                attachment
                for attachment in attachments
                if not (attachment.user_id == user_id and attachment.record_attachment_key == key)
            ]
            if len(next_attachments) == len(attachments):
                return False

            self._write_all_unlocked(next_attachments)
            return True

    def _read_all_unlocked(self) -> list[RecordAttachment]:
        if not self.file_path.exists():
            return []

        raw_data = json.loads(self.file_path.read_text(encoding="utf-8") or "[]")
        return [RecordAttachment.model_validate(item) for item in raw_data]

    def _write_all_unlocked(self, attachments: list[RecordAttachment]) -> None:
        serialized = [attachment.model_dump(mode="json") for attachment in attachments]
        temp_path = self.file_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
        os.replace(temp_path, self.file_path)


class DynamoRecordAttachmentRepository:
    def __init__(self, table_name: str, region_name: str, table: Any | None = None):
        self.table_name = table_name
        self.region_name = region_name
        self.table = table or self._build_table(table_name, region_name)

    def list_for_record(self, user_id: str, record_id: str) -> list[RecordAttachment]:
        items: list[dict[str, Any]] = []
        query_kwargs: dict[str, Any] = {
            "KeyConditionExpression": "user_id = :user_id AND begins_with(record_attachment_key, :prefix)",
            "ExpressionAttributeValues": {":user_id": user_id, ":prefix": f"{record_id}#"},
        }

        while True:
            response = self.table.query(**query_kwargs)
            items.extend(response.get("Items", []))

            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break

            query_kwargs["ExclusiveStartKey"] = last_key

        return [self._from_item(item) for item in items]

    def list_for_user(self, user_id: str, limit: int | None = None) -> list[RecordAttachment]:
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
                break

            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break

            query_kwargs["ExclusiveStartKey"] = last_key

        attachments = [self._from_item(item) for item in items]
        return attachments[:limit] if limit is not None else attachments

    def get_attachment(self, user_id: str, record_id: str, attachment_id: str) -> RecordAttachment | None:
        response = self.table.get_item(
            Key={"user_id": user_id, "record_attachment_key": record_attachment_key(record_id, attachment_id)}
        )
        item = response.get("Item")
        if item is None:
            return None

        return self._from_item(item)

    def get_attachment_by_owner_hash(
        self,
        owner_hash: str,
        record_id: str,
        attachment_id: str,
    ) -> RecordAttachment | None:
        response = self.table.query(
            IndexName="OwnerHashRecordAttachmentIndex",
            KeyConditionExpression="owner_hash = :owner_hash AND record_attachment_key = :record_attachment_key",
            ExpressionAttributeValues={
                ":owner_hash": owner_hash,
                ":record_attachment_key": record_attachment_key(record_id, attachment_id),
            },
        )
        items = response.get("Items", [])
        if not items:
            return None

        return self._from_item(items[0])

    def create_attachment(self, attachment: RecordAttachment) -> RecordAttachment:
        self.table.put_item(Item=self._to_item(attachment))
        return attachment

    def update_attachment(self, attachment: RecordAttachment) -> RecordAttachment:
        self.table.put_item(Item=self._to_item(attachment))
        return attachment

    def delete_attachment_metadata(self, user_id: str, record_id: str, attachment_id: str) -> bool:
        response = self.table.delete_item(
            Key={"user_id": user_id, "record_attachment_key": record_attachment_key(record_id, attachment_id)},
            ReturnValues="ALL_OLD",
        )
        return "Attributes" in response

    def _build_table(self, table_name: str, region_name: str) -> Any:
        import boto3

        return boto3.resource("dynamodb", region_name=region_name).Table(table_name)

    def _to_item(self, attachment: RecordAttachment) -> dict[str, Any]:
        return attachment.model_dump(mode="json")

    def _from_item(self, item: dict[str, Any]) -> RecordAttachment:
        return RecordAttachment.model_validate(item)
