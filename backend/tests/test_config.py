import pytest

from app.config import (
    COGNITO_AUTH_MODE,
    DEFAULT_CORS_ALLOWED_ORIGINS,
    DEFAULT_LOCAL_DEV_USER_ID,
    DEFAULT_PREFERENCES_TABLE_NAME,
    DEFAULT_REMINDERS_TABLE_NAME,
    DYNAMODB_PERSISTENCE,
    LAMBDA_LOCAL_DATA_FILE,
    LAMBDA_LOCAL_PREFERENCES_FILE,
    LOCAL_AUTH_MODE,
    LOCAL_PERSISTENCE,
    load_settings,
)


def test_config_defaults_are_local_safe():
    settings = load_settings({})

    assert settings.app_env == "local"
    assert settings.auth_mode == LOCAL_AUTH_MODE
    assert settings.local_dev_user_id == DEFAULT_LOCAL_DEV_USER_ID
    assert settings.persistence_mode == LOCAL_PERSISTENCE
    assert settings.reminders_table_name == DEFAULT_REMINDERS_TABLE_NAME
    assert settings.preferences_table_name == DEFAULT_PREFERENCES_TABLE_NAME
    assert settings.aws_region == "us-east-1"
    assert settings.local_data_file.endswith("backend\\data\\reminders.json") or settings.local_data_file.endswith(
        "backend/data/reminders.json"
    )
    assert settings.local_preferences_file.endswith(
        "backend\\data\\preferences.json"
    ) or settings.local_preferences_file.endswith("backend/data/preferences.json")
    assert settings.cors_allowed_origins == DEFAULT_CORS_ALLOWED_ORIGINS
    assert "https://lifeledger.jpreinold.com" in settings.cors_allowed_origins
    assert "https://www.lifeledger.jpreinold.com" in settings.cors_allowed_origins


def test_config_reads_environment_values():
    settings = load_settings(
        {
            "APP_ENV": "production",
            "AUTH_MODE": "cognito",
            "LOCAL_DEV_USER_ID": "dev-user",
            "PERSISTENCE_MODE": "dynamodb",
            "REMINDERS_TABLE_NAME": "custom-table",
            "PREFERENCES_TABLE_NAME": "custom-preferences",
            "AWS_REGION": "us-west-2",
            "CORS_ALLOWED_ORIGINS": "https://example.com, http://localhost:5173",
        }
    )

    assert settings.app_env == "production"
    assert settings.auth_mode == COGNITO_AUTH_MODE
    assert settings.local_dev_user_id == "dev-user"
    assert settings.persistence_mode == DYNAMODB_PERSISTENCE
    assert settings.reminders_table_name == "custom-table"
    assert settings.preferences_table_name == "custom-preferences"
    assert settings.aws_region == "us-west-2"
    assert settings.local_data_file.endswith("backend\\data\\reminders.json") or settings.local_data_file.endswith(
        "backend/data/reminders.json"
    )
    assert settings.cors_allowed_origins == ["https://example.com", "http://localhost:5173"]


def test_config_allows_explicit_local_data_file():
    settings = load_settings({"LOCAL_DATA_FILE": "/tmp/custom-reminders.json"})

    assert settings.local_data_file == "/tmp/custom-reminders.json"


def test_config_allows_explicit_local_preferences_file():
    settings = load_settings({"LOCAL_PREFERENCES_FILE": "/tmp/custom-preferences.json"})

    assert settings.local_preferences_file == "/tmp/custom-preferences.json"


def test_sam_local_defaults_to_writable_tmp_data_file():
    settings = load_settings({"AWS_SAM_LOCAL": "true"})

    assert settings.persistence_mode == LOCAL_PERSISTENCE
    assert settings.local_data_file == LAMBDA_LOCAL_DATA_FILE
    assert settings.local_preferences_file == LAMBDA_LOCAL_PREFERENCES_FILE


def test_config_rejects_unknown_persistence_mode():
    with pytest.raises(ValueError):
        load_settings({"PERSISTENCE_MODE": "sqlite"})


def test_config_rejects_unknown_auth_mode():
    with pytest.raises(ValueError):
        load_settings({"AUTH_MODE": "magic-link"})
