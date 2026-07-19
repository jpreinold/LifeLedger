from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


ExportReader = Callable[[str, bool], list[dict[str, Any]]]
DeleteAction = Callable[[str, int], int]
CountReader = Callable[[str, int], int]
BinaryExportReader = Callable[[str], list[tuple[str, bytes]]]


@dataclass(frozen=True)
class AccountDataStore:
    name: str
    ownership_key: str
    pagination: str
    export_behavior: str
    deletion_behavior: str
    retention_exception: str | None
    external_cleanup: str | None
    export_reader: ExportReader
    delete_action: DeleteAction
    count_reader: CountReader
    deletion_order: int
    export_enabled: bool = True
    binary_export_reader: BinaryExportReader | None = None


class AccountDataInventory:
    """The single registry consumed by account export, deletion, and verification."""

    def __init__(self, stores: list[AccountDataStore]):
        names = [store.name for store in stores]
        if len(names) != len(set(names)):
            raise ValueError("Account data store names must be unique.")
        self._stores = tuple(stores)

    @property
    def stores(self) -> tuple[AccountDataStore, ...]:
        return self._stores

    @property
    def export_stores(self) -> tuple[AccountDataStore, ...]:
        return tuple(store for store in self._stores if store.export_enabled)

    @property
    def deletion_stores(self) -> tuple[AccountDataStore, ...]:
        return tuple(sorted(self._stores, key=lambda store: (store.deletion_order, store.name)))

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "name": store.name,
                "ownership_key": store.ownership_key,
                "pagination": store.pagination,
                "export_behavior": store.export_behavior,
                "deletion_behavior": store.deletion_behavior,
                "retention_exception": store.retention_exception,
                "external_cleanup": store.external_cleanup,
            }
            for store in self._stores
        ]
