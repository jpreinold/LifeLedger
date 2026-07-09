from app.config import load_settings
from app.dynamo_repository import DynamoReminderRepository
from app.google_calendar_repository import (
    DynamoGoogleCalendarConnectionRepository,
    DynamoGoogleOAuthStateRepository,
    LocalGoogleCalendarConnectionRepository,
    LocalGoogleOAuthStateRepository,
)
from app.push_repository import DynamoPushSubscriptionRepository, LocalPushSubscriptionRepository
from app.repository import LocalReminderRepository
from app.repository_factory import (
    create_google_calendar_connection_repository,
    create_google_oauth_state_repository,
    create_push_subscription_repository,
    create_repository,
)


class FakeDynamoTable:
    pass


def test_repository_factory_defaults_to_local(tmp_path):
    repo = create_repository(load_settings({}), local_file_path=tmp_path / "reminders.json")

    assert isinstance(repo, LocalReminderRepository)


def test_repository_factory_uses_configured_local_data_file(tmp_path):
    data_file = tmp_path / "configured-reminders.json"
    repo = create_repository(load_settings({"LOCAL_DATA_FILE": str(data_file)}))

    assert isinstance(repo, LocalReminderRepository)
    assert repo.file_path == data_file


def test_repository_factory_selects_dynamodb_without_real_aws_call():
    fake_table = FakeDynamoTable()
    settings = load_settings({"PERSISTENCE_MODE": "dynamodb"})

    repo = create_repository(settings, dynamo_table=fake_table)

    assert isinstance(repo, DynamoReminderRepository)
    assert repo.table is fake_table


def test_push_repository_factory_defaults_to_local(tmp_path):
    repo = create_push_subscription_repository(load_settings({}), local_file_path=tmp_path / "push.json")

    assert isinstance(repo, LocalPushSubscriptionRepository)


def test_push_repository_factory_selects_dynamodb_without_real_aws_call():
    fake_table = FakeDynamoTable()
    settings = load_settings({"PERSISTENCE_MODE": "dynamodb"})

    repo = create_push_subscription_repository(settings, dynamo_table=fake_table)

    assert isinstance(repo, DynamoPushSubscriptionRepository)
    assert repo.table is fake_table

def test_google_calendar_connection_repository_factory_defaults_to_local(tmp_path):
    repo = create_google_calendar_connection_repository(load_settings({}), local_file_path=tmp_path / "connections.json")

    assert isinstance(repo, LocalGoogleCalendarConnectionRepository)


def test_google_oauth_state_repository_factory_defaults_to_local(tmp_path):
    repo = create_google_oauth_state_repository(load_settings({}), local_file_path=tmp_path / "states.json")

    assert isinstance(repo, LocalGoogleOAuthStateRepository)


def test_google_calendar_connection_repository_factory_selects_dynamodb_without_real_aws_call():
    fake_table = FakeDynamoTable()
    settings = load_settings({"PERSISTENCE_MODE": "dynamodb"})

    repo = create_google_calendar_connection_repository(settings, dynamo_table=fake_table)

    assert isinstance(repo, DynamoGoogleCalendarConnectionRepository)
    assert repo.table is fake_table


def test_google_oauth_state_repository_factory_selects_dynamodb_without_real_aws_call():
    fake_table = FakeDynamoTable()
    settings = load_settings({"PERSISTENCE_MODE": "dynamodb"})

    repo = create_google_oauth_state_repository(settings, dynamo_table=fake_table)

    assert isinstance(repo, DynamoGoogleOAuthStateRepository)
    assert repo.table is fake_table
