from pathlib import Path
from typing import Any

from app.config import DYNAMODB_PERSISTENCE, Settings, get_settings
from app.dynamo_repository import DynamoReminderRepository
from app.preferences_repository import DynamoPreferencesRepository, LocalPreferencesRepository, PreferencesRepository
from app.repository import LocalReminderRepository, ReminderRepository


def create_repository(
    settings: Settings | None = None,
    *,
    local_file_path: str | Path | None = None,
    dynamo_table: Any | None = None,
) -> ReminderRepository:
    resolved_settings = settings or get_settings()

    if resolved_settings.persistence_mode == DYNAMODB_PERSISTENCE:
        return DynamoReminderRepository(
            table_name=resolved_settings.reminders_table_name,
            region_name=resolved_settings.aws_region,
            table=dynamo_table,
        )

    return LocalReminderRepository(local_file_path or resolved_settings.local_data_file)


def create_preferences_repository(
    settings: Settings | None = None,
    *,
    local_file_path: str | Path | None = None,
    dynamo_table: Any | None = None,
) -> PreferencesRepository:
    resolved_settings = settings or get_settings()

    if resolved_settings.persistence_mode == DYNAMODB_PERSISTENCE:
        return DynamoPreferencesRepository(
            table_name=resolved_settings.preferences_table_name,
            region_name=resolved_settings.aws_region,
            table=dynamo_table,
        )

    return LocalPreferencesRepository(local_file_path or resolved_settings.local_preferences_file)
