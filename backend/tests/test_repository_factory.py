from app.config import load_settings
from app.attachments_repository import DynamoRecordAttachmentRepository, LocalRecordAttachmentRepository
from app.dynamo_repository import DynamoRecordRepository, DynamoReminderRepository
from app.google_calendar_repository import (
    DynamoGoogleCalendarConnectionRepository,
    DynamoGoogleOAuthStateRepository,
    LocalGoogleCalendarConnectionRepository,
    LocalGoogleOAuthStateRepository,
)
from app.push_repository import DynamoPushSubscriptionRepository, LocalPushSubscriptionRepository
from app.records_repository import LocalRecordRepository
from app.repository import LocalReminderRepository
from app.responsibility_history_repository import DynamoResponsibilityHistoryRepository, LocalResponsibilityHistoryRepository
from app.repository_factory import (
    create_google_calendar_connection_repository,
    create_google_oauth_state_repository,
    create_push_subscription_repository,
    create_record_attachment_repository,
    create_record_repository,
    create_repository,
    create_responsibility_history_repository,
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


def test_responsibility_history_factory_matches_local_and_dynamo_modes(tmp_path):
    local_path = tmp_path / "history.json"
    local_repo = create_responsibility_history_repository(load_settings({}), local_file_path=local_path)
    assert isinstance(local_repo, LocalResponsibilityHistoryRepository)
    assert local_repo.file_path == local_path

    fake_table = FakeDynamoTable()
    fake_client = object()
    dynamo_repo = create_responsibility_history_repository(
        load_settings({"PERSISTENCE_MODE": "dynamodb"}),
        dynamo_table=fake_table,
        dynamo_client=fake_client,
    )
    assert isinstance(dynamo_repo, DynamoResponsibilityHistoryRepository)
    assert dynamo_repo.table is fake_table
    assert dynamo_repo.client is fake_client


def test_record_repository_factory_defaults_to_local(tmp_path):
    repo = create_record_repository(load_settings({}), local_file_path=tmp_path / "records.json")

    assert isinstance(repo, LocalRecordRepository)


def test_record_repository_factory_uses_configured_local_records_file(tmp_path):
    data_file = tmp_path / "configured-records.json"
    repo = create_record_repository(load_settings({"LOCAL_RECORDS_FILE": str(data_file)}))

    assert isinstance(repo, LocalRecordRepository)
    assert repo.file_path == data_file


def test_record_repository_factory_selects_dynamodb_without_real_aws_call():
    fake_table = FakeDynamoTable()
    settings = load_settings({"PERSISTENCE_MODE": "dynamodb"})

    repo = create_record_repository(settings, dynamo_table=fake_table)

    assert isinstance(repo, DynamoRecordRepository)
    assert repo.table is fake_table


def test_record_attachment_repository_factory_defaults_to_local(tmp_path):
    repo = create_record_attachment_repository(load_settings({}), local_file_path=tmp_path / "attachments.json")

    assert isinstance(repo, LocalRecordAttachmentRepository)


def test_record_attachment_repository_factory_uses_configured_local_file(tmp_path):
    data_file = tmp_path / "configured-attachments.json"
    repo = create_record_attachment_repository(load_settings({"LOCAL_RECORD_ATTACHMENTS_FILE": str(data_file)}))

    assert isinstance(repo, LocalRecordAttachmentRepository)
    assert repo.file_path == data_file


def test_record_attachment_repository_factory_selects_dynamodb_without_real_aws_call():
    fake_table = FakeDynamoTable()
    settings = load_settings({"PERSISTENCE_MODE": "dynamodb"})

    repo = create_record_attachment_repository(settings, dynamo_table=fake_table)

    assert isinstance(repo, DynamoRecordAttachmentRepository)
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
