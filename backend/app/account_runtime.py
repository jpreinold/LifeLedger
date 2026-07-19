from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.account_artifacts import LocalAccountArtifactStore, S3AccountArtifactStore
from app.account_deletion_service import AccountDeletionService
from app.account_export_service import AccountExportService
from app.account_inventory_factory import create_account_data_inventory
from app.config import COGNITO_AUTH_MODE, DYNAMODB_PERSISTENCE, Settings, get_settings
from app.reconciliation_service import ReconciliationService
from app.repository_factory import (
    create_account_operations_repository,
    create_assistant_repository,
    create_encryption_service,
    create_google_calendar_connection_repository,
    create_google_oauth_state_repository,
    create_linked_item_repository,
    create_preferences_repository,
    create_push_subscription_repository,
    create_reconciliation_repository,
    create_record_attachment_repository,
    create_record_repository,
    create_repository,
    create_responsibility_history_repository,
    create_saved_search_view_repository,
    create_search_index_repository,
)
from app.attachments import create_document_storage_service
from app.google_calendar_service import GoogleCalendarService
from app.integration_cleanup_service import IntegrationCleanupService


@lru_cache(maxsize=1)
def get_account_operations_repository():
    return create_account_operations_repository(get_settings())


@lru_cache(maxsize=1)
def get_reconciliation_service() -> ReconciliationService:
    return ReconciliationService(create_reconciliation_repository(get_settings()))


@lru_cache(maxsize=1)
def get_account_inventory():
    settings = get_settings()
    reminder_repository = create_repository(settings)
    google_connections = create_google_calendar_connection_repository(settings)
    oauth_states = create_google_oauth_state_repository(settings)
    return create_account_data_inventory(
        records=create_record_repository(settings),
        reminders=reminder_repository,
        history=create_responsibility_history_repository(settings),
        attachments=create_record_attachment_repository(settings),
        relationships=create_linked_item_repository(settings),
        search=create_search_index_repository(settings),
        saved_views=create_saved_search_view_repository(settings),
        preferences=create_preferences_repository(settings),
        push=create_push_subscription_repository(settings),
        google_connections=google_connections,
        google_oauth_states=oauth_states,
        reconciliation=create_reconciliation_repository(settings),
        encryption=create_encryption_service(settings),
        document_storage=create_document_storage_service(settings),
        integration_cleanup=IntegrationCleanupService(
            reminder_repository,
            google_connections,
            oauth_states,
            GoogleCalendarService(settings),
        ),
        account_operations=get_account_operations_repository(),
        account_artifacts=get_account_artifact_store(),
        assistant=create_assistant_repository(settings),
    )


@lru_cache(maxsize=1)
def get_account_artifact_store():
    settings = get_settings()
    if settings.persistence_mode == DYNAMODB_PERSISTENCE:
        return S3AccountArtifactStore(
            settings.account_exports_bucket,
            settings.documents_kms_key_arn,
            settings.aws_region,
        )
    root = Path(settings.local_account_operations_file).parent / "account-exports"
    return LocalAccountArtifactStore(root)


@lru_cache(maxsize=1)
def get_account_export_service() -> AccountExportService:
    return AccountExportService(
        get_account_inventory(),
        get_account_operations_repository(),
        get_account_artifact_store(),
    )


@lru_cache(maxsize=1)
def get_account_deletion_service() -> AccountDeletionService:
    return AccountDeletionService(
        get_account_inventory(),
        get_account_operations_repository(),
        get_reconciliation_service(),
        CognitoIdentityCleaner(get_settings()),
    )


def dispatch_account_operation(user_id: str, operation_id: str, operation_type: str):
    settings = get_settings()
    if settings.account_operations_queue_url:
        import boto3

        boto3.client("sqs", region_name=settings.aws_region).send_message(
            QueueUrl=settings.account_operations_queue_url,
            MessageBody=json.dumps(
                {"user_id": user_id, "operation_id": operation_id, "operation_type": operation_type}
            ),
        )
        return
    if settings.app_env == "production":
        raise RuntimeError("Account operations queue is not configured.")
    if operation_type == "export":
        return get_account_export_service().process_export(user_id, operation_id)
    return get_account_deletion_service().process_deletion(user_id, operation_id)


class CognitoIdentityCleaner:
    def __init__(self, settings: Settings):
        self.settings = settings

    def __call__(self, user_id: str) -> None:
        if self.settings.auth_mode != COGNITO_AUTH_MODE:
            return
        import boto3

        client = boto3.client("cognito-idp", region_name=self.settings.aws_region)
        matches = client.list_users(
            UserPoolId=self.settings.cognito_user_pool_id,
            Filter=f'sub = "{user_id}"',
            Limit=2,
        ).get("Users", [])
        if not matches:
            return
        client.admin_delete_user(
            UserPoolId=self.settings.cognito_user_pool_id,
            Username=matches[0]["Username"],
        )
