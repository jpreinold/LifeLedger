from __future__ import annotations

import io
import json
import logging
import zipfile
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.account_artifacts import AccountArtifactStore
from app.account_data_inventory import AccountDataInventory
from app.account_models import (
    AccountExportManifest,
    AccountLifecycle,
    AccountOperation,
    AccountOperationStatus,
    AccountOperationType,
    AccountState,
)
from app.account_operations_repository import AccountOperationsRepository


logger = logging.getLogger(__name__)
FORBIDDEN_EXPORT_KEYS = {
    "user_id",
    "access_token",
    "refresh_token",
    "token_ciphertext",
    "token_encrypted_data_key",
    "token_nonce",
    "protected_ciphertext",
    "protected_encrypted_data_key",
    "protected_nonce",
    "protected_key_arn",
    "encryption_key_arn",
    "quarantine_object_key",
    "clean_object_key",
    "signed_url",
    "presigned_url",
    "p256dh",
    "auth",
}


class ExportAuthenticationRequired(ValueError):
    pass


class ExportExpired(ValueError):
    pass


class AccountUnavailable(ValueError):
    pass


class AccountExportService:
    def __init__(
        self,
        inventory: AccountDataInventory,
        operations: AccountOperationsRepository,
        artifacts: AccountArtifactStore,
        *,
        default_expiration_minutes: int = 60,
        protected_expiration_minutes: int = 15,
    ):
        self.inventory = inventory
        self.operations = operations
        self.artifacts = artifacts
        self.default_expiration_minutes = default_expiration_minutes
        self.protected_expiration_minutes = protected_expiration_minutes

    def request_export(
        self,
        user_id: str,
        *,
        include_protected_details: bool = False,
        recently_authenticated: bool = False,
        now: datetime | None = None,
    ) -> tuple[AccountOperation, bool]:
        if include_protected_details and not recently_authenticated:
            raise ExportAuthenticationRequired("Recent authentication is required for protected-detail export.")
        lifecycle = self.operations.get_lifecycle(user_id)
        if lifecycle.state in {
            AccountState.DELETION_REQUESTED,
            AccountState.DELETING,
            AccountState.DELETION_REQUIRES_ATTENTION,
            AccountState.DELETED,
        }:
            raise AccountUnavailable("Account data is unavailable while deletion is in progress.")
        existing = self.operations.find_open_operation(user_id, AccountOperationType.EXPORT)
        if existing:
            if existing.include_protected_details != include_protected_details:
                raise ValueError("An export is already in progress.")
            return existing, False
        requested_at = _utc(now or datetime.now(timezone.utc))
        failed = next(
            (
                item
                for item in self.operations.list_operations(user_id, limit=100)
                if item.operation_type == AccountOperationType.EXPORT
                and item.status == AccountOperationStatus.FAILED
                and item.include_protected_details == include_protected_details
            ),
            None,
        )
        if failed is not None:
            operation = failed.model_copy(
                update={
                    "status": AccountOperationStatus.PENDING,
                    "updated_at": requested_at,
                    "safe_error": None,
                    "artifact_key": None,
                    "artifact_size_bytes": None,
                    "expires_at": None,
                }
            )
            self.operations.save_operation(operation)
        else:
            operation = AccountOperation(
                operation_id=str(uuid4()),
                user_id=user_id,
                operation_type=AccountOperationType.EXPORT,
                status=AccountOperationStatus.PENDING,
                include_protected_details=include_protected_details,
                created_at=requested_at,
                updated_at=requested_at,
            )
            self.operations.create_operation(operation)
        self.operations.save_lifecycle(
            AccountLifecycle(
                user_id=user_id,
                state=AccountState.EXPORT_PENDING,
                current_operation_id=operation.operation_id,
                updated_at=requested_at,
            )
        )
        _log("export_requested", operation)
        return operation, True

    def mark_dispatch_failed(
        self, user_id: str, operation_id: str, *, now: datetime | None = None
    ) -> AccountOperation:
        operation = self._required(user_id, operation_id)
        failed = operation.model_copy(
            update={
                "status": AccountOperationStatus.FAILED,
                "safe_error": "LifeLedger could not start export processing. It can be retried safely.",
                "updated_at": _utc(now or datetime.now(timezone.utc)),
            }
        )
        self.operations.save_operation(failed)
        _log("export_failed", failed, step="dispatch")
        return failed

    def process_export(self, user_id: str, operation_id: str, *, now: datetime | None = None) -> AccountOperation:
        operation = self._required(user_id, operation_id)
        if operation.status == AccountOperationStatus.COMPLETE:
            return operation
        if operation.operation_type != AccountOperationType.EXPORT:
            raise ValueError("Operation is not an export.")
        generated_at = _utc(now or datetime.now(timezone.utc))
        operation = operation.model_copy(
            update={"status": AccountOperationStatus.IN_PROGRESS, "updated_at": generated_at, "safe_error": None}
        )
        self.operations.save_operation(operation)
        try:
            archive, counts = self._build_archive(operation, generated_at)
            expiration_minutes = (
                self.protected_expiration_minutes
                if operation.include_protected_details
                else self.default_expiration_minutes
            )
            artifact_key, size = self.artifacts.put(
                user_id,
                operation.operation_id,
                archive,
                expires_in_seconds=expiration_minutes * 60,
            )
        except Exception:
            failed = operation.model_copy(
                update={
                    "status": AccountOperationStatus.FAILED,
                    "safe_error": "LifeLedger could not prepare the export. It can be retried safely.",
                    "updated_at": generated_at,
                }
            )
            self.operations.save_operation(failed)
            _log("export_failed", failed)
            return failed
        complete = operation.model_copy(
            update={
                "status": AccountOperationStatus.COMPLETE,
                "artifact_key": artifact_key,
                "artifact_size_bytes": size,
                "expires_at": generated_at + timedelta(minutes=expiration_minutes),
                "updated_at": generated_at,
            }
        )
        self.operations.save_operation(complete)
        self.operations.save_lifecycle(
            AccountLifecycle(user_id=user_id, state=AccountState.ACTIVE, updated_at=generated_at)
        )
        _log("export_completed", complete, store_count=len(counts))
        return complete

    def get_download_url(
        self, user_id: str, operation_id: str, *, now: datetime | None = None, expires_in_seconds: int = 300
    ) -> str:
        operation = self._required(user_id, operation_id)
        current = _utc(now or datetime.now(timezone.utc))
        if (
            operation.status != AccountOperationStatus.COMPLETE
            or not operation.artifact_key
            or not operation.expires_at
            or current >= _utc(operation.expires_at)
        ):
            if operation.artifact_key:
                self.artifacts.delete(operation.artifact_key)
            self.operations.save_operation(
                operation.model_copy(
                    update={"status": AccountOperationStatus.EXPIRED, "artifact_key": None, "updated_at": current}
                )
            )
            raise ExportExpired("This export has expired. Request a new export.")
        remaining = max(1, int((_utc(operation.expires_at) - current).total_seconds()))
        return self.artifacts.create_download_url(
            operation.artifact_key,
            expires_in_seconds=min(expires_in_seconds, remaining),
        )

    def expire_artifact(self, user_id: str, operation_id: str, *, now: datetime | None = None) -> AccountOperation:
        operation = self._required(user_id, operation_id)
        if operation.artifact_key:
            self.artifacts.delete(operation.artifact_key)
        expired = operation.model_copy(
            update={
                "status": AccountOperationStatus.EXPIRED,
                "artifact_key": None,
                "updated_at": _utc(now or datetime.now(timezone.utc)),
            }
        )
        return self.operations.save_operation(expired)

    def _build_archive(self, operation: AccountOperation, generated_at: datetime) -> tuple[bytes, dict[str, int]]:
        content = io.BytesIO()
        counts: dict[str, int] = {}
        documents_included = 0
        with zipfile.ZipFile(content, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for store in self.inventory.export_stores:
                rows = store.export_reader(operation.user_id, operation.include_protected_details)
                safe_rows = _scrub(rows)
                counts[store.name] = len(safe_rows)
                archive.writestr(
                    f"data/{store.name}.json",
                    json.dumps(safe_rows, ensure_ascii=False, indent=2, default=str),
                )
                if store.binary_export_reader is not None:
                    for relative_path, document_content in store.binary_export_reader(operation.user_id):
                        safe_path = _safe_archive_path(relative_path)
                        archive.writestr(f"documents/{safe_path}", document_content)
                        documents_included += 1
            manifest = AccountExportManifest(
                export_id=operation.operation_id,
                generated_at=generated_at,
                include_protected_details=operation.include_protected_details,
                stores=counts,
                documents_included=documents_included,
            )
            archive.writestr("manifest.json", manifest.model_dump_json(indent=2))
            archive.writestr(
                "README.txt",
                "LifeLedger portable account export. Protected plaintext is included only when manifest.include_protected_details is true.\n",
            )
        return content.getvalue(), counts

    def _required(self, user_id: str, operation_id: str) -> AccountOperation:
        operation = self.operations.get_operation(user_id, operation_id)
        if operation is None:
            raise KeyError("Account operation not found.")
        return operation


def _scrub(value):
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, dict):
        return {key: _scrub(item) for key, item in value.items() if key.casefold() not in FORBIDDEN_EXPORT_KEYS}
    return value


def _safe_archive_path(value: str) -> str:
    parts = [part for part in value.replace("\\", "/").split("/") if part not in {"", ".", ".."}]
    if not parts:
        raise ValueError("Invalid document export path.")
    return "/".join(parts)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _log(event: str, operation: AccountOperation, **extra) -> None:
    logger.info(
        json.dumps(
            {
                "event": event,
                "operation_id": operation.operation_id,
                "status": operation.status.value,
                "protected_export": operation.include_protected_details,
                **extra,
            }
        )
    )
