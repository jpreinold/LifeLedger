from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from app.reconciliation import ReconciliationDomain, ReconciliationIssue, ReconciliationStatus


class ReconciliationRepository(Protocol):
    def create_or_get(self, issue: ReconciliationIssue) -> tuple[ReconciliationIssue, bool]: ...

    def save(self, issue: ReconciliationIssue) -> ReconciliationIssue: ...

    def get(self, reconciliation_id: str) -> ReconciliationIssue | None: ...

    def list_by_status(self, status: ReconciliationStatus, limit: int = 100) -> list[ReconciliationIssue]: ...

    def list_by_user(self, user_id: str, limit: int = 100, cursor: str | None = None) -> list[ReconciliationIssue]: ...

    def list_by_domain(self, domain: ReconciliationDomain, limit: int = 100) -> list[ReconciliationIssue]: ...

    def list_due(self, now: datetime, limit: int = 25) -> list[ReconciliationIssue]: ...

    def delete_for_user(self, user_id: str, limit: int = 100) -> int: ...


class LocalReconciliationRepository:
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if not self.file_path.exists():
            self._write_unlocked([])

    def create_or_get(self, issue: ReconciliationIssue) -> tuple[ReconciliationIssue, bool]:
        with self._lock:
            issues = self._read_unlocked()
            existing = next(
                (item for item in issues if item.reconciliation_id == issue.reconciliation_id),
                None,
            )
            if existing is not None:
                return existing, False
            issues.append(issue)
            self._write_unlocked(issues)
            return issue, True

    def save(self, issue: ReconciliationIssue) -> ReconciliationIssue:
        with self._lock:
            issues = [item for item in self._read_unlocked() if item.reconciliation_id != issue.reconciliation_id]
            issues.append(issue)
            self._write_unlocked(issues)
        return issue

    def get(self, reconciliation_id: str) -> ReconciliationIssue | None:
        with self._lock:
            return next((item for item in self._read_unlocked() if item.reconciliation_id == reconciliation_id), None)

    def list_by_status(self, status: ReconciliationStatus, limit: int = 100) -> list[ReconciliationIssue]:
        with self._lock:
            return self._sorted(item for item in self._read_unlocked() if item.status == status)[:limit]

    def list_by_user(self, user_id: str, limit: int = 100, cursor: str | None = None) -> list[ReconciliationIssue]:
        with self._lock:
            issues = self._sorted(item for item in self._read_unlocked() if item.user_id == user_id)
        if cursor:
            cursor_index = next(
                (index for index, item in enumerate(issues) if item.reconciliation_id == cursor),
                None,
            )
            if cursor_index is None:
                raise ValueError("Invalid reconciliation cursor.")
            issues = issues[cursor_index + 1 :]
        return issues[:limit]

    def list_by_domain(self, domain: ReconciliationDomain, limit: int = 100) -> list[ReconciliationIssue]:
        with self._lock:
            return self._sorted(item for item in self._read_unlocked() if item.domain == domain)[:limit]

    def list_due(self, now: datetime, limit: int = 25) -> list[ReconciliationIssue]:
        normalized_now = _utc(now)
        with self._lock:
            due = [
                item
                for item in self._read_unlocked()
                if item.retryable
                and item.status in {ReconciliationStatus.PENDING, ReconciliationStatus.RETRYING}
                and (item.next_retry_at is None or _utc(item.next_retry_at) <= normalized_now)
            ]
        return sorted(due, key=lambda item: (item.next_retry_at or item.detected_at, item.reconciliation_id))[:limit]

    def delete_for_user(self, user_id: str, limit: int = 100) -> int:
        with self._lock:
            issues = self._read_unlocked()
            targets = [item.reconciliation_id for item in issues if item.user_id == user_id][:limit]
            if not targets:
                return 0
            target_set = set(targets)
            self._write_unlocked([item for item in issues if item.reconciliation_id not in target_set])
            return len(targets)

    def _read_unlocked(self) -> list[ReconciliationIssue]:
        raw = json.loads(self.file_path.read_text(encoding="utf-8") or "[]")
        return [ReconciliationIssue.model_validate(item) for item in raw]

    def _write_unlocked(self, issues: list[ReconciliationIssue]) -> None:
        temporary = self.file_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps([item.model_dump(mode="json") for item in issues], indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, self.file_path)

    @staticmethod
    def _sorted(issues: Any) -> list[ReconciliationIssue]:
        return sorted(issues, key=lambda item: (item.detected_at, item.reconciliation_id))


class DynamoReconciliationRepository:
    def __init__(self, table_name: str, region_name: str, table: Any | None = None):
        self.table_name = table_name
        self.region_name = region_name
        self.table = table or self._build_table(table_name, region_name)

    def create_or_get(self, issue: ReconciliationIssue) -> tuple[ReconciliationIssue, bool]:
        try:
            self.table.put_item(
                Item=self._to_item(issue),
                ConditionExpression="attribute_not_exists(reconciliation_id)",
            )
            return issue, True
        except Exception as error:
            response = getattr(error, "response", {})
            if response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
            existing = self.get(issue.reconciliation_id)
            if existing is None:
                raise
            return existing, False

    def save(self, issue: ReconciliationIssue) -> ReconciliationIssue:
        self.table.put_item(Item=self._to_item(issue))
        return issue

    def get(self, reconciliation_id: str) -> ReconciliationIssue | None:
        item = self.table.get_item(Key={"reconciliation_id": reconciliation_id}).get("Item")
        return self._from_item(item) if item else None

    def list_by_status(self, status: ReconciliationStatus, limit: int = 100) -> list[ReconciliationIssue]:
        return self._query("status-index", "status", status.value, limit)

    def list_by_user(self, user_id: str, limit: int = 100, cursor: str | None = None) -> list[ReconciliationIssue]:
        kwargs: dict[str, Any] = {
            "IndexName": "user-index",
            "KeyConditionExpression": "user_id = :value",
            "ExpressionAttributeValues": {":value": user_id},
            "Limit": limit,
        }
        if cursor:
            cursor_issue = self.get(cursor)
            if cursor_issue is None or cursor_issue.user_id != user_id:
                raise ValueError("Invalid reconciliation cursor.")
            kwargs["ExclusiveStartKey"] = {
                "reconciliation_id": cursor,
                "user_id": user_id,
                "detected_at": cursor_issue.detected_at.isoformat(),
            }
        return [self._from_item(item) for item in self.table.query(**kwargs).get("Items", [])]

    def list_by_domain(self, domain: ReconciliationDomain, limit: int = 100) -> list[ReconciliationIssue]:
        return self._query("domain-index", "domain", domain.value, limit)

    def list_due(self, now: datetime, limit: int = 25) -> list[ReconciliationIssue]:
        response = self.table.query(
            IndexName="due-index",
            KeyConditionExpression="due_partition = :partition AND due_at <= :now",
            ExpressionAttributeValues={":partition": "DUE", ":now": _utc(now).isoformat()},
            Limit=limit,
        )
        return [self._from_item(item) for item in response.get("Items", [])]

    def delete_for_user(self, user_id: str, limit: int = 100) -> int:
        issues = self.list_by_user(user_id, limit=limit)
        for issue in issues:
            self.table.delete_item(Key={"reconciliation_id": issue.reconciliation_id})
        return len(issues)

    def _query(self, index: str, key: str, value: str, limit: int) -> list[ReconciliationIssue]:
        response = self.table.query(
            IndexName=index,
            KeyConditionExpression=f"{key} = :value",
            ExpressionAttributeValues={":value": value},
            Limit=limit,
        )
        return [self._from_item(item) for item in response.get("Items", [])]

    @staticmethod
    def _to_item(issue: ReconciliationIssue) -> dict[str, Any]:
        item = issue.model_dump(mode="json", exclude_none=True)
        if issue.retryable and issue.status in {ReconciliationStatus.PENDING, ReconciliationStatus.RETRYING}:
            item["due_partition"] = "DUE"
            item["due_at"] = _utc(issue.next_retry_at or issue.detected_at).isoformat()
        return item

    @staticmethod
    def _from_item(item: dict[str, Any]) -> ReconciliationIssue:
        return ReconciliationIssue.model_validate(item)

    @staticmethod
    def _build_table(table_name: str, region_name: str):
        import boto3

        return boto3.resource("dynamodb", region_name=region_name).Table(table_name)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
