from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.account_artifacts import LocalAccountArtifactStore
from app.account_data_inventory import AccountDataInventory, AccountDataStore
from app.account_deletion_service import AccountDeletionService
from app.account_export_service import AccountExportService
from app.account_models import AccountLifecycle, AccountState
from app.account_operations_repository import LocalAccountOperationsRepository
from app.auth import UserContext, get_current_user
from app.reconciliation_repository import LocalReconciliationRepository
from app.reconciliation_service import ReconciliationService
from app.routers.account import (
    get_account_deletion_service,
    get_account_dispatcher,
    get_account_export_service,
    get_account_operations_repository,
)


NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def account_client(tmp_path, monkeypatch):
    rows = [{"user_id": "local-dev-user", "id": "record-1"}]

    def export(user_id, include_protected):
        return [
            {
                **row,
                **({"protected_details": {"secret": "value"}} if include_protected else {}),
            }
            for row in rows
            if row["user_id"] == user_id
        ]

    def delete(user_id, limit):
        targets = [row for row in rows if row["user_id"] == user_id][:limit]
        for row in targets:
            rows.remove(row)
        return len(targets)

    inventory = AccountDataInventory(
        [
            AccountDataStore(
                name="records",
                ownership_key="user_id",
                pagination="bounded",
                export_behavior="JSON",
                deletion_behavior="delete",
                retention_exception=None,
                external_cleanup=None,
                export_reader=export,
                delete_action=delete,
                count_reader=lambda user_id, limit: min(limit, len([row for row in rows if row["user_id"] == user_id])),
                deletion_order=1,
            )
        ]
    )
    operations = LocalAccountOperationsRepository(tmp_path / "operations.json")
    reconciliation = ReconciliationService(LocalReconciliationRepository(tmp_path / "reconciliation.json"))
    artifacts = LocalAccountArtifactStore(tmp_path / "artifacts")
    export_service = AccountExportService(inventory, operations, artifacts)
    deletion_service = AccountDeletionService(inventory, operations, reconciliation, lambda _user_id: None)

    def dispatch(user_id, operation_id, operation_type):
        if operation_type == "export":
            return export_service.process_export(user_id, operation_id, now=NOW)
        return deletion_service.process_deletion(user_id, operation_id, now=NOW)

    main_module.app.dependency_overrides[get_current_user] = lambda: UserContext(
        user_id="local-dev-user", authenticated_at=NOW
    )
    main_module.app.dependency_overrides[get_account_operations_repository] = lambda: operations
    main_module.app.dependency_overrides[get_account_export_service] = lambda: export_service
    main_module.app.dependency_overrides[get_account_deletion_service] = lambda: deletion_service
    main_module.app.dependency_overrides[get_account_dispatcher] = lambda: dispatch
    monkeypatch.setattr(main_module, "get_account_operations_repository", lambda: operations)
    with TestClient(main_module.app) as client:
        yield client, operations, artifacts
    main_module.app.dependency_overrides.clear()


def test_export_route_defaults_to_no_protected_plaintext_and_is_no_store(account_client):
    client, _operations, _artifacts = account_client

    response = client.post("/account/exports", json={})

    assert response.status_code == 202
    assert response.headers["cache-control"] == "no-store, private"
    assert response.json()["status"] == "complete"
    assert response.json()["include_protected_details"] is False
    status_response = client.get("/account/status")
    assert status_response.json()["current_operation"]["operation_id"] == response.json()["operation_id"]
    assert status_response.json()["current_operation"]["status"] == "complete"


def test_protected_export_requires_deliberate_confirmation(account_client):
    client, _operations, _artifacts = account_client

    response = client.post(
        "/account/exports",
        json={"include_protected_details": True, "confirm_sensitive_export": False},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "protected_export_confirmation_required"


def test_cross_user_export_status_is_not_disclosed(account_client):
    client, _operations, _artifacts = account_client
    operation_id = client.post("/account/exports", json={}).json()["operation_id"]
    main_module.app.dependency_overrides[get_current_user] = lambda: UserContext(user_id="other-user")

    response = client.get(f"/account/exports/{operation_id}")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "account_operation_not_found"


def test_deletion_requires_typed_confirmation_and_reports_complete_only_after_verification(account_client):
    client, operations, _artifacts = account_client

    rejected = client.post("/account/deletion", json={"confirmation": "delete"})
    accepted = client.post("/account/deletion", json={"confirmation": "DELETE MY ACCOUNT"})

    assert rejected.status_code == 422
    assert accepted.status_code == 202
    assert accepted.json()["status"] == "complete"
    assert operations.get_lifecycle("local-dev-user").state == AccountState.ACTIVE


def test_new_writes_are_blocked_after_deletion_begins(account_client):
    client, operations, _artifacts = account_client
    operations.save_lifecycle(
        AccountLifecycle(
            user_id="local-dev-user",
            state=AccountState.DELETING,
            current_operation_id="deletion-1",
            updated_at=NOW,
        )
    )

    response = client.post(
        "/records",
        json={"record_type": "general", "title": "Should not be created"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "deletion_in_progress"

    read_response = client.get("/records")
    assert read_response.status_code == 409
    assert read_response.json()["detail"]["code"] == "account_unavailable"
    assert client.get("/account/status").status_code == 200
