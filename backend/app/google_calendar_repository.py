import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from app.encryption_service import (
    EncryptedPayload,
    EncryptionOperationError,
    EncryptionService,
    google_token_encryption_context,
)
from app.models import GoogleCalendarConnection, GoogleOAuthState
from app.schemas import GoogleCalendarConnectionStatus
from app.security_audit import log_security_event


class GoogleCalendarConnectionRepository(Protocol):
    def get_connection(self, user_id: str) -> GoogleCalendarConnection | None:
        ...

    def save_connection(self, connection: GoogleCalendarConnection) -> GoogleCalendarConnection:
        ...

    def disconnect_connection(self, user_id: str, disconnected_at: datetime) -> GoogleCalendarConnection | None:
        ...

    def delete_connection(self, user_id: str) -> bool:
        ...


class GoogleOAuthStateRepository(Protocol):
    def save_state(self, state: GoogleOAuthState) -> GoogleOAuthState:
        ...

    def get_state(self, state: str) -> GoogleOAuthState | None:
        ...

    def consume_state(self, state: str, consumed_at: datetime) -> GoogleOAuthState | None:
        ...

    def list_for_user(self, user_id: str, limit: int = 100) -> list[GoogleOAuthState]:
        ...

    def delete_for_user(self, user_id: str, limit: int = 100) -> int:
        ...


class LocalGoogleCalendarConnectionRepository:
    def __init__(self, file_path: str | Path, encryption_service: EncryptionService | None = None):
        self.file_path = Path(file_path)
        self.encryption_service = encryption_service
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

        if not self.file_path.exists():
            self._write_all_unlocked([])

    def get_connection(self, user_id: str) -> GoogleCalendarConnection | None:
        with self._lock:
            raw_items = self._read_raw_all_unlocked()
            item = next((item for item in raw_items if item.get("user_id") == user_id), None)
            if item is None:
                return None

            connection = self._from_item(item)
            if self._should_migrate_legacy_tokens(item):
                try:
                    self.save_connection(connection)
                except Exception:
                    return connection
                log_security_event("legacy_google_token_migrated", user_id=user_id, result="success")
            return connection

    def save_connection(self, connection: GoogleCalendarConnection) -> GoogleCalendarConnection:
        with self._lock:
            connections = self._read_all_unlocked()
            for index, existing in enumerate(connections):
                if existing.user_id == connection.user_id:
                    connections[index] = connection
                    self._write_all_unlocked(connections)
                    return connection

            connections.append(connection)
            self._write_all_unlocked(connections)
            return connection

    def disconnect_connection(self, user_id: str, disconnected_at: datetime) -> GoogleCalendarConnection | None:
        with self._lock:
            connection = self.get_connection(user_id)
            if connection is None:
                return None

            disconnected = connection.model_copy(
                update={
                    "access_token": "",
                    "refresh_token": "",
                    "status": GoogleCalendarConnectionStatus.DISCONNECTED,
                    "disconnected_at": disconnected_at,
                    "updated_at": disconnected_at,
                    "last_error": None,
                }
            )
            return self.save_connection(disconnected)

    def delete_connection(self, user_id: str) -> bool:
        with self._lock:
            connections = self._read_all_unlocked()
            remaining = [item for item in connections if item.user_id != user_id]
            if len(remaining) == len(connections):
                return False
            self._write_all_unlocked(remaining)
            return True

    def _read_all_unlocked(self) -> list[GoogleCalendarConnection]:
        return [self._from_item(item) for item in self._read_raw_all_unlocked()]

    def _read_raw_all_unlocked(self) -> list[dict[str, Any]]:
        if not self.file_path.exists():
            return []

        raw_data = json.loads(self.file_path.read_text(encoding="utf-8") or "[]")
        return raw_data if isinstance(raw_data, list) else []

    def _write_all_unlocked(self, connections: list[GoogleCalendarConnection]) -> None:
        serialized = [self._to_item(connection) for connection in connections]
        temp_path = self.file_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
        os.replace(temp_path, self.file_path)

    def _to_item(self, connection: GoogleCalendarConnection) -> dict[str, Any]:
        return google_connection_to_item(connection, self.encryption_service)

    def _from_item(self, item: dict[str, Any]) -> GoogleCalendarConnection:
        return google_connection_from_item(item, self.encryption_service)

    def _should_migrate_legacy_tokens(self, item: dict[str, Any]) -> bool:
        return should_migrate_legacy_google_tokens(item, self.encryption_service)


class LocalGoogleOAuthStateRepository:
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

        if not self.file_path.exists():
            self._write_all_unlocked([])

    def save_state(self, state: GoogleOAuthState) -> GoogleOAuthState:
        with self._lock:
            states = self._read_all_unlocked()
            for index, existing in enumerate(states):
                if existing.state == state.state:
                    states[index] = state
                    self._write_all_unlocked(states)
                    return state

            states.append(state)
            self._write_all_unlocked(states)
            return state

    def get_state(self, state: str) -> GoogleOAuthState | None:
        with self._lock:
            return next((item for item in self._read_all_unlocked() if item.state == state), None)

    def consume_state(self, state: str, consumed_at: datetime) -> GoogleOAuthState | None:
        with self._lock:
            saved_state = self.get_state(state)
            if saved_state is None or saved_state.consumed_at is not None:
                return None

            consumed = saved_state.model_copy(update={"consumed_at": consumed_at})
            self.save_state(consumed)
            return consumed

    def list_for_user(self, user_id: str, limit: int = 100) -> list[GoogleOAuthState]:
        with self._lock:
            return [item for item in self._read_all_unlocked() if item.user_id == user_id][:limit]

    def delete_for_user(self, user_id: str, limit: int = 100) -> int:
        with self._lock:
            states = self._read_all_unlocked()
            targets = {item.state for item in states if item.user_id == user_id}
            targets = set(list(targets)[:limit])
            self._write_all_unlocked([item for item in states if item.state not in targets])
            return len(targets)

    def _read_all_unlocked(self) -> list[GoogleOAuthState]:
        if not self.file_path.exists():
            return []

        raw_data = json.loads(self.file_path.read_text(encoding="utf-8") or "[]")
        return [GoogleOAuthState.model_validate(item) for item in raw_data]

    def _write_all_unlocked(self, states: list[GoogleOAuthState]) -> None:
        serialized = [state.model_dump(mode="json") for state in states]
        temp_path = self.file_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
        os.replace(temp_path, self.file_path)


class DynamoGoogleCalendarConnectionRepository:
    def __init__(
        self,
        table_name: str,
        region_name: str,
        table: Any | None = None,
        encryption_service: EncryptionService | None = None,
    ):
        self.table_name = table_name
        self.region_name = region_name
        self.table = table or self._build_table(table_name, region_name)
        self.encryption_service = encryption_service

    def get_connection(self, user_id: str) -> GoogleCalendarConnection | None:
        response = self.table.get_item(Key={"user_id": user_id})
        item = response.get("Item")
        if item is None:
            return None

        connection = self._from_item(item)
        if self._should_migrate_legacy_tokens(item):
            try:
                self.save_connection(connection)
            except Exception:
                return connection
            log_security_event("legacy_google_token_migrated", user_id=user_id, result="success")
        return connection

    def save_connection(self, connection: GoogleCalendarConnection) -> GoogleCalendarConnection:
        self.table.put_item(Item=self._to_item(connection))
        return connection

    def disconnect_connection(self, user_id: str, disconnected_at: datetime) -> GoogleCalendarConnection | None:
        connection = self.get_connection(user_id)
        if connection is None:
            return None

        disconnected = connection.model_copy(
            update={
                "access_token": "",
                "refresh_token": "",
                "status": GoogleCalendarConnectionStatus.DISCONNECTED,
                "disconnected_at": disconnected_at,
                "updated_at": disconnected_at,
                "last_error": None,
            }
        )
        return self.save_connection(disconnected)

    def delete_connection(self, user_id: str) -> bool:
        self.table.delete_item(Key={"user_id": user_id})
        return True

    def _build_table(self, table_name: str, region_name: str) -> Any:
        import boto3

        return boto3.resource("dynamodb", region_name=region_name).Table(table_name)

    def _to_item(self, connection: GoogleCalendarConnection) -> dict[str, Any]:
        return google_connection_to_item(connection, self.encryption_service)

    def _from_item(self, item: dict[str, Any]) -> GoogleCalendarConnection:
        return google_connection_from_item(item, self.encryption_service)

    def _should_migrate_legacy_tokens(self, item: dict[str, Any]) -> bool:
        return should_migrate_legacy_google_tokens(item, self.encryption_service)


class DynamoGoogleOAuthStateRepository:
    def __init__(self, table_name: str, region_name: str, table: Any | None = None):
        self.table_name = table_name
        self.region_name = region_name
        self.table = table or self._build_table(table_name, region_name)

    def save_state(self, state: GoogleOAuthState) -> GoogleOAuthState:
        self.table.put_item(Item=self._to_item(state))
        return state

    def get_state(self, state: str) -> GoogleOAuthState | None:
        response = self.table.get_item(Key={"state": state})
        item = response.get("Item")
        if item is None:
            return None

        return self._from_item(item)

    def consume_state(self, state: str, consumed_at: datetime) -> GoogleOAuthState | None:
        try:
            response = self.table.update_item(
                Key={"state": state},
                UpdateExpression="SET consumed_at = :consumed_at",
                ConditionExpression=(
                    "attribute_exists(#state) "
                    "AND (attribute_not_exists(consumed_at) OR attribute_type(consumed_at, :null_type))"
                ),
                ExpressionAttributeNames={"#state": "state"},
                ExpressionAttributeValues={
                    ":consumed_at": consumed_at.isoformat(),
                    ":null_type": "NULL",
                },
                ReturnValues="ALL_NEW",
            )
        except Exception as exc:
            if is_dynamo_conditional_check_failure(exc):
                return None
            raise

        item = response.get("Attributes")
        if item is None:
            return None
        return self._from_item(item)

    def list_for_user(self, user_id: str, limit: int = 100) -> list[GoogleOAuthState]:
        response = self.table.query(
            IndexName="UserOAuthStatesIndex",
            KeyConditionExpression="user_id = :user_id",
            ExpressionAttributeValues={":user_id": user_id},
            Limit=limit,
        )
        return [self._from_item(item) for item in response.get("Items", [])]

    def delete_for_user(self, user_id: str, limit: int = 100) -> int:
        states = self.list_for_user(user_id, limit=limit)
        for state in states:
            self.table.delete_item(Key={"state": state.state})
        return len(states)

    def _build_table(self, table_name: str, region_name: str) -> Any:
        import boto3

        return boto3.resource("dynamodb", region_name=region_name).Table(table_name)

    def _to_item(self, state: GoogleOAuthState) -> dict[str, Any]:
        return state.model_dump(mode="json", exclude_none=True)

    def _from_item(self, item: dict[str, Any]) -> GoogleOAuthState:
        return GoogleOAuthState.model_validate(item)


def is_dynamo_conditional_check_failure(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return False

    error = response.get("Error")
    return isinstance(error, dict) and error.get("Code") == "ConditionalCheckFailedException"


def google_connection_to_item(
    connection: GoogleCalendarConnection,
    encryption_service: EncryptionService | None = None,
) -> dict[str, Any]:
    item = connection.model_dump(mode="json", exclude_none=True)
    if encryption_service is None or not encryption_service.enabled or connection.status == GoogleCalendarConnectionStatus.DISCONNECTED:
        return item

    token_bundle = {
        "access_token": connection.access_token,
        "refresh_token": connection.refresh_token,
        "token_expires_at": connection.token_expires_at.isoformat(),
        "scopes": connection.scopes,
    }
    encrypted = encryption_service.encrypt_json(
        token_bundle,
        google_token_encryption_context(connection.user_id),
    )
    item.update(
        {
            "token_ciphertext": encrypted.ciphertext,
            "token_encrypted_data_key": encrypted.encrypted_data_key,
            "token_nonce": encrypted.nonce,
            "token_encryption_version": encrypted.encryption_version,
            "token_key_arn": encrypted.key_arn,
            "token_updated_at": connection.updated_at.isoformat(),
        }
    )
    item.pop("access_token", None)
    item.pop("refresh_token", None)
    return item


def google_connection_from_item(
    item: dict[str, Any],
    encryption_service: EncryptionService | None = None,
) -> GoogleCalendarConnection:
    connection = GoogleCalendarConnection.model_validate(item)
    if not connection.token_ciphertext:
        return connection

    if encryption_service is None or not encryption_service.enabled:
        log_security_event("google_token_decrypt_failed", user_id=connection.user_id, result="encryption_unavailable")
        return connection

    encrypted = EncryptedPayload(
        ciphertext=connection.token_ciphertext,
        encrypted_data_key=connection.token_encrypted_data_key or "",
        nonce=connection.token_nonce or "",
        encryption_version=connection.token_encryption_version or 0,
        key_arn=connection.token_key_arn,
    )
    try:
        token_bundle = encryption_service.decrypt_json(
            encrypted,
            google_token_encryption_context(connection.user_id),
        )
    except EncryptionOperationError:
        log_security_event("google_token_decrypt_failed", user_id=connection.user_id, result="decrypt_failed")
        return connection

    updates: dict[str, Any] = {
        "access_token": safe_string(token_bundle.get("access_token")),
        "refresh_token": safe_string(token_bundle.get("refresh_token")),
        "scopes": safe_string(token_bundle.get("scopes")) or connection.scopes,
    }
    token_expires_at = token_bundle.get("token_expires_at")
    if isinstance(token_expires_at, str) and token_expires_at:
        updates["token_expires_at"] = datetime.fromisoformat(token_expires_at)

    return connection.model_copy(update=updates)


def should_migrate_legacy_google_tokens(
    item: dict[str, Any],
    encryption_service: EncryptionService | None = None,
) -> bool:
    if encryption_service is None or not encryption_service.enabled:
        return False
    return bool((item.get("access_token") or item.get("refresh_token")) and not item.get("token_ciphertext"))


def safe_string(value: Any) -> str:
    return value if isinstance(value, str) else ""
