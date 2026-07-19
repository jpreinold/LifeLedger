from typing import Any

from app.models import Record, Reminder
from app.schemas import RecordStatus


class DynamoReminderRepository:
    def __init__(self, table_name: str, region_name: str, table: Any | None = None):
        self.table_name = table_name
        self.region_name = region_name
        self.table = table or self._build_table(table_name, region_name)

    def list_reminders(self, user_id: str, limit: int | None = None) -> list[Reminder]:
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

        reminders = [self._from_item(item) for item in items]
        return reminders[:limit] if limit is not None else reminders

    def list_reminders_page(
        self, user_id: str, *, limit: int, cursor: str | None = None
    ) -> tuple[list[Reminder], str | None]:
        query_kwargs: dict[str, Any] = {
            "KeyConditionExpression": "user_id = :user_id",
            "ExpressionAttributeValues": {":user_id": user_id},
            "Limit": limit,
        }
        if cursor:
            query_kwargs["ExclusiveStartKey"] = {"user_id": user_id, "id": cursor}
        response = self.table.query(**query_kwargs)
        reminders = [self._from_item(item) for item in response.get("Items", [])]
        last_key = response.get("LastEvaluatedKey")
        return reminders, last_key.get("id") if last_key else None

    def create_reminder(self, reminder: Reminder) -> Reminder:
        self.table.put_item(Item=self._to_item(reminder))
        return reminder

    def get_reminder(self, user_id: str, reminder_id: str) -> Reminder | None:
        response = self.table.get_item(Key={"user_id": user_id, "id": reminder_id})
        item = response.get("Item")
        if item is None:
            return None

        return self._from_item(item)

    def update_reminder(self, reminder: Reminder) -> Reminder:
        self.table.put_item(Item=self._to_item(reminder))
        return reminder

    def delete_reminder(self, user_id: str, reminder_id: str) -> bool:
        response = self.table.delete_item(Key={"user_id": user_id, "id": reminder_id}, ReturnValues="ALL_OLD")
        return "Attributes" in response

    def _build_table(self, table_name: str, region_name: str) -> Any:
        import boto3

        return boto3.resource("dynamodb", region_name=region_name).Table(table_name)

    def _to_item(self, reminder: Reminder) -> dict[str, Any]:
        return reminder.model_dump(mode="json")

    def _from_item(self, item: dict[str, Any]) -> Reminder:
        return Reminder.model_validate(item)


class DynamoRecordRepository:
    def __init__(self, table_name: str, region_name: str, table: Any | None = None):
        self.table_name = table_name
        self.region_name = region_name
        self.table = table or self._build_table(table_name, region_name)

    def list_records(
        self, user_id: str, include_archived: bool = False, limit: int | None = None
    ) -> list[Record]:
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

        records = [self._from_item(item) for item in items]
        if include_archived:
            return records[:limit] if limit is not None else records

        active = [record for record in records if record.status != RecordStatus.ARCHIVED]
        return active[:limit] if limit is not None else active

    def get_record(self, user_id: str, record_id: str) -> Record | None:
        response = self.table.get_item(Key={"user_id": user_id, "id": record_id})
        item = response.get("Item")
        if item is None:
            return None

        return self._from_item(item)

    def create_record(self, record: Record) -> Record:
        self.table.put_item(Item=self._to_item(record))
        return record

    def update_record(self, record: Record) -> Record:
        self.table.put_item(Item=self._to_item(record))
        return record

    def delete_record(self, user_id: str, record_id: str) -> bool:
        response = self.table.delete_item(Key={"user_id": user_id, "id": record_id}, ReturnValues="ALL_OLD")
        return "Attributes" in response

    def archive_record(self, user_id: str, record_id: str) -> Record | None:
        return self._set_record_status(user_id, record_id, RecordStatus.ARCHIVED)

    def unarchive_record(self, user_id: str, record_id: str) -> Record | None:
        return self._set_record_status(user_id, record_id, RecordStatus.ACTIVE)

    def _set_record_status(self, user_id: str, record_id: str, status: RecordStatus) -> Record | None:
        record = self.get_record(user_id, record_id)
        if record is None:
            return None

        from datetime import datetime, timezone

        updated = record.model_copy(update={"status": status, "updated_at": datetime.now(timezone.utc)})
        self.update_record(updated)
        return updated

    def _build_table(self, table_name: str, region_name: str) -> Any:
        import boto3

        return boto3.resource("dynamodb", region_name=region_name).Table(table_name)

    def _to_item(self, record: Record) -> dict[str, Any]:
        return record.model_dump(mode="json")

    def _from_item(self, item: dict[str, Any]) -> Record:
        return Record.model_validate(item)
