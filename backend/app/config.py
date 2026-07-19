import json
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
SUPPORTED_APP_ENVS = {"local", "test", "production"}
SUPPORTED_APP_COMPONENTS = {"api", "digest", "attachment_finalizer", "reconciliation", "account_worker"}
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
LAMBDA_LOCAL_RESPONSIBILITY_HISTORY_FILE = "/tmp/lifeledger-responsibility-history.json"
LAMBDA_LOCAL_RECONCILIATION_FILE = "/tmp/lifeledger-reconciliation.json"
LAMBDA_LOCAL_ACCOUNT_OPERATIONS_FILE = "/tmp/lifeledger-account-operations.json"
LAMBDA_LOCAL_ASSISTANT_DATA_FILE = "/tmp/lifeledger-assistant-data.json"
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
DEFAULT_RESPONSIBILITY_HISTORY_TABLE_NAME = "lifeledger-responsibility-history-auth"
DEFAULT_RECONCILIATION_TABLE_NAME = "lifeledger-reconciliation-auth"
DEFAULT_ACCOUNT_OPERATIONS_TABLE_NAME = "lifeledger-account-operations-auth"
DEFAULT_ASSISTANT_DATA_TABLE_NAME = "lifeledger-assistant-data-auth"
AI_PROVIDER_DISABLED = "disabled"
AI_PROVIDER_OPENAI = "openai"
SUPPORTED_AI_PROVIDERS = {AI_PROVIDER_DISABLED, AI_PROVIDER_OPENAI}
DEFAULT_AI_MODEL_PRICING_JSON = (
    '{"gpt-5.6-luna":{"input":1.0,"output":6.0},'
    '"gpt-5.6-terra":{"input":2.5,"output":15.0}}'
)
DEFAULT_GOOGLE_CALENDAR_SCOPES = (
    "https://www.googleapis.com/auth/calendar.events "
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly"
)
DEFAULT_ATTACHMENT_MAX_SIZE_BYTES = 10 * 1024 * 1024
DEFAULT_ATTACHMENT_MAX_PER_RECORD = 5


@dataclass(frozen=True)
class Settings:
    app_env: str = "local"
    app_component: str = "api"
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
    responsibility_history_table_name: str = DEFAULT_RESPONSIBILITY_HISTORY_TABLE_NAME
    reconciliation_table_name: str = DEFAULT_RECONCILIATION_TABLE_NAME
    account_operations_table_name: str = DEFAULT_ACCOUNT_OPERATIONS_TABLE_NAME
    assistant_data_table_name: str = DEFAULT_ASSISTANT_DATA_TABLE_NAME
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
    local_responsibility_history_file: str = ""
    local_reconciliation_file: str = ""
    local_account_operations_file: str = ""
    local_assistant_data_file: str = ""
    cors_allowed_origins: list[str] | None = None
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = ""
    google_client_id: str = ""
    cognito_user_pool_id: str = ""
    cognito_user_pool_client_id: str = ""
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
    account_exports_bucket: str = ""
    account_operations_queue_url: str = ""
    ai_provider: str = AI_PROVIDER_DISABLED
    ai_default_model: str = "gpt-5.6-luna"
    ai_escalation_model: str = "gpt-5.6-terra"
    ai_emergency_disabled: bool = False
    ai_api_secret_arn: str = ""
    openai_api_key: str = ""
    ai_request_timeout_seconds: int = 20
    ai_input_token_limit: int = 2_000
    ai_output_token_limit: int = 1_200
    ai_max_clarification_calls: int = 1
    ai_default_monthly_budget_usd: float = 5.0
    ai_default_daily_request_limit: int = 50
    ai_model_pricing_json: str = DEFAULT_AI_MODEL_PRICING_JSON
    app_version: str = "0.1.0"
    git_commit: str = "unknown"
    build_timestamp: str = "unknown"

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
    app_env = (source.get("APP_ENV", "local").strip() or "local").lower()
    if app_env not in SUPPORTED_APP_ENVS:
        supported = ", ".join(sorted(SUPPORTED_APP_ENVS))
        raise ValueError(f"Unsupported APP_ENV '{app_env}'. Expected one of: {supported}.")

    app_component = (source.get("APP_COMPONENT", "api").strip() or "api").lower()
    if app_component not in SUPPORTED_APP_COMPONENTS:
        supported = ", ".join(sorted(SUPPORTED_APP_COMPONENTS))
        raise ValueError(f"Unsupported APP_COMPONENT '{app_component}'. Expected one of: {supported}.")

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

    default_document_storage_mode = DOCUMENT_STORAGE_S3 if app_env == "production" else DOCUMENT_STORAGE_DISABLED
    document_storage_mode = source.get("DOCUMENT_STORAGE_MODE", default_document_storage_mode).strip().lower()
    if document_storage_mode not in SUPPORTED_DOCUMENT_STORAGE_MODES:
        supported = ", ".join(sorted(SUPPORTED_DOCUMENT_STORAGE_MODES))
        raise ValueError(f"Unsupported DOCUMENT_STORAGE_MODE '{document_storage_mode}'. Expected one of: {supported}.")

    ai_provider = (source.get("AI_PROVIDER", AI_PROVIDER_DISABLED).strip() or AI_PROVIDER_DISABLED).lower()
    if ai_provider not in SUPPORTED_AI_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_AI_PROVIDERS))
        raise ValueError(f"Unsupported AI_PROVIDER '{ai_provider}'. Expected one of: {supported}.")

    settings = Settings(
        app_env=app_env,
        app_component=app_component,
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
        responsibility_history_table_name=source.get(
            "RESPONSIBILITY_HISTORY_TABLE_NAME",
            DEFAULT_RESPONSIBILITY_HISTORY_TABLE_NAME,
        ).strip()
        or DEFAULT_RESPONSIBILITY_HISTORY_TABLE_NAME,
        reconciliation_table_name=source.get(
            "RECONCILIATION_TABLE_NAME", DEFAULT_RECONCILIATION_TABLE_NAME
        ).strip()
        or DEFAULT_RECONCILIATION_TABLE_NAME,
        account_operations_table_name=source.get(
            "ACCOUNT_OPERATIONS_TABLE_NAME", DEFAULT_ACCOUNT_OPERATIONS_TABLE_NAME
        ).strip()
        or DEFAULT_ACCOUNT_OPERATIONS_TABLE_NAME,
        assistant_data_table_name=source.get(
            "ASSISTANT_DATA_TABLE_NAME", DEFAULT_ASSISTANT_DATA_TABLE_NAME
        ).strip()
        or DEFAULT_ASSISTANT_DATA_TABLE_NAME,
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
        local_responsibility_history_file=source.get("LOCAL_RESPONSIBILITY_HISTORY_FILE", "").strip()
        or default_local_responsibility_history_file(source),
        local_reconciliation_file=source.get("LOCAL_RECONCILIATION_FILE", "").strip()
        or default_local_reconciliation_file(source),
        local_account_operations_file=source.get("LOCAL_ACCOUNT_OPERATIONS_FILE", "").strip()
        or default_local_account_operations_file(source),
        local_assistant_data_file=source.get("LOCAL_ASSISTANT_DATA_FILE", "").strip()
        or default_local_assistant_data_file(source),
        cors_allowed_origins=parse_csv_list(source.get("CORS_ALLOWED_ORIGINS", ""))
        or DEFAULT_CORS_ALLOWED_ORIGINS,
        vapid_public_key=source.get("VAPID_PUBLIC_KEY", "").strip(),
        vapid_private_key=source.get("VAPID_PRIVATE_KEY", "").strip(),
        vapid_subject=source.get("VAPID_SUBJECT", "").strip(),
        google_client_id=source.get("GOOGLE_CLIENT_ID", "").strip(),
        cognito_user_pool_id=source.get("COGNITO_USER_POOL_ID", "").strip(),
        cognito_user_pool_client_id=source.get("COGNITO_USER_POOL_CLIENT_ID", "").strip(),
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
        account_exports_bucket=source.get("ACCOUNT_EXPORTS_BUCKET", "").strip(),
        account_operations_queue_url=source.get("ACCOUNT_OPERATIONS_QUEUE_URL", "").strip(),
        ai_provider=ai_provider,
        ai_default_model=source.get("AI_DEFAULT_MODEL", "gpt-5.6-luna").strip() or "gpt-5.6-luna",
        ai_escalation_model=source.get("AI_ESCALATION_MODEL", "gpt-5.6-terra").strip(),
        ai_emergency_disabled=parse_bool(source.get("AI_EMERGENCY_DISABLED", "false")),
        ai_api_secret_arn=source.get("AI_API_SECRET_ARN", "").strip(),
        openai_api_key=source.get("OPENAI_API_KEY", "").strip(),
        ai_request_timeout_seconds=parse_int(source.get("AI_REQUEST_TIMEOUT_SECONDS", "20"), 20),
        ai_input_token_limit=parse_int(source.get("AI_INPUT_TOKEN_LIMIT", "2000"), 2_000),
        ai_output_token_limit=parse_int(source.get("AI_OUTPUT_TOKEN_LIMIT", "1200"), 1_200),
        ai_max_clarification_calls=parse_int(source.get("AI_MAX_CLARIFICATION_CALLS", "1"), 1),
        ai_default_monthly_budget_usd=float(source.get("AI_DEFAULT_MONTHLY_BUDGET_USD", "5")),
        ai_default_daily_request_limit=parse_int(source.get("AI_DEFAULT_DAILY_REQUEST_LIMIT", "50"), 50),
        ai_model_pricing_json=source.get("AI_MODEL_PRICING_JSON", DEFAULT_AI_MODEL_PRICING_JSON).strip()
        or DEFAULT_AI_MODEL_PRICING_JSON,
        app_version=source.get("APP_VERSION", "0.1.0").strip() or "0.1.0",
        git_commit=source.get("GIT_COMMIT", "unknown").strip() or "unknown",
        build_timestamp=source.get("BUILD_TIMESTAMP", "unknown").strip() or "unknown",
    )
    validate_settings(settings)
    return settings


def validate_settings(settings: Settings) -> None:
    """Fail closed before any production component begins its work."""
    if not 1 <= settings.ai_request_timeout_seconds <= 60:
        raise ValueError("AI_REQUEST_TIMEOUT_SECONDS must be between 1 and 60.")
    if not 1 <= settings.ai_input_token_limit <= 10_000:
        raise ValueError("AI_INPUT_TOKEN_LIMIT must be between 1 and 10000.")
    if not 1 <= settings.ai_output_token_limit <= 5_000:
        raise ValueError("AI_OUTPUT_TOKEN_LIMIT must be between 1 and 5000.")
    if settings.ai_max_clarification_calls not in {0, 1}:
        raise ValueError("AI_MAX_CLARIFICATION_CALLS must be 0 or 1.")
    if not 0 <= settings.ai_default_monthly_budget_usd <= 100:
        raise ValueError("AI_DEFAULT_MONTHLY_BUDGET_USD must be between 0 and 100.")
    if not 1 <= settings.ai_default_daily_request_limit <= 500:
        raise ValueError("AI_DEFAULT_DAILY_REQUEST_LIMIT must be between 1 and 500.")
    try:
        pricing = json.loads(settings.ai_model_pricing_json)
        if not isinstance(pricing, dict) or any(
            not isinstance(rates, dict)
            or float(rates.get("input", -1)) < 0
            or float(rates.get("output", -1)) < 0
            for rates in pricing.values()
        ):
            raise ValueError
    except Exception as exc:
        raise ValueError("AI_MODEL_PRICING_JSON must contain non-negative input/output rates.") from exc
    configured_models = {settings.ai_default_model, settings.ai_escalation_model} - {""}
    if settings.ai_provider == AI_PROVIDER_OPENAI and not configured_models <= set(pricing):
        raise ValueError("AI_MODEL_PRICING_JSON must include every configured OpenAI model.")
    if settings.app_env != "production":
        return

    problems: list[str] = []
    if settings.persistence_mode != DYNAMODB_PERSISTENCE:
        problems.append("PERSISTENCE_MODE must be dynamodb")

    if settings.app_component == "api":
        if settings.auth_mode != COGNITO_AUTH_MODE:
            problems.append("AUTH_MODE must be cognito")
        if settings.record_encryption_mode != RECORD_ENCRYPTION_KMS:
            problems.append("RECORD_ENCRYPTION_MODE must be kms")
        if not settings.data_encryption_kms_key_arn:
            problems.append("DATA_ENCRYPTION_KMS_KEY_ARN is required")
        if not settings.cognito_user_pool_id:
            problems.append("COGNITO_USER_POOL_ID is required")
        if not settings.cognito_user_pool_client_id:
            problems.append("COGNITO_USER_POOL_CLIENT_ID is required")
        unsafe_origins = [
            origin
            for origin in settings.cors_allowed_origins or []
            if not origin.startswith("https://") or "localhost" in origin or "127.0.0.1" in origin or origin == "*"
        ]
        if not settings.cors_allowed_origins or unsafe_origins:
            problems.append("CORS_ALLOWED_ORIGINS must contain only explicit HTTPS production origins")

    if settings.app_component in {"api", "attachment_finalizer", "account_worker", "reconciliation"}:
        if settings.document_storage_mode != DOCUMENT_STORAGE_S3:
            problems.append("DOCUMENT_STORAGE_MODE must be s3")
        if not settings.documents_quarantine_bucket:
            problems.append("DOCUMENTS_QUARANTINE_BUCKET is required")
        if not settings.documents_clean_bucket:
            problems.append("DOCUMENTS_CLEAN_BUCKET is required")
        if not settings.documents_kms_key_arn:
            problems.append("DOCUMENTS_KMS_KEY_ARN is required")

    required_tables = {
        "REMINDERS_TABLE_NAME": settings.reminders_table_name,
        "RECORDS_TABLE_NAME": settings.records_table_name,
        "RESPONSIBILITY_HISTORY_TABLE_NAME": settings.responsibility_history_table_name,
        "RECONCILIATION_TABLE_NAME": settings.reconciliation_table_name,
        "ACCOUNT_OPERATIONS_TABLE_NAME": settings.account_operations_table_name,
        "ASSISTANT_DATA_TABLE_NAME": settings.assistant_data_table_name,
    }
    if any(not value for value in required_tables.values()):
        problems.append("all required data table names must be configured")

    if settings.app_component in {"api", "account_worker"} and not settings.account_exports_bucket:
        problems.append("ACCOUNT_EXPORTS_BUCKET is required")

    if settings.ai_provider == AI_PROVIDER_OPENAI and not settings.ai_api_secret_arn:
        problems.append("AI_API_SECRET_ARN is required when AI_PROVIDER is openai")

    if settings.local_records_encryption_key or settings.google_client_secret or settings.vapid_private_key or settings.openai_api_key:
        problems.append("local plaintext secret providers are not allowed")

    if problems:
        raise ValueError("Unsafe production configuration: " + "; ".join(problems) + ".")

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


def default_local_responsibility_history_file(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env
    if source.get("AWS_SAM_LOCAL") == "true" or source.get("AWS_LAMBDA_FUNCTION_NAME"):
        return LAMBDA_LOCAL_RESPONSIBILITY_HISTORY_FILE
    backend_root = Path(__file__).resolve().parents[1]
    return str(backend_root / "data" / "responsibility-history.json")


def default_local_reconciliation_file(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env
    if source.get("AWS_SAM_LOCAL") == "true" or source.get("AWS_LAMBDA_FUNCTION_NAME"):
        return LAMBDA_LOCAL_RECONCILIATION_FILE
    backend_root = Path(__file__).resolve().parents[1]
    return str(backend_root / "data" / "reconciliation.json")


def default_local_account_operations_file(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env
    if source.get("AWS_SAM_LOCAL") == "true" or source.get("AWS_LAMBDA_FUNCTION_NAME"):
        return LAMBDA_LOCAL_ACCOUNT_OPERATIONS_FILE
    backend_root = Path(__file__).resolve().parents[1]
    return str(backend_root / "data" / "account-operations.json")


def default_local_assistant_data_file(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env
    if source.get("AWS_SAM_LOCAL") == "true" or source.get("AWS_LAMBDA_FUNCTION_NAME"):
        return LAMBDA_LOCAL_ASSISTANT_DATA_FILE
    backend_root = Path(__file__).resolve().parents[1]
    return str(backend_root / "data" / "assistant-data.json")


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



