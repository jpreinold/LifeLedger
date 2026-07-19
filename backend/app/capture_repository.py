from __future__ import annotations

import base64
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import threading
from typing import Any, Protocol, TypeVar

from app.capture_models import (
    AISettings,
    AIUsageRecord,
    ActionProposal,
    Capture,
    CaptureStatus,
    ClarificationSession,
)


T = TypeVar("T")


class AssistantRepository(Protocol):
    def create_capture(self, capture: Capture) -> tuple[Capture, bool]: ...
    def save_capture(self, capture: Capture) -> Capture: ...
    def get_capture(self, user_id: str, capture_id: str) -> Capture | None: ...
    def list_captures(
        self,
        user_id: str,
        *,
        statuses: set[CaptureStatus] | None = None,
        limit: int = 25,
        cursor: str | None = None,
    ) -> tuple[list[Capture], str | None]: ...
    def create_proposal(self, proposal: ActionProposal) -> tuple[ActionProposal, bool]: ...
    def save_proposal(self, proposal: ActionProposal) -> ActionProposal: ...
    def get_proposal(self, user_id: str, proposal_id: str) -> ActionProposal | None: ...
    def get_proposal_for_capture(self, user_id: str, capture_id: str) -> ActionProposal | None: ...
    def save_clarification(self, session: ClarificationSession) -> ClarificationSession: ...
    def get_clarification(self, user_id: str, clarification_id: str) -> ClarificationSession | None: ...
    def get_clarification_for_proposal(self, user_id: str, proposal_id: str) -> ClarificationSession | None: ...
    def get_ai_settings(self, user_id: str) -> AISettings | None: ...
    def save_ai_settings(self, settings: AISettings) -> AISettings: ...
    def record_usage_once(self, usage: AIUsageRecord) -> tuple[AIUsageRecord, bool]: ...
    def list_usage(self, user_id: str, prefix: str, *, limit: int = 1_000) -> list[AIUsageRecord]: ...
    def list_entity_rows(self, user_id: str, kind: str, *, limit: int | None = None) -> list[dict[str, Any]]: ...
    def delete_entity_rows(self, user_id: str, kind: str, *, limit: int = 100) -> int: ...
    def count_entity_rows(self, user_id: str, kind: str, *, limit: int = 100) -> int: ...


KIND_MODELS = {
    "capture": Capture,
    "proposal": ActionProposal,
    "clarification": ClarificationSession,
    "usage": AIUsageRecord,
    "settings": AISettings,
}

KIND_ID_FIELDS = {
    "capture": "capture_id",
    "proposal": "proposal_id",
    "clarification": "clarification_id",
    "usage": "usage_id",
    "settings": "user_id",
}


class LocalAssistantRepository:
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if not self.file_path.exists():
            self._write_rows_unlocked([])

    def create_capture(self, capture: Capture) -> tuple[Capture, bool]:
        return self._create("capture", capture)

    def save_capture(self, capture: Capture) -> Capture:
        return self._save("capture", capture)

    def get_capture(self, user_id: str, capture_id: str) -> Capture | None:
        return self._get("capture", user_id, capture_id)

    def list_captures(
        self,
        user_id: str,
        *,
        statuses: set[CaptureStatus] | None = None,
        limit: int = 25,
        cursor: str | None = None,
    ) -> tuple[list[Capture], str | None]:
        _validate_limit(limit)
        offset = _decode_cursor(cursor)
        captures = [
            Capture.model_validate(row["data"])
            for row in self._read_rows()
            if row.get("kind") == "capture" and row.get("data", {}).get("user_id") == user_id
        ]
        if statuses:
            captures = [item for item in captures if item.status in statuses]
        captures.sort(key=lambda item: (item.captured_at, item.capture_id), reverse=True)
        page = captures[offset : offset + limit]
        next_cursor = _encode_cursor(offset + limit) if offset + limit < len(captures) else None
        return page, next_cursor

    def create_proposal(self, proposal: ActionProposal) -> tuple[ActionProposal, bool]:
        return self._create("proposal", proposal)

    def save_proposal(self, proposal: ActionProposal) -> ActionProposal:
        return self._save("proposal", proposal)

    def get_proposal(self, user_id: str, proposal_id: str) -> ActionProposal | None:
        return self._get("proposal", user_id, proposal_id)

    def get_proposal_for_capture(self, user_id: str, capture_id: str) -> ActionProposal | None:
        values = [
            ActionProposal.model_validate(row["data"])
            for row in self._read_rows()
            if row.get("kind") == "proposal"
            and row.get("data", {}).get("user_id") == user_id
            and row.get("data", {}).get("capture_id") == capture_id
        ]
        return max(values, key=lambda item: (item.created_at, item.proposal_id), default=None)

    def save_clarification(self, session: ClarificationSession) -> ClarificationSession:
        return self._save("clarification", session)

    def get_clarification(self, user_id: str, clarification_id: str) -> ClarificationSession | None:
        return self._get("clarification", user_id, clarification_id)

    def get_clarification_for_proposal(self, user_id: str, proposal_id: str) -> ClarificationSession | None:
        values = [
            ClarificationSession.model_validate(row["data"])
            for row in self._read_rows()
            if row.get("kind") == "clarification"
            and row.get("data", {}).get("user_id") == user_id
            and row.get("data", {}).get("proposal_id") == proposal_id
        ]
        return max(values, key=lambda item: (item.created_at, item.clarification_id), default=None)

    def get_ai_settings(self, user_id: str) -> AISettings | None:
        return self._get("settings", user_id, user_id)

    def save_ai_settings(self, settings: AISettings) -> AISettings:
        return self._save("settings", settings)

    def record_usage_once(self, usage: AIUsageRecord) -> tuple[AIUsageRecord, bool]:
        return self._create("usage", usage)

    def list_usage(self, user_id: str, prefix: str, *, limit: int = 1_000) -> list[AIUsageRecord]:
        return [
            item
            for item in self._list_models("usage", user_id, limit=limit)
            if item.billing_day.startswith(prefix) or item.billing_month.startswith(prefix)
        ]

    def list_entity_rows(self, user_id: str, kind: str, *, limit: int | None = None) -> list[dict[str, Any]]:
        _required_kind(kind)
        rows = [
            row["data"]
            for row in self._read_rows()
            if row.get("kind") == kind and row.get("data", {}).get("user_id") == user_id
        ]
        return rows if limit is None else rows[:limit]

    def delete_entity_rows(self, user_id: str, kind: str, *, limit: int = 100) -> int:
        _required_kind(kind)
        with self._lock:
            rows = self._read_rows_unlocked()
            deleted = 0
            remaining = []
            for row in rows:
                matches = row.get("kind") == kind and row.get("data", {}).get("user_id") == user_id
                if matches and deleted < limit:
                    deleted += 1
                else:
                    remaining.append(row)
            if deleted:
                self._write_rows_unlocked(remaining)
            return deleted

    def count_entity_rows(self, user_id: str, kind: str, *, limit: int = 100) -> int:
        return len(self.list_entity_rows(user_id, kind, limit=limit))

    def _create(self, kind: str, model: T) -> tuple[T, bool]:
        with self._lock:
            rows = self._read_rows_unlocked()
            model_id = _model_id(kind, model)
            user_id = getattr(model, "user_id")
            for row in rows:
                if _row_matches(row, kind, user_id, model_id):
                    return KIND_MODELS[kind].model_validate(row["data"]), False
            rows.append({"kind": kind, "data": model.model_dump(mode="json")})
            self._write_rows_unlocked(rows)
            return model, True

    def _save(self, kind: str, model: T) -> T:
        with self._lock:
            rows = self._read_rows_unlocked()
            model_id = _model_id(kind, model)
            user_id = getattr(model, "user_id")
            replacement = {"kind": kind, "data": model.model_dump(mode="json")}
            for index, row in enumerate(rows):
                if _row_matches(row, kind, user_id, model_id):
                    rows[index] = replacement
                    self._write_rows_unlocked(rows)
                    return model
            rows.append(replacement)
            self._write_rows_unlocked(rows)
            return model

    def _get(self, kind: str, user_id: str, model_id: str):
        for row in self._read_rows():
            if _row_matches(row, kind, user_id, model_id):
                return KIND_MODELS[kind].model_validate(row["data"])
        return None

    def _list_models(self, kind: str, user_id: str, *, limit: int):
        return [KIND_MODELS[kind].model_validate(row) for row in self.list_entity_rows(user_id, kind, limit=limit)]

    def _read_rows(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read_rows_unlocked()

    def _read_rows_unlocked(self) -> list[dict[str, Any]]:
        if not self.file_path.exists():
            return []
        raw = json.loads(self.file_path.read_text(encoding="utf-8") or "[]")
        return raw if isinstance(raw, list) else []

    def _write_rows_unlocked(self, rows: list[dict[str, Any]]) -> None:
        temp = self.file_path.with_suffix(".tmp")
        temp.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        os.replace(temp, self.file_path)


class DynamoAssistantRepository:
    def __init__(self, table_name: str, region_name: str, table: Any | None = None):
        self.table_name = table_name
        self.region_name = region_name
        self.table = table or self._build_table(table_name, region_name)

    def create_capture(self, capture: Capture) -> tuple[Capture, bool]:
        return self._create("capture", capture)

    def save_capture(self, capture: Capture) -> Capture:
        return self._save("capture", capture)

    def get_capture(self, user_id: str, capture_id: str) -> Capture | None:
        return self._get("capture", user_id, capture_id)

    def list_captures(
        self,
        user_id: str,
        *,
        statuses: set[CaptureStatus] | None = None,
        limit: int = 25,
        cursor: str | None = None,
    ) -> tuple[list[Capture], str | None]:
        _validate_limit(limit)
        from boto3.dynamodb.conditions import Key

        kwargs: dict[str, Any] = {
            "IndexName": "UserEntityTypeIndex",
            "KeyConditionExpression": Key("type_partition").eq(f"{user_id}#capture"),
            "ScanIndexForward": False,
            "Limit": min(100, limit * 4),
        }
        if cursor:
            kwargs["ExclusiveStartKey"] = _decode_dynamo_cursor(cursor)
        response = self.table.query(**kwargs)
        values = [self._from_item("capture", item) for item in response.get("Items", [])]
        if statuses:
            values = [item for item in values if item.status in statuses]
        values = values[:limit]
        next_cursor = _encode_dynamo_cursor(response.get("LastEvaluatedKey"))
        return values, next_cursor

    def create_proposal(self, proposal: ActionProposal) -> tuple[ActionProposal, bool]:
        return self._create("proposal", proposal)

    def save_proposal(self, proposal: ActionProposal) -> ActionProposal:
        return self._save("proposal", proposal)

    def get_proposal(self, user_id: str, proposal_id: str) -> ActionProposal | None:
        return self._get("proposal", user_id, proposal_id)

    def get_proposal_for_capture(self, user_id: str, capture_id: str) -> ActionProposal | None:
        return self._query_parent("proposal", f"{user_id}#proposal_by_capture#{capture_id}")

    def save_clarification(self, session: ClarificationSession) -> ClarificationSession:
        return self._save("clarification", session)

    def get_clarification(self, user_id: str, clarification_id: str) -> ClarificationSession | None:
        return self._get("clarification", user_id, clarification_id)

    def get_clarification_for_proposal(self, user_id: str, proposal_id: str) -> ClarificationSession | None:
        return self._query_parent("clarification", f"{user_id}#clarification_by_proposal#{proposal_id}")

    def get_ai_settings(self, user_id: str) -> AISettings | None:
        return self._get("settings", user_id, user_id)

    def save_ai_settings(self, settings: AISettings) -> AISettings:
        return self._save("settings", settings)

    def record_usage_once(self, usage: AIUsageRecord) -> tuple[AIUsageRecord, bool]:
        return self._create("usage", usage)

    def list_usage(self, user_id: str, prefix: str, *, limit: int = 1_000) -> list[AIUsageRecord]:
        from boto3.dynamodb.conditions import Key

        month = prefix[:7]
        key_condition = Key("billing_partition").eq(f"{user_id}#{month}")
        if len(prefix) >= 10:
            key_condition &= Key("billing_sort").begins_with(prefix[:10])
        response = self.table.query(
            IndexName="BillingPeriodIndex",
            KeyConditionExpression=key_condition,
            Limit=limit,
        )
        values = [self._from_item("usage", item) for item in response.get("Items", [])]
        return [item for item in values if item.billing_day.startswith(prefix) or item.billing_month.startswith(prefix)]

    def list_entity_rows(self, user_id: str, kind: str, *, limit: int | None = None) -> list[dict[str, Any]]:
        _required_kind(kind)
        from boto3.dynamodb.conditions import Key

        response = self.table.query(
            KeyConditionExpression=Key("user_id").eq(user_id) & Key("entity_key").begins_with(f"{kind.upper()}#"),
            Limit=limit or 1_000,
        )
        return [self._payload(item) for item in response.get("Items", [])]

    def delete_entity_rows(self, user_id: str, kind: str, *, limit: int = 100) -> int:
        rows = self._query_raw_kind(user_id, kind, limit)
        for row in rows:
            self.table.delete_item(Key={"user_id": user_id, "entity_key": row["entity_key"]})
        return len(rows)

    def count_entity_rows(self, user_id: str, kind: str, *, limit: int = 100) -> int:
        return len(self._query_raw_kind(user_id, kind, limit))

    def _query_raw_kind(self, user_id: str, kind: str, limit: int):
        from boto3.dynamodb.conditions import Key

        response = self.table.query(
            KeyConditionExpression=Key("user_id").eq(user_id) & Key("entity_key").begins_with(f"{kind.upper()}#"),
            ProjectionExpression="user_id, entity_key",
            Limit=limit,
        )
        return response.get("Items", [])

    def _query_parent(self, kind: str, parent_partition: str):
        from boto3.dynamodb.conditions import Key

        response = self.table.query(
            IndexName="ParentIndex",
            KeyConditionExpression=Key("parent_partition").eq(parent_partition),
            ScanIndexForward=False,
            Limit=1,
        )
        items = response.get("Items", [])
        return self._from_item(kind, items[0]) if items else None

    def _create(self, kind: str, model: T) -> tuple[T, bool]:
        item = self._to_item(kind, model)
        try:
            self.table.put_item(Item=item, ConditionExpression="attribute_not_exists(entity_key)")
            return model, True
        except Exception as exc:
            response = getattr(exc, "response", {})
            if response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
            existing = self._get(kind, getattr(model, "user_id"), _model_id(kind, model))
            if existing is None:
                raise
            return existing, False

    def _save(self, kind: str, model: T) -> T:
        self.table.put_item(Item=self._to_item(kind, model))
        return model

    def _get(self, kind: str, user_id: str, model_id: str):
        response = self.table.get_item(Key={"user_id": user_id, "entity_key": _entity_key(kind, model_id)})
        item = response.get("Item")
        return self._from_item(kind, item) if item else None

    def _to_item(self, kind: str, model: Any) -> dict[str, Any]:
        payload = model.model_dump(mode="json")
        model_id = _model_id(kind, model)
        created_at = payload.get("captured_at") or payload.get("created_at") or payload.get("timestamp") or payload.get("updated_at")
        item: dict[str, Any] = {
            "user_id": model.user_id,
            "entity_key": _entity_key(kind, model_id),
            "entity_type": kind,
            "payload": payload,
            "type_partition": f"{model.user_id}#{kind}",
            "sort_key": f"{created_at}#{model_id}",
        }
        status = payload.get("status")
        if status:
            item["status_partition"] = f"{model.user_id}#{kind}#{status}"
        if kind == "proposal":
            item["parent_partition"] = f"{model.user_id}#proposal_by_capture#{model.capture_id}"
            if status in {"ready_for_review", "approved", "executing", "partially_completed", "failed"}:
                item["expiration_partition"] = "proposal#executable"
            item["expires_at_sort"] = f"{payload['expires_at']}#{model_id}"
            item["ttl"] = _ttl_after(payload["expires_at"], days=30)
        elif kind == "clarification":
            item["parent_partition"] = f"{model.user_id}#clarification_by_proposal#{model.proposal_id}"
            item["ttl"] = _ttl_after(payload["expires_at"], days=30)
        elif kind == "usage":
            item["billing_partition"] = f"{model.user_id}#{model.billing_month}"
            item["billing_sort"] = f"{model.billing_day}#{payload['timestamp']}#{model_id}"
        elif kind == "capture" and payload.get("retention_expires_at"):
            item["ttl"] = int(datetime.fromisoformat(payload["retention_expires_at"]).timestamp())
        return _to_decimal(item)

    def _from_item(self, kind: str, item: dict[str, Any]):
        return KIND_MODELS[kind].model_validate(self._payload(item))

    @staticmethod
    def _payload(item: dict[str, Any]) -> dict[str, Any]:
        return _from_decimal(item.get("payload", {}))

    @staticmethod
    def _build_table(table_name: str, region_name: str):
        import boto3

        return boto3.resource("dynamodb", region_name=region_name).Table(table_name)


def _required_kind(kind: str) -> None:
    if kind not in KIND_MODELS:
        raise ValueError(f"Unsupported assistant entity kind: {kind}")


def _ttl_after(value: str, *, days: int) -> int:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int((parsed + timedelta(days=days)).timestamp())


def _model_id(kind: str, model: Any) -> str:
    return str(getattr(model, KIND_ID_FIELDS[kind]))


def _entity_key(kind: str, model_id: str) -> str:
    return f"{kind.upper()}#{model_id}"


def _row_matches(row: dict[str, Any], kind: str, user_id: str, model_id: str) -> bool:
    data = row.get("data", {})
    return row.get("kind") == kind and data.get("user_id") == user_id and str(data.get(KIND_ID_FIELDS[kind])) == model_id


def _validate_limit(limit: int) -> None:
    if limit < 1 or limit > 100:
        raise ValueError("Limit must be between 1 and 100.")


def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"offset": offset}).encode()).decode().rstrip("=")


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        padding = "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(cursor + padding))
        offset = int(value["offset"])
    except Exception as exc:
        raise ValueError("Invalid capture cursor.") from exc
    if offset < 0:
        raise ValueError("Invalid capture cursor.")
    return offset


def _encode_dynamo_cursor(key: dict[str, Any] | None) -> str | None:
    if not key:
        return None
    raw = json.dumps(_from_decimal(key), separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_dynamo_cursor(cursor: str) -> dict[str, Any]:
    try:
        padding = "=" * (-len(cursor) % 4)
        return _to_decimal(json.loads(base64.urlsafe_b64decode(cursor + padding)))
    except Exception as exc:
        raise ValueError("Invalid capture cursor.") from exc


def _to_decimal(value):
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, list):
        return [_to_decimal(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_decimal(item) for key, item in value.items()}
    return value


def _from_decimal(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [_from_decimal(item) for item in value]
    if isinstance(value, dict):
        return {key: _from_decimal(item) for key, item in value.items()}
    return value
