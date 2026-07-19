from __future__ import annotations

from typing import Any

from app.account_data_inventory import AccountDataInventory, AccountDataStore
from app.attachments_repository import RecordAttachmentRepository
from app.capture_repository import AssistantRepository
from app.encryption_service import EncryptedPayload, EncryptionService, record_encryption_context
from app.google_calendar_repository import GoogleCalendarConnectionRepository, GoogleOAuthStateRepository
from app.linked_items_repository import LinkedItemRepository
from app.preferences_repository import PreferencesRepository
from app.push_repository import PushSubscriptionRepository
from app.records_repository import RecordRepository
from app.reconciliation_repository import ReconciliationRepository
from app.repository import ReminderRepository
from app.responsibility_history_repository import ResponsibilityHistoryRepository
from app.search_repository import SavedSearchViewRepository, SearchIndexRepository
from app.schemas import AttachmentStatus


def create_account_data_inventory(
    *,
    records: RecordRepository,
    reminders: ReminderRepository,
    history: ResponsibilityHistoryRepository,
    attachments: RecordAttachmentRepository,
    relationships: LinkedItemRepository,
    search: SearchIndexRepository,
    saved_views: SavedSearchViewRepository,
    preferences: PreferencesRepository,
    push: PushSubscriptionRepository,
    google_connections: GoogleCalendarConnectionRepository,
    google_oauth_states: GoogleOAuthStateRepository,
    reconciliation: ReconciliationRepository,
    encryption: EncryptionService,
    document_storage,
    integration_cleanup=None,
    account_operations=None,
    account_artifacts=None,
    assistant: AssistantRepository | None = None,
) -> AccountDataInventory:
    def export_records(user_id: str, include_protected: bool) -> list[dict[str, Any]]:
        result = []
        for record in records.list_records(user_id, include_archived=True):
            item = record.model_dump(mode="json")
            for key in (
                "protected_ciphertext",
                "protected_encrypted_data_key",
                "protected_nonce",
                "protected_key_arn",
            ):
                item.pop(key, None)
            item["protected_detail_metadata"] = {
                "has_protected_details": bool(record.protected_ciphertext),
                "field_names": record.protected_field_names,
                "updated_at": record.protected_updated_at.isoformat() if record.protected_updated_at else None,
            }
            if include_protected and record.protected_ciphertext and record.protected_encrypted_data_key and record.protected_nonce:
                item["protected_details"] = encryption.decrypt_json(
                    EncryptedPayload(
                        ciphertext=record.protected_ciphertext,
                        encrypted_data_key=record.protected_encrypted_data_key,
                        nonce=record.protected_nonce,
                        encryption_version=record.protected_encryption_version or 0,
                        key_arn=record.protected_key_arn,
                    ),
                    record_encryption_context(record.user_id, record.id),
                )
            result.append(item)
        return result

    def export_documents(user_id: str, _include_protected: bool) -> list[dict[str, Any]]:
        result = []
        for attachment in attachments.list_for_user(user_id):
            item = attachment.model_dump(mode="json")
            for key in ("owner_hash", "quarantine_object_key", "clean_object_key", "encryption_key_arn"):
                item.pop(key, None)
            result.append(item)
        return result

    def export_document_files(user_id: str) -> list[tuple[str, bytes]]:
        files = []
        for attachment in attachments.list_for_user(user_id):
            if attachment.status != AttachmentStatus.AVAILABLE or not attachment.clean_object_key:
                continue
            extension = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}.get(
                attachment.content_type, ".bin"
            )
            files.append(
                (
                    f"{attachment.record_id}/{attachment.attachment_id}{extension}",
                    document_storage.read_clean_object(attachment.clean_object_key),
                )
            )
        return files

    def delete_document_objects(user_id: str, limit: int) -> int:
        if hasattr(document_storage, "delete_user_objects"):
            return document_storage.delete_user_objects(user_id, limit=limit)
        targets = [
            item
            for item in attachments.list_for_user(user_id, limit=limit)
            if item.quarantine_object_key or item.clean_object_key
        ][:limit]
        for attachment in targets:
            if attachment.quarantine_object_key:
                document_storage.delete_quarantine_object(attachment.quarantine_object_key)
            if attachment.clean_object_key:
                document_storage.delete_clean_object(attachment.clean_object_key)
            attachments.update_attachment(
                attachment.model_copy(update={"quarantine_object_key": None, "clean_object_key": None})
            )
        return len(targets)

    def count_document_objects(user_id: str, limit: int) -> int:
        if hasattr(document_storage, "list_user_objects"):
            return len(document_storage.list_user_objects(user_id, limit=limit))
        return len(
            [
                item
                for item in attachments.list_for_user(user_id, limit=limit)
                if item.quarantine_object_key or item.clean_object_key
            ][:limit]
        )

    def delete_document_metadata(user_id: str, limit: int) -> int:
        targets = attachments.list_for_user(user_id, limit=limit)
        for attachment in targets:
            attachments.delete_attachment_metadata(user_id, attachment.record_id, attachment.attachment_id)
        return len(targets)

    def delete_reminders(user_id: str, limit: int) -> int:
        targets = reminders.list_reminders(user_id, limit=limit)
        for reminder in targets:
            reminders.delete_reminder(user_id, reminder.id)
        return len(targets)

    def delete_records(user_id: str, limit: int) -> int:
        targets = records.list_records(user_id, include_archived=True, limit=limit)
        for record in targets:
            records.delete_record(user_id, record.id)
        return len(targets)

    def count_search(user_id: str, limit: int) -> int:
        return min(
            limit,
            len(search.list_projection_ids_for_user(user_id, limit)) + len(search.list_sync_failures(user_id, limit)),
        )

    def model_rows(values) -> list[dict[str, Any]]:
        return [value.model_dump(mode="json") for value in values]

    stores = []
    if assistant is not None:
        assistant_kinds = (
            ("captures", "capture", 5),
            ("action_proposals", "proposal", 6),
            ("clarifications", "clarification", 7),
            ("ai_usage", "usage", 8),
            ("ai_settings", "settings", 9),
        )
        for store_name, kind, order in assistant_kinds:
            stores.append(
                _store(
                    store_name,
                    "user_id",
                    order,
                    lambda user_id, _protected, entity_kind=kind: assistant.list_entity_rows(
                        user_id, entity_kind, limit=None
                    ),
                    lambda user_id, limit, entity_kind=kind: assistant.delete_entity_rows(
                        user_id, entity_kind, limit=limit
                    ),
                    lambda user_id, limit, entity_kind=kind: assistant.count_entity_rows(
                        user_id, entity_kind, limit=limit
                    ),
                    retention=(
                        "Resolved temporary state may use bounded TTL; unresolved captures are retained."
                        if kind in {"proposal", "clarification"}
                        else None
                    ),
                )
            )
    if account_operations is not None and account_artifacts is not None:
        def delete_export_artifacts(user_id: str, limit: int) -> int:
            return account_artifacts.delete_for_user(user_id, limit=limit)

        stores.extend(
            [
                _store(
                    "export_artifacts",
                    "hashed user prefix and user-scoped job",
                    -10,
                    lambda _user_id, _protected: [],
                    delete_export_artifacts,
                    lambda user_id, limit: len(account_artifacts.list_for_user(user_id, limit=limit)),
                    export_enabled=False,
                    external="Private KMS-encrypted S3 export objects",
                ),
                _store(
                    "account_operation_control",
                    "user_id",
                    100,
                    lambda user_id, _protected: [
                        {
                            "operation_id": item.operation_id,
                            "operation_type": item.operation_type,
                            "status": item.status,
                            "created_at": item.created_at,
                            "updated_at": item.updated_at,
                        }
                        for item in account_operations.list_operations(user_id)
                        if item.operation_type.value != "export"
                    ],
                    lambda _user_id, _limit: 0,
                    lambda _user_id, _limit: 0,
                    retention="Control rows remain only while deletion is resumable and are removed after identity cleanup.",
                ),
            ]
        )
    stores.extend([
        _store(
            "push_subscriptions",
            "user_id",
            0,
            lambda user_id, _protected: [
                {
                    "subscription_id": item.subscription_id,
                    "user_agent": item.user_agent,
                    "created_at": item.created_at,
                    "updated_at": item.updated_at,
                    "disabled_at": item.disabled_at,
                }
                for item in push.list_subscriptions(user_id, include_disabled=True)
            ],
            push.delete_for_user,
            lambda user_id, limit: min(limit, len(push.list_subscriptions(user_id, include_disabled=True))),
            external="Web Push subscription endpoint",
        ),
        _store(
            "google_calendar_connection",
            "user_id",
            1,
            lambda user_id, _protected: [
                {
                    "provider": item.provider,
                    "google_account_email": item.google_account_email,
                    "calendar_id": item.calendar_id,
                    "calendar_label": item.calendar_label,
                    "scopes": item.scopes,
                    "connected_at": item.connected_at,
                    "updated_at": item.updated_at,
                    "disconnected_at": item.disconnected_at,
                    "status": item.status,
                }
                for item in [google_connections.get_connection(user_id)]
                if item is not None
            ],
            lambda user_id, limit: (
                integration_cleanup.cleanup_google_calendar(user_id, limit=limit)
                if integration_cleanup is not None
                else int(google_connections.delete_connection(user_id))
            ),
            lambda user_id, _limit: int(google_connections.get_connection(user_id) is not None),
            external="Google token revocation and mapped Calendar event cleanup",
        ),
        _store(
            "responsibility_history",
            "user_id",
            10,
            lambda user_id, _protected: model_rows(history.list_for_user(user_id, limit=None)),
            history.delete_for_user,
            lambda user_id, limit: len(history.list_for_user(user_id, limit=limit)),
        ),
        _store(
            "relationships",
            "user_id",
            20,
            lambda user_id, _protected: model_rows(relationships.list_for_user(user_id, limit=None)),
            relationships.delete_for_user,
            lambda user_id, limit: len(relationships.list_for_user(user_id, limit=limit)),
        ),
        _store(
            "document_objects",
            "hashed user prefix",
            30,
            lambda _user_id, _protected: [],
            delete_document_objects,
            count_document_objects,
            export_enabled=False,
            external="S3 quarantine and promoted clean objects",
        ),
        AccountDataStore(
            name="document_metadata",
            ownership_key="user_id",
            pagination="user partition, bounded batches",
            export_behavior="JSON metadata plus clean document archive entries",
            deletion_behavior="delete metadata after S3 object cleanup",
            retention_exception=None,
            external_cleanup="Clean document bytes are copied into the export archive",
            export_reader=export_documents,
            binary_export_reader=export_document_files,
            delete_action=delete_document_metadata,
            count_reader=lambda user_id, limit: len(attachments.list_for_user(user_id, limit=limit)),
            deletion_order=31,
        ),
        _store(
            "search_projections",
            "user_id",
            40,
            lambda _user_id, _protected: [],
            search.delete_for_user,
            count_search,
            export_enabled=False,
        ),
        _store(
            "saved_views",
            "user_id",
            45,
            lambda user_id, _protected: model_rows(saved_views.list_views(user_id)),
            saved_views.delete_for_user,
            lambda user_id, limit: len(saved_views.list_views(user_id)[:limit]),
        ),
        _store(
            "preferences",
            "user_id",
            50,
            lambda user_id, _protected: model_rows(
                [item for item in [preferences.get_preferences(user_id)] if item is not None]
            ),
            lambda user_id, _limit: int(preferences.delete_preferences(user_id)),
            lambda user_id, _limit: int(preferences.get_preferences(user_id) is not None),
        ),
        _store(
            "reminders",
            "user_id",
            60,
            lambda user_id, _protected: model_rows(reminders.list_reminders(user_id)),
            delete_reminders,
            lambda user_id, limit: len(reminders.list_reminders(user_id, limit=limit)),
        ),
        _store(
            "records",
            "user_id",
            70,
            export_records,
            delete_records,
            lambda user_id, limit: len(records.list_records(user_id, include_archived=True, limit=limit)),
        ),
        _store(
            "google_oauth_states",
            "user_id GSI",
            80,
            lambda _user_id, _protected: [],
            google_oauth_states.delete_for_user,
            lambda user_id, limit: len(google_oauth_states.list_for_user(user_id, limit=limit)),
            export_enabled=False,
        ),
        _store(
            "reconciliation_issues",
            "user_id GSI",
            90,
            lambda _user_id, _protected: [],
            reconciliation.delete_for_user,
            lambda user_id, limit: len(reconciliation.list_by_user(user_id, limit=limit)),
            export_enabled=False,
            retention="Resolved operational issues have bounded TTL; unresolved deletion work remains until cleanup.",
        ),
    ])
    return AccountDataInventory(stores)


def _store(
    name,
    ownership_key,
    order,
    exporter,
    deleter,
    counter,
    *,
    export_enabled=True,
    external=None,
    retention=None,
):
    return AccountDataStore(
        name=name,
        ownership_key=ownership_key,
        pagination="user partition or user GSI; bounded batches",
        export_behavior="portable JSON" if export_enabled else "not exported; derived or operational state",
        deletion_behavior="idempotent bounded user-scoped cleanup",
        retention_exception=retention,
        external_cleanup=external,
        export_reader=exporter,
        delete_action=deleter,
        count_reader=counter,
        deletion_order=order,
        export_enabled=export_enabled,
    )
