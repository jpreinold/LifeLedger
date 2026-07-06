import json
import os
import threading
from pathlib import Path
from typing import Any, Protocol

from app.models import UserPreferences


class PreferencesRepository(Protocol):
    def get_preferences(self, user_id: str) -> UserPreferences | None:
        ...

    def save_preferences(self, preferences: UserPreferences) -> UserPreferences:
        ...


class LocalPreferencesRepository:
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

        if not self.file_path.exists():
            self._write_all_unlocked([])

    def get_preferences(self, user_id: str) -> UserPreferences | None:
        with self._lock:
            return next((item for item in self._read_all_unlocked() if item.user_id == user_id), None)

    def save_preferences(self, preferences: UserPreferences) -> UserPreferences:
        with self._lock:
            items = self._read_all_unlocked()
            for index, existing in enumerate(items):
                if existing.user_id == preferences.user_id:
                    items[index] = preferences
                    self._write_all_unlocked(items)
                    return preferences

            items.append(preferences)
            self._write_all_unlocked(items)
            return preferences

    def _read_all_unlocked(self) -> list[UserPreferences]:
        if not self.file_path.exists():
            return []

        raw_data = json.loads(self.file_path.read_text(encoding="utf-8") or "[]")
        return [UserPreferences.model_validate(item) for item in raw_data]

    def _write_all_unlocked(self, preferences: list[UserPreferences]) -> None:
        serialized = [item.model_dump(mode="json") for item in preferences]
        temp_path = self.file_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
        os.replace(temp_path, self.file_path)


class DynamoPreferencesRepository:
    def __init__(self, table_name: str, region_name: str, table: Any | None = None):
        self.table_name = table_name
        self.region_name = region_name
        self.table = table or self._build_table(table_name, region_name)

    def get_preferences(self, user_id: str) -> UserPreferences | None:
        response = self.table.get_item(Key={"user_id": user_id})
        item = response.get("Item")
        if item is None:
            return None

        return self._from_item(item)

    def save_preferences(self, preferences: UserPreferences) -> UserPreferences:
        self.table.put_item(Item=self._to_item(preferences))
        return preferences

    def _build_table(self, table_name: str, region_name: str) -> Any:
        import boto3

        return boto3.resource("dynamodb", region_name=region_name).Table(table_name)

    def _to_item(self, preferences: UserPreferences) -> dict[str, Any]:
        return preferences.model_dump(mode="json")

    def _from_item(self, item: dict[str, Any]) -> UserPreferences:
        return UserPreferences.model_validate(item)
