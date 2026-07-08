from datetime import datetime, timezone

from app.config import load_settings
from app.preferences import default_digest_preferences
from app.preferences_repository import DynamoPreferencesRepository, LocalPreferencesRepository
from app.repository_factory import create_preferences_repository


class FakeDynamoTable:
    def __init__(self):
        self.items = {}

    def get_item(self, Key):
        item = self.items.get(Key["user_id"])
        return {"Item": item} if item else {}

    def put_item(self, Item):
        self.items[Item["user_id"]] = Item
        return {}


def test_default_digest_preferences_are_push_ready_defaults():
    preferences = default_digest_preferences("user-1", datetime(2026, 7, 6, tzinfo=timezone.utc))

    assert preferences.user_id == "user-1"
    assert preferences.digest_enabled is True
    assert preferences.digest_time == "09:00"
    assert preferences.digest_lookahead_days == 30
    assert preferences.timezone is None
    assert preferences.digest_last_seen_at is None
    assert preferences.digest_last_pushed_at is None


def test_local_preferences_repository_round_trips_by_user(tmp_path):
    repo = LocalPreferencesRepository(tmp_path / "preferences.json")
    preferences = default_digest_preferences("user-1").model_copy(update={"digest_enabled": False})

    saved = repo.save_preferences(preferences)

    assert saved.digest_enabled is False
    assert repo.get_preferences("user-1") == preferences
    assert repo.get_preferences("user-2") is None


def test_dynamo_preferences_repository_round_trips_by_user():
    table = FakeDynamoTable()
    repo = DynamoPreferencesRepository("preferences", "us-east-1", table=table)
    preferences = default_digest_preferences("user-1").model_copy(update={"timezone": "America/New_York"})

    repo.save_preferences(preferences)

    assert repo.get_preferences("user-1") == preferences
    assert repo.get_preferences("user-2") is None


def test_preferences_repository_factory_defaults_to_local(tmp_path):
    repo = create_preferences_repository(load_settings({}), local_file_path=tmp_path / "preferences.json")

    assert isinstance(repo, LocalPreferencesRepository)


def test_preferences_repository_factory_selects_dynamodb_without_real_aws_call():
    fake_table = FakeDynamoTable()
    settings = load_settings({"PERSISTENCE_MODE": "dynamodb"})

    repo = create_preferences_repository(settings, dynamo_table=fake_table)

    assert isinstance(repo, DynamoPreferencesRepository)
    assert repo.table is fake_table