import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping


LOCAL_PERSISTENCE = "local"
DYNAMODB_PERSISTENCE = "dynamodb"
SUPPORTED_PERSISTENCE_MODES = {LOCAL_PERSISTENCE, DYNAMODB_PERSISTENCE}
LAMBDA_LOCAL_DATA_FILE = "/tmp/lifeledger-reminders.json"
DEFAULT_CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://lifeledger.jpreinold.com",
]


@dataclass(frozen=True)
class Settings:
    app_env: str = "local"
    persistence_mode: str = LOCAL_PERSISTENCE
    reminders_table_name: str = "lifeledger-reminders"
    aws_region: str = "us-east-1"
    local_data_file: str = ""
    cors_allowed_origins: list[str] | None = None


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    source = os.environ if env is None else env
    persistence_mode = source.get("PERSISTENCE_MODE", LOCAL_PERSISTENCE).strip().lower()

    if persistence_mode not in SUPPORTED_PERSISTENCE_MODES:
        supported = ", ".join(sorted(SUPPORTED_PERSISTENCE_MODES))
        raise ValueError(f"Unsupported PERSISTENCE_MODE '{persistence_mode}'. Expected one of: {supported}.")

    return Settings(
        app_env=source.get("APP_ENV", "local").strip() or "local",
        persistence_mode=persistence_mode,
        reminders_table_name=source.get("REMINDERS_TABLE_NAME", "lifeledger-reminders").strip()
        or "lifeledger-reminders",
        aws_region=source.get("AWS_REGION", "us-east-1").strip() or "us-east-1",
        local_data_file=source.get("LOCAL_DATA_FILE", "").strip() or default_local_data_file(source),
        cors_allowed_origins=parse_csv_list(source.get("CORS_ALLOWED_ORIGINS", ""))
        or DEFAULT_CORS_ALLOWED_ORIGINS,
    )


def default_local_data_file(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env

    if source.get("AWS_SAM_LOCAL") == "true" or source.get("AWS_LAMBDA_FUNCTION_NAME"):
        return LAMBDA_LOCAL_DATA_FILE

    backend_root = Path(__file__).resolve().parents[1]
    return str(backend_root / "data" / "reminders.json")


def parse_csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
