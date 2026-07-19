import io
import json
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

from app.account_artifacts import LocalAccountArtifactStore
from app.account_data_inventory import AccountDataInventory, AccountDataStore
from app.account_deletion_service import AccountDeletionService
from app.account_export_service import AccountExportService, ExportAuthenticationRequired, ExportExpired
from app.account_inventory_factory import create_account_data_inventory
from app.account_models import AccountOperationStatus, AccountState
from app.account_operations_repository import LocalAccountOperationsRepository
from app.reconciliation_repository import LocalReconciliationRepository
from app.reconciliation_service import ReconciliationService


NOW = datetime(2026, 7, 18, 14, 0, tzinfo=timezone.utc)


class MemoryStore:
    def __init__(self, name, rows):
        self.name = name
        self.rows = rows
        self.fail_once = False
        self.export_fail_once = False

    def export(self, user_id, include_protected):
        if self.export_fail_once:
            self.export_fail_once = False
            raise RuntimeError("private export failure")
        values = [dict(row) for row in self.rows if row["user_id"] == user_id]
        for value in values:
            if not include_protected:
                value.pop("protected_details", None)
        return values

    def delete(self, user_id, limit):
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("private storage failure")
        targets = [row for row in self.rows if row["user_id"] == user_id][:limit]
        target_ids = {id(row) for row in targets}
        self.rows = [row for row in self.rows if id(row) not in target_ids]
        return len(targets)

    def count(self, user_id, limit):
        return min(limit, sum(1 for row in self.rows if row["user_id"] == user_id))


def make_inventory(*memory_stores):
    return AccountDataInventory(
        [
            AccountDataStore(
                name=store.name,
                ownership_key="user_id",
                pagination="user partition, bounded batches",
                export_behavior="portable JSON; secrets removed",
                deletion_behavior="idempotent user-partition delete",
                retention_exception=None,
                external_cleanup="S3 object delete" if store.name == "documents" else None,
                export_reader=store.export,
                delete_action=store.delete,
                count_reader=store.count,
                deletion_order=index,
            )
            for index, store in enumerate(memory_stores)
        ]
    )


def make_dependencies(tmp_path, stores):
    operations = LocalAccountOperationsRepository(tmp_path / "operations.json")
    reconciliation_repo = LocalReconciliationRepository(tmp_path / "reconciliation.json")
    reconciliation = ReconciliationService(reconciliation_repo)
    artifacts = LocalAccountArtifactStore(tmp_path / "artifacts")
    inventory = make_inventory(*stores)
    return inventory, operations, reconciliation, artifacts


def read_archive(artifacts, artifact_key):
    return zipfile.ZipFile(io.BytesIO(artifacts.read(artifact_key)))


def test_central_inventory_registers_every_phase13_store():
    from unittest.mock import Mock

    inventory = create_account_data_inventory(
        records=Mock(),
        reminders=Mock(),
        history=Mock(),
        attachments=Mock(),
        relationships=Mock(),
        search=Mock(),
        saved_views=Mock(),
        preferences=Mock(),
        push=Mock(),
        google_connections=Mock(),
        google_oauth_states=Mock(),
        reconciliation=Mock(),
        encryption=Mock(),
        document_storage=Mock(),
        account_operations=Mock(),
        account_artifacts=Mock(),
    )

    assert {item["name"] for item in inventory.describe()} == {
        "export_artifacts",
        "account_operation_control",
        "push_subscriptions",
        "google_calendar_connection",
        "responsibility_history",
        "relationships",
        "document_objects",
        "document_metadata",
        "search_projections",
        "saved_views",
        "preferences",
        "reminders",
        "records",
        "google_oauth_states",
        "reconciliation_issues",
    }


def test_export_artifact_inventory_deletes_orphans_by_owner_prefix(tmp_path):
    from unittest.mock import Mock

    artifacts = LocalAccountArtifactStore(tmp_path / "artifacts")
    orphan_key, _ = artifacts.put("user-a", "orphan-operation", b"private", expires_in_seconds=60)
    other_key, _ = artifacts.put("user-b", "other-operation", b"other", expires_in_seconds=60)
    inventory = create_account_data_inventory(
        records=Mock(),
        reminders=Mock(),
        history=Mock(),
        attachments=Mock(),
        relationships=Mock(),
        search=Mock(),
        saved_views=Mock(),
        preferences=Mock(),
        push=Mock(),
        google_connections=Mock(),
        google_oauth_states=Mock(),
        reconciliation=Mock(),
        encryption=Mock(),
        document_storage=Mock(),
        account_operations=Mock(),
        account_artifacts=artifacts,
    )
    store = next(item for item in inventory.stores if item.name == "export_artifacts")

    assert store.count_reader("user-a", 10) == 1
    assert store.delete_action("user-a", 10) == 1
    assert store.count_reader("user-a", 10) == 0
    with pytest.raises(FileNotFoundError):
        artifacts.read(orphan_key)
    assert artifacts.read(other_key) == b"other"


def test_export_includes_registered_data_and_excludes_secrets_and_protected_plaintext_by_default(tmp_path):
    records = MemoryStore(
        "records",
        [
            {
                "user_id": "user-a",
                "id": "record-1",
                "title": "Passport",
                "protected_details": {"document_number": "secret-number"},
                "protected_ciphertext": "ciphertext",
            },
            {"user_id": "user-b", "id": "other", "title": "Other user"},
        ],
    )
    integrations = MemoryStore(
        "integrations",
        [{"user_id": "user-a", "provider": "google", "access_token": "token", "refresh_token": "refresh"}],
    )
    inventory, operations, _, artifacts = make_dependencies(tmp_path, [records, integrations])
    service = AccountExportService(inventory, operations, artifacts)

    operation, created = service.request_export("user-a", now=NOW)
    duplicate, duplicate_created = service.request_export("user-a", now=NOW)
    complete = service.process_export("user-a", operation.operation_id, now=NOW)

    assert created is True
    assert duplicate_created is False
    assert duplicate.operation_id == operation.operation_id
    assert complete.status == AccountOperationStatus.COMPLETE
    with read_archive(artifacts, complete.artifact_key) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        exported_records = json.loads(archive.read("data/records.json"))
        exported_integrations = json.loads(archive.read("data/integrations.json"))
    assert manifest["stores"] == {"records": 1, "integrations": 1}
    assert manifest["include_protected_details"] is False
    assert exported_records == [{"id": "record-1", "title": "Passport"}]
    assert exported_integrations == [{"provider": "google"}]


def test_failed_export_retry_reuses_the_same_bounded_job(tmp_path):
    records = MemoryStore("records", [{"user_id": "user-a", "id": "record-1"}])
    records.export_fail_once = True
    inventory, operations, _, artifacts = make_dependencies(tmp_path, [records])
    service = AccountExportService(inventory, operations, artifacts)
    operation, _ = service.request_export("user-a", now=NOW)

    failed = service.process_export("user-a", operation.operation_id, now=NOW)
    retried, should_dispatch = service.request_export("user-a", now=NOW + timedelta(minutes=1))
    complete = service.process_export("user-a", retried.operation_id, now=NOW + timedelta(minutes=1))

    assert failed.status == AccountOperationStatus.FAILED
    assert should_dispatch is True
    assert retried.operation_id == operation.operation_id
    assert complete.status == AccountOperationStatus.COMPLETE
    assert len(operations.list_operations("user-a")) == 1


def test_protected_export_requires_explicit_recent_authentication(tmp_path):
    records = MemoryStore(
        "records",
        [{"user_id": "user-a", "id": "record-1", "protected_details": {"document_number": "secret"}}],
    )
    inventory, operations, _, artifacts = make_dependencies(tmp_path, [records])
    service = AccountExportService(inventory, operations, artifacts)

    with pytest.raises(ExportAuthenticationRequired):
        service.request_export("user-a", include_protected_details=True, now=NOW)

    operation, _ = service.request_export(
        "user-a", include_protected_details=True, recently_authenticated=True, now=NOW
    )
    complete = service.process_export("user-a", operation.operation_id, now=NOW)
    with read_archive(artifacts, complete.artifact_key) as archive:
        records_export = json.loads(archive.read("data/records.json"))
    assert records_export[0]["protected_details"] == {"document_number": "secret"}
    assert complete.expires_at == NOW + timedelta(minutes=15)


def test_cross_user_and_expired_export_access_are_rejected_and_artifact_deleted(tmp_path):
    records = MemoryStore("records", [{"user_id": "user-a", "id": "record-1"}])
    inventory, operations, _, artifacts = make_dependencies(tmp_path, [records])
    service = AccountExportService(inventory, operations, artifacts)
    operation, _ = service.request_export("user-a", now=NOW)
    complete = service.process_export("user-a", operation.operation_id, now=NOW)

    with pytest.raises(KeyError):
        service.get_download_url("user-b", operation.operation_id, now=NOW)
    with pytest.raises(ExportExpired):
        service.get_download_url("user-a", operation.operation_id, now=NOW + timedelta(hours=2))
    with pytest.raises(FileNotFoundError):
        artifacts.read(complete.artifact_key)


def test_deletion_uses_every_registered_store_verifies_zero_then_cleans_identity(tmp_path):
    records = MemoryStore("records", [{"user_id": "user-a", "id": "record-1"}, {"user_id": "user-b", "id": "other"}])
    documents = MemoryStore("documents", [{"user_id": "user-a", "id": "document-1"}])
    relationships = MemoryStore("relationships", [{"user_id": "user-a", "id": "link-1"}])
    inventory, operations, reconciliation, _ = make_dependencies(tmp_path, [relationships, documents, records])
    identity_calls = []

    def clean_identity(user_id):
        assert all(store.count(user_id, 100) == 0 for store in [records, documents, relationships])
        identity_calls.append(user_id)

    service = AccountDeletionService(inventory, operations, reconciliation, clean_identity)
    operation, created = service.request_deletion("user-a", now=NOW)
    duplicate, duplicate_created = service.request_deletion("user-a", now=NOW)

    assert created is True
    assert duplicate_created is False
    assert duplicate.operation_id == operation.operation_id
    assert operations.get_lifecycle("user-a").state == AccountState.DELETION_REQUESTED
    result = service.process_deletion("user-a", operation.operation_id, now=NOW)

    assert result.status == AccountOperationStatus.COMPLETE
    assert identity_calls == ["user-a"]
    assert records.count("user-b", 100) == 1
    assert operations.get_lifecycle("user-a").state == AccountState.ACTIVE
    assert operations.has_deletion_receipt(operation.operation_id) is True
    replay = service.process_deletion("user-a", operation.operation_id, now=NOW + timedelta(minutes=1))
    assert replay.status == AccountOperationStatus.COMPLETE
    assert identity_calls == ["user-a"]


def test_partial_deletion_failure_is_retryable_and_never_reports_complete(tmp_path):
    documents = MemoryStore("documents", [{"user_id": "user-a", "id": "document-1"}])
    documents.fail_once = True
    inventory, operations, reconciliation, _ = make_dependencies(tmp_path, [documents])
    service = AccountDeletionService(inventory, operations, reconciliation, lambda _user_id: None)
    operation, _ = service.request_deletion("user-a", now=NOW)

    failed = service.process_deletion("user-a", operation.operation_id, now=NOW)

    assert failed.status == AccountOperationStatus.FAILED
    assert operations.get_lifecycle("user-a").state == AccountState.DELETION_REQUIRES_ATTENTION
    assert service.verify("user-a", operation.operation_id, now=NOW).counts == {"documents": 1}
    assert len(reconciliation.repository.list_by_user("user-a")) == 1

    retried, should_dispatch = service.request_deletion("user-a", now=NOW + timedelta(minutes=1))
    assert should_dispatch is True
    assert retried.operation_id == operation.operation_id
    recovered = service.process_deletion("user-a", retried.operation_id, now=NOW + timedelta(minutes=1))
    assert recovered.status == AccountOperationStatus.COMPLETE


def test_verification_contains_only_registered_store_names_and_safe_counts(tmp_path):
    sensitive = MemoryStore(
        "records",
        [{"user_id": "user-a", "title": "private title", "notes": "private notes"}],
    )
    inventory, operations, reconciliation, _ = make_dependencies(tmp_path, [sensitive])
    service = AccountDeletionService(inventory, operations, reconciliation, lambda _user_id: None)
    operation, _ = service.request_deletion("user-a", now=NOW)

    verification = service.verify("user-a", operation.operation_id, now=NOW)

    assert verification.model_dump(mode="json")["counts"] == {"records": 1}
    assert "private" not in verification.model_dump_json()
