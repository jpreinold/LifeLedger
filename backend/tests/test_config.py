import pytest

from app.config import DYNAMODB_PERSISTENCE, LAMBDA_LOCAL_DATA_FILE, LOCAL_PERSISTENCE, load_settings


def test_config_defaults_are_local_safe():
    settings = load_settings({})

    assert settings.app_env == "local"
    assert settings.persistence_mode == LOCAL_PERSISTENCE
    assert settings.reminders_table_name == "lifeledger-reminders"
    assert settings.aws_region == "us-east-1"
    assert settings.local_data_file.endswith("backend\\data\\reminders.json") or settings.local_data_file.endswith(
        "backend/data/reminders.json"
    )


def test_config_reads_environment_values():
    settings = load_settings(
        {
            "APP_ENV": "production",
            "PERSISTENCE_MODE": "dynamodb",
            "REMINDERS_TABLE_NAME": "custom-table",
            "AWS_REGION": "us-west-2",
        }
    )

    assert settings.app_env == "production"
    assert settings.persistence_mode == DYNAMODB_PERSISTENCE
    assert settings.reminders_table_name == "custom-table"
    assert settings.aws_region == "us-west-2"
    assert settings.local_data_file.endswith("backend\\data\\reminders.json") or settings.local_data_file.endswith(
        "backend/data/reminders.json"
    )


def test_config_allows_explicit_local_data_file():
    settings = load_settings({"LOCAL_DATA_FILE": "/tmp/custom-reminders.json"})

    assert settings.local_data_file == "/tmp/custom-reminders.json"


def test_sam_local_defaults_to_writable_tmp_data_file():
    settings = load_settings({"AWS_SAM_LOCAL": "true"})

    assert settings.persistence_mode == LOCAL_PERSISTENCE
    assert settings.local_data_file == LAMBDA_LOCAL_DATA_FILE


def test_config_rejects_unknown_persistence_mode():
    with pytest.raises(ValueError):
        load_settings({"PERSISTENCE_MODE": "sqlite"})
