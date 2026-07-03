from datetime import date, datetime, timezone
from uuid import uuid4

from app.dynamo_repository import DynamoReminderRepository
from app.models import Reminder


class FakeDynamoTable:
    def __init__(self):
        self.items = {}

    def query(self, ExpressionAttributeValues, **_kwargs):
        user_id = ExpressionAttributeValues[":user_id"]
        return {
            "Items": [
                item
                for item in self.items.values()
                if item["user_id"] == user_id
            ]
        }

    def put_item(self, Item):
        self.items[(Item["user_id"], Item["id"])] = dict(Item)
        return {}

    def get_item(self, Key):
        item = self.items.get((Key["user_id"], Key["id"]))
        if item is None:
            return {}
        return {"Item": item}

    def delete_item(self, Key, ReturnValues=None):
        item = self.items.pop((Key["user_id"], Key["id"]), None)
        if item is None:
            return {}
        return {"Attributes": item}


def test_dynamo_repository_crud_with_fake_table():
    table = FakeDynamoTable()
    repo = DynamoReminderRepository(table_name="test-table", region_name="us-east-1", table=table)
    reminder = build_reminder()

    repo.create_reminder(reminder)
    loaded = repo.get_reminder(reminder.user_id, reminder.id)

    assert loaded is not None
    assert loaded.id == reminder.id
    assert loaded.title == "Dynamo repository check"

    updated = reminder.model_copy(update={"title": "Updated Dynamo reminder"})
    repo.update_reminder(updated)

    reminders = repo.list_reminders(reminder.user_id)
    assert len(reminders) == 1
    assert reminders[0].title == "Updated Dynamo reminder"

    assert repo.get_reminder("other-user", reminder.id) is None
    assert repo.list_reminders("other-user") == []

    assert repo.delete_reminder(reminder.user_id, reminder.id) is True
    assert repo.get_reminder(reminder.user_id, reminder.id) is None
    assert repo.delete_reminder(reminder.user_id, reminder.id) is False


def test_dynamo_repository_module_imports_without_aws_credentials():
    assert DynamoReminderRepository.__name__ == "DynamoReminderRepository"


def build_reminder():
    now = datetime.now(timezone.utc)
    return Reminder(
        id=str(uuid4()),
        user_id="user-a",
        title="Dynamo repository check",
        category="Other",
        due_date=date.today(),
        repeat="None",
        priority="Medium",
        notes=None,
        completed=False,
        created_at=now,
        updated_at=now,
        completed_at=None,
    )
