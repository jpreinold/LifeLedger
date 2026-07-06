from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from app.dynamo_repository import DynamoReminderRepository
from app.models import Reminder
from app.schemas import BirthdayDetails, MaintenanceDetails, ReminderCategory, ReminderType, RenewalDetails, RepeatOption


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
    assert loaded.reminder_lead_value == 1
    assert loaded.reminder_lead_unit == "weeks"
    assert loaded.reminder_time == "09:00"

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


def test_dynamo_repository_loads_legacy_items_without_timing_fields():
    table = FakeDynamoTable()
    repo = DynamoReminderRepository(table_name="test-table", region_name="us-east-1", table=table)
    now = datetime.now(timezone.utc).isoformat()
    table.items[("user-a", "legacy-reminder")] = {
        "id": "legacy-reminder",
        "user_id": "user-a",
        "title": "Legacy Dynamo reminder",
        "category": "Other",
        "due_date": date.today().isoformat(),
        "repeat": "None",
        "priority": "Medium",
        "notes": None,
        "completed": False,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }

    loaded = repo.get_reminder("user-a", "legacy-reminder")

    assert loaded is not None
    assert loaded.reminder_lead_value is None
    assert loaded.reminder_lead_unit is None
    assert loaded.reminder_time is None
    assert loaded.reminder_type == ReminderType.GENERIC
    assert loaded.birthday_details is None
    assert loaded.maintenance_details is None


def test_dynamo_repository_preserves_birthday_fields():
    table = FakeDynamoTable()
    repo = DynamoReminderRepository(table_name="test-table", region_name="us-east-1", table=table)
    birthday = date.today()
    reminder = build_reminder().model_copy(
        update={
            "title": "Jasmine's birthday",
            "category": ReminderCategory.FAMILY,
            "due_date": birthday,
            "repeat": RepeatOption.YEARLY,
            "reminder_type": ReminderType.BIRTHDAY,
            "birthday_details": BirthdayDetails(
                person_name="Jasmine",
                birth_month=birthday.month,
                birth_day=birthday.day,
                birth_year=birthday.year - 31,
                age_turning_next_birthday=31,
            ),
        }
    )

    repo.create_reminder(reminder)
    loaded = repo.get_reminder(reminder.user_id, reminder.id)

    assert loaded is not None
    assert loaded.reminder_type == ReminderType.BIRTHDAY
    assert loaded.birthday_details is not None
    assert loaded.birthday_details.person_name == "Jasmine"
    assert loaded.birthday_details.birth_year == birthday.year - 31



def test_dynamo_repository_preserves_renewal_fields():
    table = FakeDynamoTable()
    repo = DynamoReminderRepository(table_name="test-table", region_name="us-east-1", table=table)
    expiration_date = date.today()
    reminder = build_reminder().model_copy(
        update={
            "title": "Passport expiration",
            "category": ReminderCategory.OTHER,
            "due_date": expiration_date,
            "repeat": RepeatOption.YEARLY,
            "reminder_type": ReminderType.RENEWAL,
            "renewal_details": RenewalDetails(
                item_name="Passport",
                renewal_kind="expiration",
                expiration_date=expiration_date,
                review_lead_days=90,
            ),
        }
    )

    repo.create_reminder(reminder)
    loaded = repo.get_reminder(reminder.user_id, reminder.id)

    assert loaded is not None
    assert loaded.reminder_type == ReminderType.RENEWAL
    assert loaded.renewal_details is not None
    assert loaded.renewal_details.item_name == "Passport"
    assert loaded.renewal_details.expiration_date == expiration_date

def test_dynamo_repository_preserves_maintenance_fields():
    table = FakeDynamoTable()
    repo = DynamoReminderRepository(table_name="test-table", region_name="us-east-1", table=table)
    next_due_date = date.today()
    reminder = build_reminder().model_copy(
        update={
            "title": "Change HVAC filter",
            "category": ReminderCategory.HOME,
            "due_date": next_due_date,
            "repeat": RepeatOption.QUARTERLY,
            "reminder_type": ReminderType.MAINTENANCE,
            "maintenance_details": MaintenanceDetails(
                item_name="Change HVAC filter",
                maintenance_area="home",
                last_completed_date=date.today(),
                interval_value=3,
                interval_unit="months",
                next_due_date=next_due_date,
            ),
        }
    )

    repo.create_reminder(reminder)
    loaded = repo.get_reminder(reminder.user_id, reminder.id)

    assert loaded is not None
    assert loaded.reminder_type == ReminderType.MAINTENANCE
    assert loaded.maintenance_details is not None
    assert loaded.maintenance_details.item_name == "Change HVAC filter"
    assert loaded.maintenance_details.next_due_date == next_due_date


def test_dynamo_repository_preserves_alert_state():
    table = FakeDynamoTable()
    repo = DynamoReminderRepository(table_name="test-table", region_name="us-east-1", table=table)
    alert_time = datetime.now(timezone.utc) + timedelta(days=1)
    reminder = build_reminder().model_copy(
        update={
            "alert_dismissed_until": alert_time,
            "alert_last_action_at": alert_time,
            "alert_snoozed_until": alert_time,
        }
    )

    repo.create_reminder(reminder)
    loaded = repo.get_reminder(reminder.user_id, reminder.id)

    assert loaded is not None
    assert loaded.alert_dismissed_until == alert_time
    assert loaded.alert_last_action_at == alert_time
    assert loaded.alert_snoozed_until == alert_time
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
        reminder_lead_value=1,
        reminder_lead_unit="weeks",
        reminder_time="09:00",
        completed=False,
        created_at=now,
        updated_at=now,
        completed_at=None,
    )
