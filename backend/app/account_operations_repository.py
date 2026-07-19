from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

from app.account_models import AccountLifecycle, AccountOperation, AccountOperationStatus, AccountOperationType, AccountState


class AccountOperationsRepository(Protocol):
    def get_lifecycle(self, user_id: str) -> AccountLifecycle: ...

    def save_lifecycle(self, lifecycle: AccountLifecycle) -> AccountLifecycle: ...

    def create_operation(self, operation: AccountOperation) -> AccountOperation: ...

    def save_operation(self, operation: AccountOperation) -> AccountOperation: ...

    def get_operation(self, user_id: str, operation_id: str) -> AccountOperation | None: ...

    def find_open_operation(self, user_id: str, operation_type: AccountOperationType) -> AccountOperation | None: ...

    def list_operations(self, user_id: str, limit: int = 100) -> list[AccountOperation]: ...

    def delete_for_user(self, user_id: str) -> int: ...

    def save_deletion_receipt(self, operation_id: str, completed_at: datetime) -> None: ...

    def has_deletion_receipt(self, operation_id: str) -> bool: ...


class LocalAccountOperationsRepository:
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if not self.file_path.exists():
            self._write_unlocked({"lifecycles": [], "operations": [], "deletion_receipts": []})

    def get_lifecycle(self, user_id: str) -> AccountLifecycle:
        with self._lock:
            raw = self._read_unlocked()
            item = next((item for item in raw["lifecycles"] if item["user_id"] == user_id), None)
        if item:
            return AccountLifecycle.model_validate(item)
        return AccountLifecycle(user_id=user_id, state=AccountState.ACTIVE, updated_at=datetime.now(timezone.utc))

    def save_lifecycle(self, lifecycle: AccountLifecycle) -> AccountLifecycle:
        with self._lock:
            raw = self._read_unlocked()
            raw["lifecycles"] = [item for item in raw["lifecycles"] if item["user_id"] != lifecycle.user_id]
            raw["lifecycles"].append(lifecycle.model_dump(mode="json"))
            self._write_unlocked(raw)
        return lifecycle

    def create_operation(self, operation: AccountOperation) -> AccountOperation:
        with self._lock:
            raw = self._read_unlocked()
            if any(item["operation_id"] == operation.operation_id for item in raw["operations"]):
                raise ValueError("Account operation already exists.")
            raw["operations"].append(operation.model_dump(mode="json"))
            self._write_unlocked(raw)
        return operation

    def save_operation(self, operation: AccountOperation) -> AccountOperation:
        with self._lock:
            raw = self._read_unlocked()
            raw["operations"] = [item for item in raw["operations"] if item["operation_id"] != operation.operation_id]
            raw["operations"].append(operation.model_dump(mode="json"))
            self._write_unlocked(raw)
        return operation

    def get_operation(self, user_id: str, operation_id: str) -> AccountOperation | None:
        with self._lock:
            item = next(
                (
                    item
                    for item in self._read_unlocked()["operations"]
                    if item["user_id"] == user_id and item["operation_id"] == operation_id
                ),
                None,
            )
        return AccountOperation.model_validate(item) if item else None

    def find_open_operation(self, user_id: str, operation_type: AccountOperationType) -> AccountOperation | None:
        with self._lock:
            candidates = [
                AccountOperation.model_validate(item)
                for item in self._read_unlocked()["operations"]
                if item["user_id"] == user_id
                and item["operation_type"] == operation_type.value
                and item["status"] in {AccountOperationStatus.PENDING.value, AccountOperationStatus.IN_PROGRESS.value}
            ]
        return max(candidates, key=lambda item: item.created_at) if candidates else None

    def list_operations(self, user_id: str, limit: int = 100) -> list[AccountOperation]:
        with self._lock:
            operations = [
                AccountOperation.model_validate(item)
                for item in self._read_unlocked()["operations"]
                if item["user_id"] == user_id
            ]
        return sorted(operations, key=lambda item: item.created_at, reverse=True)[:limit]

    def delete_for_user(self, user_id: str) -> int:
        with self._lock:
            raw = self._read_unlocked()
            before = len(raw["lifecycles"]) + len(raw["operations"])
            raw["lifecycles"] = [item for item in raw["lifecycles"] if item["user_id"] != user_id]
            raw["operations"] = [item for item in raw["operations"] if item["user_id"] != user_id]
            self._write_unlocked(raw)
            return before - len(raw["lifecycles"]) - len(raw["operations"])

    def save_deletion_receipt(self, operation_id: str, completed_at: datetime) -> None:
        with self._lock:
            raw = self._read_unlocked()
            raw["deletion_receipts"] = [
                item for item in raw["deletion_receipts"] if item["operation_id"] != operation_id
            ]
            raw["deletion_receipts"].append(
                {
                    "operation_id": operation_id,
                    "status": "complete",
                    "completed_at": completed_at.isoformat(),
                }
            )
            self._write_unlocked(raw)

    def has_deletion_receipt(self, operation_id: str) -> bool:
        with self._lock:
            return any(
                item["operation_id"] == operation_id
                for item in self._read_unlocked()["deletion_receipts"]
            )

    def _read_unlocked(self) -> dict[str, list[dict[str, Any]]]:
        raw = json.loads(self.file_path.read_text(encoding="utf-8") or "{}")
        return {
            "lifecycles": raw.get("lifecycles", []),
            "operations": raw.get("operations", []),
            "deletion_receipts": raw.get("deletion_receipts", []),
        }

    def _write_unlocked(self, value: dict[str, list[dict[str, Any]]]) -> None:
        temporary = self.file_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
        os.replace(temporary, self.file_path)


class DynamoAccountOperationsRepository:
    def __init__(self, table_name: str, region_name: str, table: Any | None = None):
        self.table_name = table_name
        self.region_name = region_name
        self.table = table or self._build_table(table_name, region_name)

    def get_lifecycle(self, user_id: str) -> AccountLifecycle:
        item = self.table.get_item(Key={"user_id": user_id, "operation_key": "STATE"}).get("Item")
        if not item:
            return AccountLifecycle(user_id=user_id, state=AccountState.ACTIVE, updated_at=datetime.now(timezone.utc))
        item.pop("operation_key", None)
        return AccountLifecycle.model_validate(item)

    def save_lifecycle(self, lifecycle: AccountLifecycle) -> AccountLifecycle:
        self.table.put_item(Item={"operation_key": "STATE", **lifecycle.model_dump(mode="json", exclude_none=True)})
        return lifecycle

    def create_operation(self, operation: AccountOperation) -> AccountOperation:
        self.table.put_item(
            Item=self._operation_item(operation),
            ConditionExpression="attribute_not_exists(operation_key)",
        )
        return operation

    def save_operation(self, operation: AccountOperation) -> AccountOperation:
        self.table.put_item(Item=self._operation_item(operation))
        return operation

    def get_operation(self, user_id: str, operation_id: str) -> AccountOperation | None:
        item = self.table.get_item(
            Key={"user_id": user_id, "operation_key": f"OP#{operation_id}"}
        ).get("Item")
        return self._operation_from_item(item) if item else None

    def find_open_operation(self, user_id: str, operation_type: AccountOperationType) -> AccountOperation | None:
        response = self.table.query(
            KeyConditionExpression="user_id = :user_id AND begins_with(operation_key, :prefix)",
            ExpressionAttributeValues={":user_id": user_id, ":prefix": "OP#"},
        )
        operations = [self._operation_from_item(item) for item in response.get("Items", [])]
        candidates = [
            item
            for item in operations
            if item.operation_type == operation_type
            and item.status in {AccountOperationStatus.PENDING, AccountOperationStatus.IN_PROGRESS}
        ]
        return max(candidates, key=lambda item: item.created_at) if candidates else None

    def list_operations(self, user_id: str, limit: int = 100) -> list[AccountOperation]:
        response = self.table.query(
            KeyConditionExpression="user_id = :user_id AND begins_with(operation_key, :prefix)",
            ExpressionAttributeValues={":user_id": user_id, ":prefix": "OP#"},
            Limit=limit,
        )
        operations = [self._operation_from_item(item) for item in response.get("Items", [])]
        return sorted(operations, key=lambda item: item.created_at, reverse=True)[:limit]

    def delete_for_user(self, user_id: str) -> int:
        deleted = 0
        query_kwargs: dict[str, Any] = {
            "KeyConditionExpression": "user_id = :user_id",
            "ExpressionAttributeValues": {":user_id": user_id},
            "ProjectionExpression": "user_id, operation_key",
            "Limit": 100,
        }
        while True:
            response = self.table.query(**query_kwargs)
            for item in response.get("Items", []):
                self.table.delete_item(Key=item)
                deleted += 1
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            query_kwargs["ExclusiveStartKey"] = last_key
        return deleted

    def save_deletion_receipt(self, operation_id: str, completed_at: datetime) -> None:
        self.table.put_item(
            Item={
                "user_id": "__DELETION_RECEIPTS__",
                "operation_key": f"RECEIPT#{operation_id}",
                "operation_id": operation_id,
                "status": "complete",
                "completed_at": completed_at.isoformat(),
                "ttl": int((completed_at + timedelta(days=7)).timestamp()),
            }
        )

    def has_deletion_receipt(self, operation_id: str) -> bool:
        item = self.table.get_item(
            Key={
                "user_id": "__DELETION_RECEIPTS__",
                "operation_key": f"RECEIPT#{operation_id}",
            }
        ).get("Item")
        return item is not None

    @staticmethod
    def _operation_item(operation: AccountOperation) -> dict[str, Any]:
        item = {
            "operation_key": f"OP#{operation.operation_id}",
            **operation.model_dump(mode="json", exclude_none=True),
        }
        if (
            operation.operation_type == AccountOperationType.EXPORT
            and operation.status == AccountOperationStatus.COMPLETE
            and operation.expires_at is not None
        ):
            item["expiry_partition"] = "EXPORT"
        return item

    @staticmethod
    def _operation_from_item(item: dict[str, Any]) -> AccountOperation:
        item = dict(item)
        item.pop("operation_key", None)
        return AccountOperation.model_validate(item)

    @staticmethod
    def _build_table(table_name: str, region_name: str):
        import boto3

        return boto3.resource("dynamodb", region_name=region_name).Table(table_name)
