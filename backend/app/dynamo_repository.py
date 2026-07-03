from typing import Any

from app.models import Reminder


class DynamoReminderRepository:
    def __init__(self, table_name: str, region_name: str, table: Any | None = None):
        self.table_name = table_name
        self.region_name = region_name
        self.table = table or self._build_table(table_name, region_name)

    def list_reminders(self, user_id: str) -> list[Reminder]:
        items: list[dict[str, Any]] = []
        query_kwargs: dict[str, Any] = {
            "KeyConditionExpression": "user_id = :user_id",
            "ExpressionAttributeValues": {":user_id": user_id},
        }

        while True:
            response = self.table.query(**query_kwargs)
            items.extend(response.get("Items", []))

            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break

            query_kwargs["ExclusiveStartKey"] = last_key

        return [self._from_item(item) for item in items]

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
