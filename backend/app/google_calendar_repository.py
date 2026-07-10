import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from app.models import GoogleCalendarConnection, GoogleOAuthState
from app.schemas import GoogleCalendarConnectionStatus


class GoogleCalendarConnectionRepository(Protocol):
    def get_connection(self, user_id: str) -> GoogleCalendarConnection | None:
        ...

    def save_connection(self, connection: GoogleCalendarConnection) -> GoogleCalendarConnection:
        ...

    def disconnect_connection(self, user_id: str, disconnected_at: datetime) -> GoogleCalendarConnection | None:
        ...


class GoogleOAuthStateRepository(Protocol):
    def save_state(self, state: GoogleOAuthState) -> GoogleOAuthState:
        ...

    def get_state(self, state: str) -> GoogleOAuthState | None:
        ...

    def consume_state(self, state: str, consumed_at: datetime) -> GoogleOAuthState | None:
        ...


class LocalGoogleCalendarConnectionRepository:
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

        if not self.file_path.exists():
            self._write_all_unlocked([])

    def get_connection(self, user_id: str) -> GoogleCalendarConnection | None:
        with self._lock:
            return next((item for item in self._read_all_unlocked() if item.user_id == user_id), None)

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

    def _read_all_unlocked(self) -> list[GoogleCalendarConnection]:
        if not self.file_path.exists():
            return []

        raw_data = json.loads(self.file_path.read_text(encoding="utf-8") or "[]")
        return [GoogleCalendarConnection.model_validate(item) for item in raw_data]

    def _write_all_unlocked(self, connections: list[GoogleCalendarConnection]) -> None:
        serialized = [connection.model_dump(mode="json") for connection in connections]
        temp_path = self.file_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
        os.replace(temp_path, self.file_path)


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
    def __init__(self, table_name: str, region_name: str, table: Any | None = None):
        self.table_name = table_name
        self.region_name = region_name
        self.table = table or self._build_table(table_name, region_name)

    def get_connection(self, user_id: str) -> GoogleCalendarConnection | None:
        response = self.table.get_item(Key={"user_id": user_id})
        item = response.get("Item")
        if item is None:
            return None

        return self._from_item(item)

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

    def _build_table(self, table_name: str, region_name: str) -> Any:
        import boto3

        return boto3.resource("dynamodb", region_name=region_name).Table(table_name)

    def _to_item(self, connection: GoogleCalendarConnection) -> dict[str, Any]:
        return connection.model_dump(mode="json")

    def _from_item(self, item: dict[str, Any]) -> GoogleCalendarConnection:
        return GoogleCalendarConnection.model_validate(item)


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
