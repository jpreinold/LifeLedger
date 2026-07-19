import json
import os
import threading
from pathlib import Path
from typing import Protocol

from app.models import Record
from app.schemas import RecordStatus


class RecordRepository(Protocol):
    def list_records(
        self, user_id: str, include_archived: bool = False, limit: int | None = None
    ) -> list[Record]:
        ...

    def get_record(self, user_id: str, record_id: str) -> Record | None:
        ...

    def create_record(self, record: Record) -> Record:
        ...

    def update_record(self, record: Record) -> Record:
        ...

    def delete_record(self, user_id: str, record_id: str) -> bool:
        ...

    def archive_record(self, user_id: str, record_id: str) -> Record | None:
        ...

    def unarchive_record(self, user_id: str, record_id: str) -> Record | None:
        ...


class LocalRecordRepository:
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

        if not self.file_path.exists():
            self._write_all_unlocked([])

    def list_records(
        self, user_id: str, include_archived: bool = False, limit: int | None = None
    ) -> list[Record]:
        with self._lock:
            records = [
                record
                for record in self._read_all_unlocked()
                if record.user_id == user_id and (include_archived or record.status != RecordStatus.ARCHIVED)
            ]
        return records[:limit] if limit is not None else records

    def get_record(self, user_id: str, record_id: str) -> Record | None:
        with self._lock:
            return next(
                (
                    record
                    for record in self._read_all_unlocked()
                    if record.user_id == user_id and record.id == record_id
                ),
                None,
            )

    def create_record(self, record: Record) -> Record:
        with self._lock:
            records = self._read_all_unlocked()
            records.append(record)
            self._write_all_unlocked(records)
            return record

    def update_record(self, record: Record) -> Record:
        with self._lock:
            records = self._read_all_unlocked()
            for index, existing in enumerate(records):
                if existing.user_id == record.user_id and existing.id == record.id:
                    records[index] = record
                    self._write_all_unlocked(records)
                    return record

            records.append(record)
            self._write_all_unlocked(records)
            return record

    def delete_record(self, user_id: str, record_id: str) -> bool:
        with self._lock:
            records = self._read_all_unlocked()
            next_records = [
                record
                for record in records
                if not (record.user_id == user_id and record.id == record_id)
            ]

            if len(next_records) == len(records):
                return False

            self._write_all_unlocked(next_records)
            return True

    def archive_record(self, user_id: str, record_id: str) -> Record | None:
        return self._set_record_status(user_id, record_id, RecordStatus.ARCHIVED)

    def unarchive_record(self, user_id: str, record_id: str) -> Record | None:
        return self._set_record_status(user_id, record_id, RecordStatus.ACTIVE)

    def _set_record_status(self, user_id: str, record_id: str, status: RecordStatus) -> Record | None:
        with self._lock:
            record = self.get_record(user_id, record_id)
            if record is None:
                return None

            from datetime import datetime, timezone

            return self.update_record(record.model_copy(update={"status": status, "updated_at": datetime.now(timezone.utc)}))

    def _read_all_unlocked(self) -> list[Record]:
        if not self.file_path.exists():
            return []

        raw_data = json.loads(self.file_path.read_text(encoding="utf-8") or "[]")
        return [Record.model_validate(item) for item in raw_data]

    def _write_all_unlocked(self, records: list[Record]) -> None:
        serialized = [record.model_dump(mode="json") for record in records]
        temp_path = self.file_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
        os.replace(temp_path, self.file_path)
