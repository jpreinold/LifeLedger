import pytest

from app.config import (
    COGNITO_AUTH_MODE,
    DEFAULT_CORS_ALLOWED_ORIGINS,
    DEFAULT_GOOGLE_CALENDAR_CONNECTIONS_TABLE_NAME,
    DEFAULT_GOOGLE_CALENDAR_SCOPES,
    DEFAULT_GOOGLE_OAUTH_STATES_TABLE_NAME,
    DEFAULT_LOCAL_DEV_USER_ID,
    DEFAULT_PREFERENCES_TABLE_NAME,
    DEFAULT_PUSH_SUBSCRIPTIONS_TABLE_NAME,
    DEFAULT_RECORDS_TABLE_NAME,
    DEFAULT_REMINDERS_TABLE_NAME,
    DYNAMODB_PERSISTENCE,
    LAMBDA_LOCAL_DATA_FILE,
    LAMBDA_LOCAL_RECORDS_FILE,
    LAMBDA_LOCAL_PREFERENCES_FILE,
    LAMBDA_LOCAL_GOOGLE_CALENDAR_CONNECTIONS_FILE,
    LAMBDA_LOCAL_GOOGLE_OAUTH_STATES_FILE,
    LAMBDA_LOCAL_PUSH_SUBSCRIPTIONS_FILE,
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
    assert settings.records_table_name == DEFAULT_RECORDS_TABLE_NAME
    assert settings.preferences_table_name == DEFAULT_PREFERENCES_TABLE_NAME
    assert settings.push_subscriptions_table_name == DEFAULT_PUSH_SUBSCRIPTIONS_TABLE_NAME
    assert settings.google_calendar_connections_table_name == DEFAULT_GOOGLE_CALENDAR_CONNECTIONS_TABLE_NAME
    assert settings.google_oauth_states_table_name == DEFAULT_GOOGLE_OAUTH_STATES_TABLE_NAME
    assert settings.aws_region == "us-east-1"
    assert settings.local_data_file.endswith("backend\\data\\reminders.json") or settings.local_data_file.endswith(
        "backend/data/reminders.json"
    )
    assert settings.local_records_file.endswith("backend\\data\\records.json") or settings.local_records_file.endswith(
        "backend/data/records.json"
    )
    assert settings.local_preferences_file.endswith(
        "backend\\data\\preferences.json"
    ) or settings.local_preferences_file.endswith("backend/data/preferences.json")
    assert settings.local_push_subscriptions_file.endswith(
        "backend\\data\\push-subscriptions.json"
    ) or settings.local_push_subscriptions_file.endswith("backend/data/push-subscriptions.json")
    assert settings.local_google_calendar_connections_file.endswith(
        "backend\\data\\google-calendar-connections.json"
    ) or settings.local_google_calendar_connections_file.endswith("backend/data/google-calendar-connections.json")
    assert settings.local_google_oauth_states_file.endswith(
        "backend\\data\\google-oauth-states.json"
    ) or settings.local_google_oauth_states_file.endswith("backend/data/google-oauth-states.json")
    assert settings.push_notifications_configured is False
    assert settings.google_calendar_configured is False
    assert settings.google_calendar_scopes == DEFAULT_GOOGLE_CALENDAR_SCOPES
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
            "RECORDS_TABLE_NAME": "custom-records",
            "PREFERENCES_TABLE_NAME": "custom-preferences",
            "PUSH_SUBSCRIPTIONS_TABLE_NAME": "custom-push",
            "GOOGLE_CALENDAR_CONNECTIONS_TABLE_NAME": "custom-google-connections",
            "GOOGLE_OAUTH_STATES_TABLE_NAME": "custom-google-states",
            "VAPID_PUBLIC_KEY": "public",
            "VAPID_PRIVATE_KEY": "private",
            "VAPID_SUBJECT": "mailto:test@example.com",
            "AWS_REGION": "us-west-2",
            "GOOGLE_CLIENT_ID": "google-client-id",
            "GOOGLE_CLIENT_SECRET": "google-client-secret",
            "GOOGLE_OAUTH_REDIRECT_URI": "https://example.com/oauth/google-calendar",
            "GOOGLE_CALENDAR_SCOPES": "https://www.googleapis.com/auth/calendar.events",
            "CORS_ALLOWED_ORIGINS": "https://example.com, http://localhost:5173",
        }
    )

    assert settings.app_env == "production"
    assert settings.auth_mode == COGNITO_AUTH_MODE
    assert settings.local_dev_user_id == "dev-user"
    assert settings.persistence_mode == DYNAMODB_PERSISTENCE
    assert settings.reminders_table_name == "custom-table"
    assert settings.records_table_name == "custom-records"
    assert settings.preferences_table_name == "custom-preferences"
    assert settings.push_subscriptions_table_name == "custom-push"
    assert settings.google_calendar_connections_table_name == "custom-google-connections"
    assert settings.google_oauth_states_table_name == "custom-google-states"
    assert settings.push_notifications_configured is True
    assert settings.google_calendar_configured is True
    assert settings.aws_region == "us-west-2"
    assert settings.local_data_file.endswith("backend\\data\\reminders.json") or settings.local_data_file.endswith(
        "backend/data/reminders.json"
    )
    assert settings.cors_allowed_origins == ["https://example.com", "http://localhost:5173"]


def test_config_allows_explicit_local_data_file():
    settings = load_settings({"LOCAL_DATA_FILE": "/tmp/custom-reminders.json"})

    assert settings.local_data_file == "/tmp/custom-reminders.json"


def test_config_allows_explicit_local_records_file():
    settings = load_settings({"LOCAL_RECORDS_FILE": "/tmp/custom-records.json"})

    assert settings.local_records_file == "/tmp/custom-records.json"


def test_config_allows_explicit_local_preferences_file():
    settings = load_settings({"LOCAL_PREFERENCES_FILE": "/tmp/custom-preferences.json"})

    assert settings.local_preferences_file == "/tmp/custom-preferences.json"


def test_config_allows_explicit_local_push_subscriptions_file():
    settings = load_settings({"LOCAL_PUSH_SUBSCRIPTIONS_FILE": "/tmp/custom-push.json"})

    assert settings.local_push_subscriptions_file == "/tmp/custom-push.json"


def test_config_allows_explicit_local_google_calendar_files():
    settings = load_settings(
        {
            "LOCAL_GOOGLE_CALENDAR_CONNECTIONS_FILE": "/tmp/custom-google-connections.json",
            "LOCAL_GOOGLE_OAUTH_STATES_FILE": "/tmp/custom-google-states.json",
        }
    )

    assert settings.local_google_calendar_connections_file == "/tmp/custom-google-connections.json"
    assert settings.local_google_oauth_states_file == "/tmp/custom-google-states.json"


def test_sam_local_defaults_to_writable_tmp_data_file():
    settings = load_settings({"AWS_SAM_LOCAL": "true"})

    assert settings.persistence_mode == LOCAL_PERSISTENCE
    assert settings.local_data_file == LAMBDA_LOCAL_DATA_FILE
    assert settings.local_records_file == LAMBDA_LOCAL_RECORDS_FILE
    assert settings.local_preferences_file == LAMBDA_LOCAL_PREFERENCES_FILE
    assert settings.local_push_subscriptions_file == LAMBDA_LOCAL_PUSH_SUBSCRIPTIONS_FILE
    assert settings.local_google_calendar_connections_file == LAMBDA_LOCAL_GOOGLE_CALENDAR_CONNECTIONS_FILE
    assert settings.local_google_oauth_states_file == LAMBDA_LOCAL_GOOGLE_OAUTH_STATES_FILE


def test_config_rejects_unknown_persistence_mode():
    with pytest.raises(ValueError):
        load_settings({"PERSISTENCE_MODE": "sqlite"})


def test_config_rejects_unknown_auth_mode():
    with pytest.raises(ValueError):
        load_settings({"AUTH_MODE": "magic-link"})
