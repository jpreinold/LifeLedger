import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping


LOCAL_AUTH_MODE = "local"
COGNITO_AUTH_MODE = "cognito"
SUPPORTED_AUTH_MODES = {LOCAL_AUTH_MODE, COGNITO_AUTH_MODE}
LOCAL_PERSISTENCE = "local"
DYNAMODB_PERSISTENCE = "dynamodb"
SUPPORTED_PERSISTENCE_MODES = {LOCAL_PERSISTENCE, DYNAMODB_PERSISTENCE}
RECORD_ENCRYPTION_DISABLED = "disabled"
RECORD_ENCRYPTION_LOCAL = "local"
RECORD_ENCRYPTION_KMS = "kms"
SUPPORTED_RECORD_ENCRYPTION_MODES = {
    RECORD_ENCRYPTION_DISABLED,
    RECORD_ENCRYPTION_LOCAL,
    RECORD_ENCRYPTION_KMS,
}
DOCUMENT_STORAGE_DISABLED = "disabled"
DOCUMENT_STORAGE_LOCAL = "local"
DOCUMENT_STORAGE_S3 = "s3"
SUPPORTED_DOCUMENT_STORAGE_MODES = {
    DOCUMENT_STORAGE_DISABLED,
    DOCUMENT_STORAGE_LOCAL,
    DOCUMENT_STORAGE_S3,
}
LAMBDA_LOCAL_DATA_FILE = "/tmp/lifeledger-reminders.json"
LAMBDA_LOCAL_RECORDS_FILE = "/tmp/lifeledger-records.json"
LAMBDA_LOCAL_RECORD_ATTACHMENTS_FILE = "/tmp/lifeledger-record-attachments.json"
LAMBDA_LOCAL_LINKED_ITEMS_FILE = "/tmp/lifeledger-linked-items.json"
LAMBDA_LOCAL_SEARCH_INDEX_FILE = "/tmp/lifeledger-search-index.json"
LAMBDA_LOCAL_SAVED_VIEWS_FILE = "/tmp/lifeledger-saved-views.json"
LAMBDA_LOCAL_PREFERENCES_FILE = "/tmp/lifeledger-preferences.json"
LAMBDA_LOCAL_PUSH_SUBSCRIPTIONS_FILE = "/tmp/lifeledger-push-subscriptions.json"
LAMBDA_LOCAL_GOOGLE_CALENDAR_CONNECTIONS_FILE = "/tmp/lifeledger-google-calendar-connections.json"
LAMBDA_LOCAL_GOOGLE_OAUTH_STATES_FILE = "/tmp/lifeledger-google-oauth-states.json"
DEFAULT_LOCAL_DEV_USER_ID = "local-dev-user"
DEFAULT_CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://lifeledger.jpreinold.com",
    "https://www.lifeledger.jpreinold.com",
]
DEFAULT_REMINDERS_TABLE_NAME = "lifeledger-reminders-auth"
DEFAULT_RECORDS_TABLE_NAME = "lifeledger-records-auth"
DEFAULT_PREFERENCES_TABLE_NAME = "lifeledger-preferences-auth"
DEFAULT_PUSH_SUBSCRIPTIONS_TABLE_NAME = "lifeledger-push-subscriptions-auth"
DEFAULT_GOOGLE_CALENDAR_CONNECTIONS_TABLE_NAME = "lifeledger-google-calendar-connections-auth"
DEFAULT_GOOGLE_OAUTH_STATES_TABLE_NAME = "lifeledger-google-oauth-states-auth"
DEFAULT_RECORD_ATTACHMENTS_TABLE_NAME = "lifeledger-record-attachments-auth"
DEFAULT_LINKED_ITEMS_TABLE_NAME = "lifeledger-linked-items-auth"
DEFAULT_SEARCH_INDEX_TABLE_NAME = "lifeledger-search-index-auth"
DEFAULT_SAVED_VIEWS_TABLE_NAME = "lifeledger-saved-views-auth"
DEFAULT_GOOGLE_CALENDAR_SCOPES = (
    "https://www.googleapis.com/auth/calendar.events "
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly"
)
DEFAULT_ATTACHMENT_MAX_SIZE_BYTES = 10 * 1024 * 1024
DEFAULT_ATTACHMENT_MAX_PER_RECORD = 5


@dataclass(frozen=True)
class Settings:
    app_env: str = "local"
    auth_mode: str = LOCAL_AUTH_MODE
    local_dev_user_id: str = DEFAULT_LOCAL_DEV_USER_ID
    persistence_mode: str = LOCAL_PERSISTENCE
    reminders_table_name: str = DEFAULT_REMINDERS_TABLE_NAME
    records_table_name: str = DEFAULT_RECORDS_TABLE_NAME
    preferences_table_name: str = DEFAULT_PREFERENCES_TABLE_NAME
    push_subscriptions_table_name: str = DEFAULT_PUSH_SUBSCRIPTIONS_TABLE_NAME
    google_calendar_connections_table_name: str = DEFAULT_GOOGLE_CALENDAR_CONNECTIONS_TABLE_NAME
    google_oauth_states_table_name: str = DEFAULT_GOOGLE_OAUTH_STATES_TABLE_NAME
    record_attachments_table_name: str = DEFAULT_RECORD_ATTACHMENTS_TABLE_NAME
    linked_items_table_name: str = DEFAULT_LINKED_ITEMS_TABLE_NAME
    search_index_table_name: str = DEFAULT_SEARCH_INDEX_TABLE_NAME
    saved_views_table_name: str = DEFAULT_SAVED_VIEWS_TABLE_NAME
    aws_region: str = "us-east-1"
    local_data_file: str = ""
    local_records_file: str = ""
    local_record_attachments_file: str = ""
    local_linked_items_file: str = ""
    local_search_index_file: str = ""
    local_saved_views_file: str = ""
    local_preferences_file: str = ""
    local_push_subscriptions_file: str = ""
    local_google_calendar_connections_file: str = ""
    local_google_oauth_states_file: str = ""
    cors_allowed_origins: list[str] | None = None
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_oauth_redirect_uri: str = ""
    google_calendar_scopes: str = DEFAULT_GOOGLE_CALENDAR_SCOPES
    data_encryption_kms_key_arn: str = ""
    record_encryption_mode: str = RECORD_ENCRYPTION_DISABLED
    local_records_encryption_key: str = ""
    google_oauth_secret_arn: str = ""
    push_secret_arn: str = ""
    allow_plaintext_production_secrets: bool = False
    document_storage_mode: str = DOCUMENT_STORAGE_DISABLED
    documents_quarantine_bucket: str = ""
    documents_clean_bucket: str = ""
    documents_kms_key_arn: str = ""
    attachment_max_size_bytes: int = DEFAULT_ATTACHMENT_MAX_SIZE_BYTES
    attachment_max_per_record: int = DEFAULT_ATTACHMENT_MAX_PER_RECORD

    @property
    def plaintext_secret_fallback_allowed(self) -> bool:
        return self.app_env != "production" or self.allow_plaintext_production_secrets

    @property
    def push_notifications_configured(self) -> bool:
        private_key_configured = bool(self.push_secret_arn) or (
            self.plaintext_secret_fallback_allowed and bool(self.vapid_private_key)
        )
        return bool(self.vapid_public_key and private_key_configured and self.vapid_subject)

    @property
    def google_calendar_configured(self) -> bool:
        client_secret_configured = bool(self.google_oauth_secret_arn) or (
            self.plaintext_secret_fallback_allowed and bool(self.google_client_secret)
        )
        return bool(
            self.google_client_id
            and client_secret_configured
            and self.google_oauth_redirect_uri
            and self.google_calendar_scopes
        )

    @property
    def document_storage_configured(self) -> bool:
        return bool(
            self.document_storage_mode == DOCUMENT_STORAGE_S3
            and self.documents_quarantine_bucket
            and self.documents_clean_bucket
            and self.documents_kms_key_arn
        )


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    source = os.environ if env is None else env
    auth_mode = source.get("AUTH_MODE", LOCAL_AUTH_MODE).strip().lower()
    persistence_mode = source.get("PERSISTENCE_MODE", LOCAL_PERSISTENCE).strip().lower()

    if auth_mode not in SUPPORTED_AUTH_MODES:
        supported = ", ".join(sorted(SUPPORTED_AUTH_MODES))
        raise ValueError(f"Unsupported AUTH_MODE '{auth_mode}'. Expected one of: {supported}.")

    if persistence_mode not in SUPPORTED_PERSISTENCE_MODES:
        supported = ", ".join(sorted(SUPPORTED_PERSISTENCE_MODES))
        raise ValueError(f"Unsupported PERSISTENCE_MODE '{persistence_mode}'. Expected one of: {supported}.")

    record_encryption_mode = source.get("RECORD_ENCRYPTION_MODE", RECORD_ENCRYPTION_DISABLED).strip().lower()
    if record_encryption_mode not in SUPPORTED_RECORD_ENCRYPTION_MODES:
        supported = ", ".join(sorted(SUPPORTED_RECORD_ENCRYPTION_MODES))
        raise ValueError(f"Unsupported RECORD_ENCRYPTION_MODE '{record_encryption_mode}'. Expected one of: {supported}.")

    app_env = source.get("APP_ENV", "local").strip() or "local"
    default_document_storage_mode = DOCUMENT_STORAGE_S3 if app_env == "production" else DOCUMENT_STORAGE_DISABLED
    document_storage_mode = source.get("DOCUMENT_STORAGE_MODE", default_document_storage_mode).strip().lower()
    if document_storage_mode not in SUPPORTED_DOCUMENT_STORAGE_MODES:
        supported = ", ".join(sorted(SUPPORTED_DOCUMENT_STORAGE_MODES))
        raise ValueError(f"Unsupported DOCUMENT_STORAGE_MODE '{document_storage_mode}'. Expected one of: {supported}.")

    return Settings(
        app_env=app_env,
        auth_mode=auth_mode,
        local_dev_user_id=source.get("LOCAL_DEV_USER_ID", DEFAULT_LOCAL_DEV_USER_ID).strip()
        or DEFAULT_LOCAL_DEV_USER_ID,
        persistence_mode=persistence_mode,
        reminders_table_name=source.get("REMINDERS_TABLE_NAME", DEFAULT_REMINDERS_TABLE_NAME).strip()
        or DEFAULT_REMINDERS_TABLE_NAME,
        records_table_name=source.get("RECORDS_TABLE_NAME", DEFAULT_RECORDS_TABLE_NAME).strip()
        or DEFAULT_RECORDS_TABLE_NAME,
        preferences_table_name=source.get("PREFERENCES_TABLE_NAME", DEFAULT_PREFERENCES_TABLE_NAME).strip()
        or DEFAULT_PREFERENCES_TABLE_NAME,
        push_subscriptions_table_name=source.get(
            "PUSH_SUBSCRIPTIONS_TABLE_NAME",
            DEFAULT_PUSH_SUBSCRIPTIONS_TABLE_NAME,
        ).strip()
        or DEFAULT_PUSH_SUBSCRIPTIONS_TABLE_NAME,
        google_calendar_connections_table_name=source.get(
            "GOOGLE_CALENDAR_CONNECTIONS_TABLE_NAME",
            DEFAULT_GOOGLE_CALENDAR_CONNECTIONS_TABLE_NAME,
        ).strip()
        or DEFAULT_GOOGLE_CALENDAR_CONNECTIONS_TABLE_NAME,
        google_oauth_states_table_name=source.get(
            "GOOGLE_OAUTH_STATES_TABLE_NAME",
            DEFAULT_GOOGLE_OAUTH_STATES_TABLE_NAME,
        ).strip()
        or DEFAULT_GOOGLE_OAUTH_STATES_TABLE_NAME,
        record_attachments_table_name=source.get(
            "RECORD_ATTACHMENTS_TABLE_NAME",
            DEFAULT_RECORD_ATTACHMENTS_TABLE_NAME,
        ).strip()
        or DEFAULT_RECORD_ATTACHMENTS_TABLE_NAME,
        linked_items_table_name=source.get("LINKED_ITEMS_TABLE_NAME", DEFAULT_LINKED_ITEMS_TABLE_NAME).strip()
        or DEFAULT_LINKED_ITEMS_TABLE_NAME,
        search_index_table_name=source.get("SEARCH_INDEX_TABLE_NAME", DEFAULT_SEARCH_INDEX_TABLE_NAME).strip()
        or DEFAULT_SEARCH_INDEX_TABLE_NAME,
        saved_views_table_name=source.get("SAVED_VIEWS_TABLE_NAME", DEFAULT_SAVED_VIEWS_TABLE_NAME).strip()
        or DEFAULT_SAVED_VIEWS_TABLE_NAME,
        aws_region=source.get("AWS_REGION", "us-east-1").strip() or "us-east-1",
        local_data_file=source.get("LOCAL_DATA_FILE", "").strip() or default_local_data_file(source),
        local_records_file=source.get("LOCAL_RECORDS_FILE", "").strip() or default_local_records_file(source),
        local_record_attachments_file=source.get("LOCAL_RECORD_ATTACHMENTS_FILE", "").strip()
        or default_local_record_attachments_file(source),
        local_linked_items_file=source.get("LOCAL_LINKED_ITEMS_FILE", "").strip()
        or default_local_linked_items_file(source),
        local_search_index_file=source.get("LOCAL_SEARCH_INDEX_FILE", "").strip()
        or default_local_search_index_file(source),
        local_saved_views_file=source.get("LOCAL_SAVED_VIEWS_FILE", "").strip()
        or default_local_saved_views_file(source),
        local_preferences_file=source.get("LOCAL_PREFERENCES_FILE", "").strip()
        or default_local_preferences_file(source),
        local_push_subscriptions_file=source.get("LOCAL_PUSH_SUBSCRIPTIONS_FILE", "").strip()
        or default_local_push_subscriptions_file(source),
        local_google_calendar_connections_file=source.get("LOCAL_GOOGLE_CALENDAR_CONNECTIONS_FILE", "").strip()
        or default_local_google_calendar_connections_file(source),
        local_google_oauth_states_file=source.get("LOCAL_GOOGLE_OAUTH_STATES_FILE", "").strip()
        or default_local_google_oauth_states_file(source),
        cors_allowed_origins=parse_csv_list(source.get("CORS_ALLOWED_ORIGINS", ""))
        or DEFAULT_CORS_ALLOWED_ORIGINS,
        vapid_public_key=source.get("VAPID_PUBLIC_KEY", "").strip(),
        vapid_private_key=source.get("VAPID_PRIVATE_KEY", "").strip(),
        vapid_subject=source.get("VAPID_SUBJECT", "").strip(),
        google_client_id=source.get("GOOGLE_CLIENT_ID", "").strip(),
        google_client_secret=source.get("GOOGLE_CLIENT_SECRET", "").strip(),
        google_oauth_redirect_uri=source.get("GOOGLE_OAUTH_REDIRECT_URI", "").strip(),
        google_calendar_scopes=source.get("GOOGLE_CALENDAR_SCOPES", DEFAULT_GOOGLE_CALENDAR_SCOPES).strip()
        or DEFAULT_GOOGLE_CALENDAR_SCOPES,
        data_encryption_kms_key_arn=source.get("DATA_ENCRYPTION_KMS_KEY_ARN", "").strip(),
        record_encryption_mode=record_encryption_mode,
        local_records_encryption_key=source.get("LOCAL_RECORDS_ENCRYPTION_KEY", "").strip(),
        google_oauth_secret_arn=source.get("GOOGLE_OAUTH_SECRET_ARN", "").strip(),
        push_secret_arn=source.get("PUSH_SECRET_ARN", "").strip(),
        allow_plaintext_production_secrets=parse_bool(
            source.get("ALLOW_PLAINTEXT_PRODUCTION_SECRETS", "false")
        ),
        document_storage_mode=document_storage_mode,
        documents_quarantine_bucket=source.get("DOCUMENTS_QUARANTINE_BUCKET", "").strip(),
        documents_clean_bucket=source.get("DOCUMENTS_CLEAN_BUCKET", "").strip(),
        documents_kms_key_arn=source.get("DOCUMENTS_KMS_KEY_ARN", "").strip(),
        attachment_max_size_bytes=parse_int(
            source.get("ATTACHMENT_MAX_SIZE_BYTES", str(DEFAULT_ATTACHMENT_MAX_SIZE_BYTES)),
            DEFAULT_ATTACHMENT_MAX_SIZE_BYTES,
        ),
        attachment_max_per_record=parse_int(
            source.get("ATTACHMENT_MAX_PER_RECORD", str(DEFAULT_ATTACHMENT_MAX_PER_RECORD)),
            DEFAULT_ATTACHMENT_MAX_PER_RECORD,
        ),
    )


def default_local_data_file(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env

    if source.get("AWS_SAM_LOCAL") == "true" or source.get("AWS_LAMBDA_FUNCTION_NAME"):
        return LAMBDA_LOCAL_DATA_FILE

    backend_root = Path(__file__).resolve().parents[1]
    return str(backend_root / "data" / "reminders.json")


def default_local_records_file(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env

    if source.get("AWS_SAM_LOCAL") == "true" or source.get("AWS_LAMBDA_FUNCTION_NAME"):
        return LAMBDA_LOCAL_RECORDS_FILE

    backend_root = Path(__file__).resolve().parents[1]
    return str(backend_root / "data" / "records.json")


def default_local_record_attachments_file(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env

    if source.get("AWS_SAM_LOCAL") == "true" or source.get("AWS_LAMBDA_FUNCTION_NAME"):
        return LAMBDA_LOCAL_RECORD_ATTACHMENTS_FILE

    backend_root = Path(__file__).resolve().parents[1]
    return str(backend_root / "data" / "record-attachments.json")


def default_local_linked_items_file(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env

    if source.get("AWS_SAM_LOCAL") == "true" or source.get("AWS_LAMBDA_FUNCTION_NAME"):
        return LAMBDA_LOCAL_LINKED_ITEMS_FILE

    backend_root = Path(__file__).resolve().parents[1]
    return str(backend_root / "data" / "linked-items.json")


def default_local_search_index_file(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env

    if source.get("AWS_SAM_LOCAL") == "true" or source.get("AWS_LAMBDA_FUNCTION_NAME"):
        return LAMBDA_LOCAL_SEARCH_INDEX_FILE

    backend_root = Path(__file__).resolve().parents[1]
    return str(backend_root / "data" / "search-index.json")


def default_local_saved_views_file(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env

    if source.get("AWS_SAM_LOCAL") == "true" or source.get("AWS_LAMBDA_FUNCTION_NAME"):
        return LAMBDA_LOCAL_SAVED_VIEWS_FILE

    backend_root = Path(__file__).resolve().parents[1]
    return str(backend_root / "data" / "saved-views.json")

def default_local_preferences_file(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env

    if source.get("AWS_SAM_LOCAL") == "true" or source.get("AWS_LAMBDA_FUNCTION_NAME"):
        return LAMBDA_LOCAL_PREFERENCES_FILE

    backend_root = Path(__file__).resolve().parents[1]
    return str(backend_root / "data" / "preferences.json")


def default_local_push_subscriptions_file(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env

    if source.get("AWS_SAM_LOCAL") == "true" or source.get("AWS_LAMBDA_FUNCTION_NAME"):
        return LAMBDA_LOCAL_PUSH_SUBSCRIPTIONS_FILE

    backend_root = Path(__file__).resolve().parents[1]
    return str(backend_root / "data" / "push-subscriptions.json")


def default_local_google_calendar_connections_file(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env

    if source.get("AWS_SAM_LOCAL") == "true" or source.get("AWS_LAMBDA_FUNCTION_NAME"):
        return LAMBDA_LOCAL_GOOGLE_CALENDAR_CONNECTIONS_FILE

    backend_root = Path(__file__).resolve().parents[1]
    return str(backend_root / "data" / "google-calendar-connections.json")


def default_local_google_oauth_states_file(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env

    if source.get("AWS_SAM_LOCAL") == "true" or source.get("AWS_LAMBDA_FUNCTION_NAME"):
        return LAMBDA_LOCAL_GOOGLE_OAUTH_STATES_FILE

    backend_root = Path(__file__).resolve().parents[1]
    return str(backend_root / "data" / "google-oauth-states.json")


def parse_csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()



