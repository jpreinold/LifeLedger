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
from app.linked_items_repository import (
    DynamoLinkedItemRepository,
    LinkedItemRepository,
    LocalLinkedItemRepository,
)
from app.preferences_repository import DynamoPreferencesRepository, LocalPreferencesRepository, PreferencesRepository
from app.push_repository import DynamoPushSubscriptionRepository, LocalPushSubscriptionRepository, PushSubscriptionRepository
from app.records_repository import LocalRecordRepository, RecordRepository
from app.search_repository import (
    DynamoSavedSearchViewRepository,
    DynamoSearchIndexRepository,
    LocalSavedSearchViewRepository,
    LocalSearchIndexRepository,
    SavedSearchViewRepository,
    SearchIndexRepository,
)
from app.repository import LocalReminderRepository, ReminderRepository
from app.responsibility_history_repository import (
    DynamoResponsibilityHistoryRepository,
    LocalResponsibilityHistoryRepository,
    ResponsibilityHistoryRepository,
)
from app.reconciliation_repository import (
    DynamoReconciliationRepository,
    LocalReconciliationRepository,
    ReconciliationRepository,
)
from app.account_operations_repository import (
    AccountOperationsRepository,
    DynamoAccountOperationsRepository,
    LocalAccountOperationsRepository,
)
from app.capture_repository import AssistantRepository, DynamoAssistantRepository, LocalAssistantRepository


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


def create_responsibility_history_repository(
    settings: Settings | None = None,
    *,
    local_file_path: str | Path | None = None,
    dynamo_table: Any | None = None,
    dynamo_client: Any | None = None,
) -> ResponsibilityHistoryRepository:
    resolved_settings = settings or get_settings()
    if resolved_settings.persistence_mode == DYNAMODB_PERSISTENCE:
        return DynamoResponsibilityHistoryRepository(
            table_name=resolved_settings.responsibility_history_table_name,
            reminder_table_name=resolved_settings.reminders_table_name,
            region_name=resolved_settings.aws_region,
            table=dynamo_table,
            client=dynamo_client,
        )
    return LocalResponsibilityHistoryRepository(
        local_file_path or resolved_settings.local_responsibility_history_file
    )


def create_reconciliation_repository(
    settings: Settings | None = None,
    *,
    local_file_path: str | Path | None = None,
    dynamo_table: Any | None = None,
) -> ReconciliationRepository:
    resolved_settings = settings or get_settings()
    if resolved_settings.persistence_mode == DYNAMODB_PERSISTENCE:
        return DynamoReconciliationRepository(
            table_name=resolved_settings.reconciliation_table_name,
            region_name=resolved_settings.aws_region,
            table=dynamo_table,
        )
    return LocalReconciliationRepository(local_file_path or resolved_settings.local_reconciliation_file)


def create_account_operations_repository(
    settings: Settings | None = None,
    *,
    local_file_path: str | Path | None = None,
    dynamo_table: Any | None = None,
) -> AccountOperationsRepository:
    resolved_settings = settings or get_settings()
    if resolved_settings.persistence_mode == DYNAMODB_PERSISTENCE:
        return DynamoAccountOperationsRepository(
            table_name=resolved_settings.account_operations_table_name,
            region_name=resolved_settings.aws_region,
            table=dynamo_table,
        )
    return LocalAccountOperationsRepository(local_file_path or resolved_settings.local_account_operations_file)


def create_assistant_repository(
    settings: Settings | None = None,
    *,
    local_file_path: str | Path | None = None,
    dynamo_table: Any | None = None,
) -> AssistantRepository:
    resolved_settings = settings or get_settings()
    if resolved_settings.persistence_mode == DYNAMODB_PERSISTENCE:
        return DynamoAssistantRepository(
            table_name=resolved_settings.assistant_data_table_name,
            region_name=resolved_settings.aws_region,
            table=dynamo_table,
        )
    return LocalAssistantRepository(local_file_path or resolved_settings.local_assistant_data_file)


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


def create_linked_item_repository(
    settings: Settings | None = None,
    *,
    local_file_path: str | Path | None = None,
    dynamo_table: Any | None = None,
) -> LinkedItemRepository:
    resolved_settings = settings or get_settings()

    if resolved_settings.persistence_mode == DYNAMODB_PERSISTENCE:
        return DynamoLinkedItemRepository(
            table_name=resolved_settings.linked_items_table_name,
            region_name=resolved_settings.aws_region,
            table=dynamo_table,
        )

    return LocalLinkedItemRepository(local_file_path or resolved_settings.local_linked_items_file)


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


def create_search_index_repository(
    settings: Settings | None = None,
    *,
    local_file_path: str | Path | None = None,
    dynamo_table: Any | None = None,
) -> SearchIndexRepository:
    resolved_settings = settings or get_settings()

    if resolved_settings.persistence_mode == DYNAMODB_PERSISTENCE:
        return DynamoSearchIndexRepository(
            table_name=resolved_settings.search_index_table_name,
            region_name=resolved_settings.aws_region,
            table=dynamo_table,
        )

    return LocalSearchIndexRepository(local_file_path or resolved_settings.local_search_index_file)


def create_saved_search_view_repository(
    settings: Settings | None = None,
    *,
    local_file_path: str | Path | None = None,
    dynamo_table: Any | None = None,
) -> SavedSearchViewRepository:
    resolved_settings = settings or get_settings()

    if resolved_settings.persistence_mode == DYNAMODB_PERSISTENCE:
        return DynamoSavedSearchViewRepository(
            table_name=resolved_settings.saved_views_table_name,
            region_name=resolved_settings.aws_region,
            table=dynamo_table,
        )

    return LocalSavedSearchViewRepository(local_file_path or resolved_settings.local_saved_views_file)
