from pathlib import Path
from typing import Any

from app.attachments_repository import (
    DynamoRecordAttachmentRepository,
    LocalRecordAttachmentRepository,
    RecordAttachmentRepository,
)
from app.config import DYNAMODB_PERSISTENCE, Settings, get_settings
from app.dynamo_repository import DynamoRecordRepository, DynamoReminderRepository
from app.encryption_service import EncryptionService
from app.google_calendar_repository import (
    DynamoGoogleCalendarConnectionRepository,
    DynamoGoogleOAuthStateRepository,
    GoogleCalendarConnectionRepository,
    GoogleOAuthStateRepository,
    LocalGoogleCalendarConnectionRepository,
    LocalGoogleOAuthStateRepository,
)
from app.preferences_repository import DynamoPreferencesRepository, LocalPreferencesRepository, PreferencesRepository
from app.push_repository import DynamoPushSubscriptionRepository, LocalPushSubscriptionRepository, PushSubscriptionRepository
from app.records_repository import LocalRecordRepository, RecordRepository
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


def create_record_repository(
    settings: Settings | None = None,
    *,
    local_file_path: str | Path | None = None,
    dynamo_table: Any | None = None,
) -> RecordRepository:
    resolved_settings = settings or get_settings()

    if resolved_settings.persistence_mode == DYNAMODB_PERSISTENCE:
        return DynamoRecordRepository(
            table_name=resolved_settings.records_table_name,
            region_name=resolved_settings.aws_region,
            table=dynamo_table,
        )

    return LocalRecordRepository(local_file_path or resolved_settings.local_records_file)


def create_record_attachment_repository(
    settings: Settings | None = None,
    *,
    local_file_path: str | Path | None = None,
    dynamo_table: Any | None = None,
) -> RecordAttachmentRepository:
    resolved_settings = settings or get_settings()

    if resolved_settings.persistence_mode == DYNAMODB_PERSISTENCE:
        return DynamoRecordAttachmentRepository(
            table_name=resolved_settings.record_attachments_table_name,
            region_name=resolved_settings.aws_region,
            table=dynamo_table,
        )

    return LocalRecordAttachmentRepository(local_file_path or resolved_settings.local_record_attachments_file)


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


def create_push_subscription_repository(
    settings: Settings | None = None,
    *,
    local_file_path: str | Path | None = None,
    dynamo_table: Any | None = None,
) -> PushSubscriptionRepository:
    resolved_settings = settings or get_settings()

    if resolved_settings.persistence_mode == DYNAMODB_PERSISTENCE:
        return DynamoPushSubscriptionRepository(
            table_name=resolved_settings.push_subscriptions_table_name,
            region_name=resolved_settings.aws_region,
            table=dynamo_table,
        )

    return LocalPushSubscriptionRepository(local_file_path or resolved_settings.local_push_subscriptions_file)


def create_google_calendar_connection_repository(
    settings: Settings | None = None,
    *,
    local_file_path: str | Path | None = None,
    dynamo_table: Any | None = None,
    encryption_service: EncryptionService | None = None,
) -> GoogleCalendarConnectionRepository:
    resolved_settings = settings or get_settings()
    resolved_encryption_service = encryption_service or create_encryption_service(resolved_settings)

    if resolved_settings.persistence_mode == DYNAMODB_PERSISTENCE:
        return DynamoGoogleCalendarConnectionRepository(
            table_name=resolved_settings.google_calendar_connections_table_name,
            region_name=resolved_settings.aws_region,
            table=dynamo_table,
            encryption_service=resolved_encryption_service,
        )

    return LocalGoogleCalendarConnectionRepository(
        local_file_path or resolved_settings.local_google_calendar_connections_file,
        encryption_service=resolved_encryption_service,
    )


def create_google_oauth_state_repository(
    settings: Settings | None = None,
    *,
    local_file_path: str | Path | None = None,
    dynamo_table: Any | None = None,
) -> GoogleOAuthStateRepository:
    resolved_settings = settings or get_settings()

    if resolved_settings.persistence_mode == DYNAMODB_PERSISTENCE:
        return DynamoGoogleOAuthStateRepository(
            table_name=resolved_settings.google_oauth_states_table_name,
            region_name=resolved_settings.aws_region,
            table=dynamo_table,
        )

    return LocalGoogleOAuthStateRepository(local_file_path or resolved_settings.local_google_oauth_states_file)


def create_encryption_service(settings: Settings | None = None) -> EncryptionService:
    return EncryptionService(settings or get_settings())
