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
LAMBDA_LOCAL_DATA_FILE = "/tmp/lifeledger-reminders.json"
LAMBDA_LOCAL_PREFERENCES_FILE = "/tmp/lifeledger-preferences.json"
LAMBDA_LOCAL_PUSH_SUBSCRIPTIONS_FILE = "/tmp/lifeledger-push-subscriptions.json"
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
DEFAULT_PREFERENCES_TABLE_NAME = "lifeledger-preferences-auth"
DEFAULT_PUSH_SUBSCRIPTIONS_TABLE_NAME = "lifeledger-push-subscriptions-auth"


@dataclass(frozen=True)
class Settings:
    app_env: str = "local"
    auth_mode: str = LOCAL_AUTH_MODE
    local_dev_user_id: str = DEFAULT_LOCAL_DEV_USER_ID
    persistence_mode: str = LOCAL_PERSISTENCE
    reminders_table_name: str = DEFAULT_REMINDERS_TABLE_NAME
    preferences_table_name: str = DEFAULT_PREFERENCES_TABLE_NAME
    push_subscriptions_table_name: str = DEFAULT_PUSH_SUBSCRIPTIONS_TABLE_NAME
    aws_region: str = "us-east-1"
    local_data_file: str = ""
    local_preferences_file: str = ""
    local_push_subscriptions_file: str = ""
    cors_allowed_origins: list[str] | None = None
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = ""

    @property
    def push_notifications_configured(self) -> bool:
        return bool(self.vapid_public_key and self.vapid_private_key and self.vapid_subject)


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

    return Settings(
        app_env=source.get("APP_ENV", "local").strip() or "local",
        auth_mode=auth_mode,
        local_dev_user_id=source.get("LOCAL_DEV_USER_ID", DEFAULT_LOCAL_DEV_USER_ID).strip()
        or DEFAULT_LOCAL_DEV_USER_ID,
        persistence_mode=persistence_mode,
        reminders_table_name=source.get("REMINDERS_TABLE_NAME", DEFAULT_REMINDERS_TABLE_NAME).strip()
        or DEFAULT_REMINDERS_TABLE_NAME,
        preferences_table_name=source.get("PREFERENCES_TABLE_NAME", DEFAULT_PREFERENCES_TABLE_NAME).strip()
        or DEFAULT_PREFERENCES_TABLE_NAME,
        push_subscriptions_table_name=source.get(
            "PUSH_SUBSCRIPTIONS_TABLE_NAME",
            DEFAULT_PUSH_SUBSCRIPTIONS_TABLE_NAME,
        ).strip()
        or DEFAULT_PUSH_SUBSCRIPTIONS_TABLE_NAME,
        aws_region=source.get("AWS_REGION", "us-east-1").strip() or "us-east-1",
        local_data_file=source.get("LOCAL_DATA_FILE", "").strip() or default_local_data_file(source),
        local_preferences_file=source.get("LOCAL_PREFERENCES_FILE", "").strip()
        or default_local_preferences_file(source),
        local_push_subscriptions_file=source.get("LOCAL_PUSH_SUBSCRIPTIONS_FILE", "").strip()
        or default_local_push_subscriptions_file(source),
        cors_allowed_origins=parse_csv_list(source.get("CORS_ALLOWED_ORIGINS", ""))
        or DEFAULT_CORS_ALLOWED_ORIGINS,
        vapid_public_key=source.get("VAPID_PUBLIC_KEY", "").strip(),
        vapid_private_key=source.get("VAPID_PRIVATE_KEY", "").strip(),
        vapid_subject=source.get("VAPID_SUBJECT", "").strip(),
    )


def default_local_data_file(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env

    if source.get("AWS_SAM_LOCAL") == "true" or source.get("AWS_LAMBDA_FUNCTION_NAME"):
        return LAMBDA_LOCAL_DATA_FILE

    backend_root = Path(__file__).resolve().parents[1]
    return str(backend_root / "data" / "reminders.json")


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


def parse_csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
