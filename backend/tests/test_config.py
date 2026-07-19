import pytest

from app.config import (
    COGNITO_AUTH_MODE,
    DEFAULT_CORS_ALLOWED_ORIGINS,
    DEFAULT_GOOGLE_CALENDAR_CONNECTIONS_TABLE_NAME,
    DEFAULT_GOOGLE_CALENDAR_SCOPES,
    DEFAULT_GOOGLE_OAUTH_STATES_TABLE_NAME,
    DEFAULT_LINKED_ITEMS_TABLE_NAME,
    DEFAULT_LOCAL_DEV_USER_ID,
    DEFAULT_PREFERENCES_TABLE_NAME,
    DEFAULT_PUSH_SUBSCRIPTIONS_TABLE_NAME,
    DEFAULT_RECORD_ATTACHMENTS_TABLE_NAME,
    DEFAULT_RECORDS_TABLE_NAME,
    DEFAULT_RESPONSIBILITY_HISTORY_TABLE_NAME,
    DEFAULT_REMINDERS_TABLE_NAME,
    DOCUMENT_STORAGE_DISABLED,
    DOCUMENT_STORAGE_S3,
    DYNAMODB_PERSISTENCE,
    LAMBDA_LOCAL_DATA_FILE,
    LAMBDA_LOCAL_LINKED_ITEMS_FILE,
    LAMBDA_LOCAL_RECORD_ATTACHMENTS_FILE,
    LAMBDA_LOCAL_RECORDS_FILE,
    LAMBDA_LOCAL_PREFERENCES_FILE,
    LAMBDA_LOCAL_GOOGLE_CALENDAR_CONNECTIONS_FILE,
    LAMBDA_LOCAL_GOOGLE_OAUTH_STATES_FILE,
    LAMBDA_LOCAL_PUSH_SUBSCRIPTIONS_FILE,
    LOCAL_AUTH_MODE,
    LOCAL_PERSISTENCE,
    RECORD_ENCRYPTION_DISABLED,
    RECORD_ENCRYPTION_KMS,
    RECORD_ENCRYPTION_LOCAL,
    load_settings,
)

def secure_production_env() -> dict[str, str]:
    return {
        "APP_ENV": "production",
        "AUTH_MODE": "cognito",
        "PERSISTENCE_MODE": "dynamodb",
        "RECORD_ENCRYPTION_MODE": "kms",
        "DATA_ENCRYPTION_KMS_KEY_ARN": "arn:aws:kms:us-east-1:123456789012:key/data",
        "COGNITO_USER_POOL_ID": "us-east-1_example",
        "COGNITO_USER_POOL_CLIENT_ID": "client-id",
        "DOCUMENT_STORAGE_MODE": "s3",
        "DOCUMENTS_QUARANTINE_BUCKET": "quarantine",
        "DOCUMENTS_CLEAN_BUCKET": "clean",
        "DOCUMENTS_KMS_KEY_ARN": "arn:aws:kms:us-east-1:123456789012:key/documents",
        "ACCOUNT_EXPORTS_BUCKET": "lifeledger-account-exports",
        "CORS_ALLOWED_ORIGINS": "https://lifeledger.example.com",
    }

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
    assert settings.record_attachments_table_name == DEFAULT_RECORD_ATTACHMENTS_TABLE_NAME
    assert settings.linked_items_table_name == DEFAULT_LINKED_ITEMS_TABLE_NAME
    assert settings.responsibility_history_table_name == DEFAULT_RESPONSIBILITY_HISTORY_TABLE_NAME
    assert settings.aws_region == "us-east-1"
    assert settings.local_data_file.endswith("backend\\data\\reminders.json") or settings.local_data_file.endswith(
        "backend/data/reminders.json"
    )
    assert settings.local_records_file.endswith("backend\\data\\records.json") or settings.local_records_file.endswith(
        "backend/data/records.json"
    )
    assert settings.local_record_attachments_file.endswith(
        "backend\\data\\record-attachments.json"
    ) or settings.local_record_attachments_file.endswith("backend/data/record-attachments.json")
    assert settings.local_linked_items_file.endswith(
        "backend\\data\\linked-items.json"
    ) or settings.local_linked_items_file.endswith("backend/data/linked-items.json")
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
    assert settings.local_responsibility_history_file.endswith(
        "backend\\data\\responsibility-history.json"
    ) or settings.local_responsibility_history_file.endswith("backend/data/responsibility-history.json")
    assert settings.push_notifications_configured is False
    assert settings.google_calendar_configured is False
    assert settings.google_calendar_scopes == DEFAULT_GOOGLE_CALENDAR_SCOPES
    assert settings.record_encryption_mode == RECORD_ENCRYPTION_DISABLED
    assert settings.data_encryption_kms_key_arn == ""
    assert settings.google_oauth_secret_arn == ""
    assert settings.push_secret_arn == ""
    assert settings.allow_plaintext_production_secrets is False
    assert settings.document_storage_mode == DOCUMENT_STORAGE_DISABLED
    assert settings.document_storage_configured is False
    assert settings.documents_quarantine_bucket == ""
    assert settings.documents_clean_bucket == ""
    assert settings.documents_kms_key_arn == ""
    assert settings.attachment_max_size_bytes == 10 * 1024 * 1024
    assert settings.attachment_max_per_record == 5
    assert settings.cors_allowed_origins == DEFAULT_CORS_ALLOWED_ORIGINS
    assert "https://lifeledger.jpreinold.com" in settings.cors_allowed_origins
    assert "https://www.lifeledger.jpreinold.com" in settings.cors_allowed_origins


def test_config_reads_environment_values():
    settings = load_settings(
        {
            "APP_ENV": "test",
            "AUTH_MODE": "cognito",
            "LOCAL_DEV_USER_ID": "dev-user",
            "PERSISTENCE_MODE": "dynamodb",
            "REMINDERS_TABLE_NAME": "custom-table",
            "RECORDS_TABLE_NAME": "custom-records",
            "PREFERENCES_TABLE_NAME": "custom-preferences",
            "PUSH_SUBSCRIPTIONS_TABLE_NAME": "custom-push",
            "GOOGLE_CALENDAR_CONNECTIONS_TABLE_NAME": "custom-google-connections",
            "GOOGLE_OAUTH_STATES_TABLE_NAME": "custom-google-states",
            "RECORD_ATTACHMENTS_TABLE_NAME": "custom-attachments",
            "LINKED_ITEMS_TABLE_NAME": "custom-linked-items",
            "RESPONSIBILITY_HISTORY_TABLE_NAME": "custom-history",
            "LOCAL_RESPONSIBILITY_HISTORY_FILE": "custom-history.json",
            "VAPID_PUBLIC_KEY": "public",
            "VAPID_PRIVATE_KEY": "private",
            "VAPID_SUBJECT": "mailto:test@example.com",
            "DATA_ENCRYPTION_KMS_KEY_ARN": "arn:aws:kms:us-west-2:123456789012:key/example",
            "RECORD_ENCRYPTION_MODE": "kms",
            "LOCAL_RECORDS_ENCRYPTION_KEY": "local-key",
            "GOOGLE_OAUTH_SECRET_ARN": "arn:aws:secretsmanager:us-west-2:123456789012:secret:google",
            "PUSH_SECRET_ARN": "arn:aws:secretsmanager:us-west-2:123456789012:secret:push",
            "ALLOW_PLAINTEXT_PRODUCTION_SECRETS": "true",
            "AWS_REGION": "us-west-2",
            "DOCUMENT_STORAGE_MODE": "s3",
            "DOCUMENTS_QUARANTINE_BUCKET": "quarantine-bucket",
            "DOCUMENTS_CLEAN_BUCKET": "clean-bucket",
            "DOCUMENTS_KMS_KEY_ARN": "arn:aws:kms:us-west-2:123456789012:key/documents",
            "ATTACHMENT_MAX_SIZE_BYTES": "4096",
            "ATTACHMENT_MAX_PER_RECORD": "3",
            "GOOGLE_CLIENT_ID": "google-client-id",
            "GOOGLE_CLIENT_SECRET": "google-client-secret",
            "GOOGLE_OAUTH_REDIRECT_URI": "https://example.com/oauth/google-calendar",
            "GOOGLE_CALENDAR_SCOPES": "https://www.googleapis.com/auth/calendar.events",
            "CORS_ALLOWED_ORIGINS": "https://example.com, http://localhost:5173",
        }
    )

    assert settings.app_env == "test"
    assert settings.auth_mode == COGNITO_AUTH_MODE
    assert settings.local_dev_user_id == "dev-user"
    assert settings.persistence_mode == DYNAMODB_PERSISTENCE
    assert settings.reminders_table_name == "custom-table"
    assert settings.records_table_name == "custom-records"
    assert settings.preferences_table_name == "custom-preferences"
    assert settings.push_subscriptions_table_name == "custom-push"
    assert settings.google_calendar_connections_table_name == "custom-google-connections"
    assert settings.google_oauth_states_table_name == "custom-google-states"
    assert settings.record_attachments_table_name == "custom-attachments"
    assert settings.linked_items_table_name == "custom-linked-items"
    assert settings.responsibility_history_table_name == "custom-history"
    assert settings.local_responsibility_history_file == "custom-history.json"
    assert settings.push_notifications_configured is True
    assert settings.google_calendar_configured is True
    assert settings.record_encryption_mode == RECORD_ENCRYPTION_KMS
    assert settings.data_encryption_kms_key_arn == "arn:aws:kms:us-west-2:123456789012:key/example"
    assert settings.local_records_encryption_key == "local-key"
    assert settings.google_oauth_secret_arn == "arn:aws:secretsmanager:us-west-2:123456789012:secret:google"
    assert settings.push_secret_arn == "arn:aws:secretsmanager:us-west-2:123456789012:secret:push"
    assert settings.allow_plaintext_production_secrets is True
    assert settings.aws_region == "us-west-2"
    assert settings.document_storage_mode == DOCUMENT_STORAGE_S3
    assert settings.document_storage_configured is True
    assert settings.documents_quarantine_bucket == "quarantine-bucket"
    assert settings.documents_clean_bucket == "clean-bucket"
    assert settings.documents_kms_key_arn == "arn:aws:kms:us-west-2:123456789012:key/documents"
    assert settings.attachment_max_size_bytes == 4096
    assert settings.attachment_max_per_record == 3
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


def test_config_allows_explicit_local_record_attachments_file():
    settings = load_settings({"LOCAL_RECORD_ATTACHMENTS_FILE": "/tmp/custom-attachments.json"})

    assert settings.local_record_attachments_file == "/tmp/custom-attachments.json"


def test_config_allows_explicit_local_linked_items_file():
    settings = load_settings({"LOCAL_LINKED_ITEMS_FILE": "/tmp/custom-linked-items.json"})

    assert settings.local_linked_items_file == "/tmp/custom-linked-items.json"


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
    assert settings.local_record_attachments_file == LAMBDA_LOCAL_RECORD_ATTACHMENTS_FILE
    assert settings.local_linked_items_file == LAMBDA_LOCAL_LINKED_ITEMS_FILE
    assert settings.local_preferences_file == LAMBDA_LOCAL_PREFERENCES_FILE
    assert settings.local_push_subscriptions_file == LAMBDA_LOCAL_PUSH_SUBSCRIPTIONS_FILE
    assert settings.local_google_calendar_connections_file == LAMBDA_LOCAL_GOOGLE_CALENDAR_CONNECTIONS_FILE
    assert settings.local_google_oauth_states_file == LAMBDA_LOCAL_GOOGLE_OAUTH_STATES_FILE


def test_config_rejects_unknown_app_environment_or_component():
    with pytest.raises(ValueError, match="Unsupported APP_ENV"):
        load_settings({"APP_ENV": "staging"})
    with pytest.raises(ValueError, match="Unsupported APP_COMPONENT"):
        load_settings({"APP_COMPONENT": "unknown"})


def test_config_rejects_unknown_persistence_mode():
    with pytest.raises(ValueError):
        load_settings({"PERSISTENCE_MODE": "sqlite"})


def test_config_rejects_unknown_auth_mode():
    with pytest.raises(ValueError):
        load_settings({"AUTH_MODE": "magic-link"})


def test_config_rejects_unknown_record_encryption_mode():
    with pytest.raises(ValueError):
        load_settings({"RECORD_ENCRYPTION_MODE": "plaintext"})


def test_config_rejects_unknown_document_storage_mode():
    with pytest.raises(ValueError):
        load_settings({"DOCUMENT_STORAGE_MODE": "public-bucket"})


def test_production_without_explicit_secure_configuration_is_rejected():
    with pytest.raises(ValueError, match="Unsafe production configuration"):
        load_settings({"APP_ENV": "production"})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("AUTH_MODE", "local", "AUTH_MODE must be cognito"),
        ("PERSISTENCE_MODE", "local", "PERSISTENCE_MODE must be dynamodb"),
        ("RECORD_ENCRYPTION_MODE", "disabled", "RECORD_ENCRYPTION_MODE must be kms"),
    ],
)
def test_production_rejects_insecure_modes(field: str, value: str, message: str):
    env = secure_production_env()
    env[field] = value
    with pytest.raises(ValueError, match=message):
        load_settings(env)


def test_production_rejects_plaintext_local_secret_providers_even_with_legacy_override():
    env = secure_production_env()
    env.update({
        "GOOGLE_CLIENT_SECRET": "secret",
        "VAPID_PRIVATE_KEY": "private",
        "ALLOW_PLAINTEXT_PRODUCTION_SECRETS": "true",
    })
    with pytest.raises(ValueError, match="local plaintext secret providers"):
        load_settings(env)


def test_secret_arns_configure_production_google_and_push():
    env = secure_production_env()
    env.update(
        {
            "GOOGLE_CLIENT_ID": "client-id",
            "GOOGLE_OAUTH_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:google",
            "GOOGLE_OAUTH_REDIRECT_URI": "https://example.com/oauth",
            "VAPID_PUBLIC_KEY": "public",
            "PUSH_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:push",
            "VAPID_SUBJECT": "mailto:test@example.com",
        }
    )
    settings = load_settings(env)
    assert settings.google_calendar_configured is True
    assert settings.push_notifications_configured is True
    assert settings.document_storage_configured is True


def test_local_record_encryption_mode_can_be_selected():
    settings = load_settings({"RECORD_ENCRYPTION_MODE": "local"})

    assert settings.record_encryption_mode == RECORD_ENCRYPTION_LOCAL
