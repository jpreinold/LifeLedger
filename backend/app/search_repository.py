import json
import os
import threading
from pathlib import Path
from typing import Any, Protocol

from app.models import SavedSearchView, SearchProjection

SEARCH_PROJECTION_PREFIX = "ITEM#"
SEARCH_TOKEN_PREFIX = "TOKEN#"
SEARCH_PROJECTION_KIND = "search_projection"
SEARCH_TOKEN_KIND = "search_token"


def search_projection_key(search_item_id: str) -> str:
    return f"{SEARCH_PROJECTION_PREFIX}{search_item_id}"


def search_token_key(token: str, search_item_id: str) -> str:
    return f"{SEARCH_TOKEN_PREFIX}{token}#{search_item_id}"


class SearchIndexRepository(Protocol):
    def upsert_projection(self, projection: SearchProjection) -> SearchProjection:
        ...

    def get_projection(self, user_id: str, search_item_id: str) -> SearchProjection | None:
        ...

    def batch_get_projections(self, user_id: str, search_item_ids: list[str]) -> list[SearchProjection]:
        ...

    def list_projection_ids_for_token_prefix(self, user_id: str, token_prefix: str, limit: int) -> list[str]:
        ...

    def list_projection_ids_for_user(self, user_id: str, limit: int) -> list[str]:
        ...

    def delete_projection(self, user_id: str, search_item_id: str) -> bool:
        ...


class SavedSearchViewRepository(Protocol):
    def create_view(self, view: SavedSearchView) -> SavedSearchView:
        ...

    def list_views(self, user_id: str) -> list[SavedSearchView]:
        ...

    def get_view(self, user_id: str, saved_view_id: str) -> SavedSearchView | None:
        ...

    def update_view(self, view: SavedSearchView) -> SavedSearchView | None:
        ...

    def delete_view(self, user_id: str, saved_view_id: str) -> bool:
        ...


class LocalSearchIndexRepository:
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

        if not self.file_path.exists():
            self._write_all_unlocked([])

    def upsert_projection(self, projection: SearchProjection) -> SearchProjection:
        with self._lock:
            projections = [
                item
                for item in self._read_all_unlocked()
                if not (item.user_id == projection.user_id and item.search_item_id == projection.search_item_id)
            ]
            projections.append(projection)
            self._write_all_unlocked(projections)
            return projection

    def get_projection(self, user_id: str, search_item_id: str) -> SearchProjection | None:
        with self._lock:
            return next(
                (
                    projection
                    for projection in self._read_all_unlocked()
                    if projection.user_id == user_id and projection.search_item_id == search_item_id
                ),
                None,
            )

    def batch_get_projections(self, user_id: str, search_item_ids: list[str]) -> list[SearchProjection]:
        requested = set(search_item_ids)
        with self._lock:
            return [
                projection
                for projection in self._read_all_unlocked()
                if projection.user_id == user_id and projection.search_item_id in requested
            ]

    def list_projection_ids_for_token_prefix(self, user_id: str, token_prefix: str, limit: int) -> list[str]:
        normalized_prefix = token_prefix.casefold()
        ids: list[str] = []
        seen: set[str] = set()
        with self._lock:
            for projection in self._read_all_unlocked():
                if projection.user_id != user_id:
                    continue
                if not any(token.startswith(normalized_prefix) for token in projection.normalized_search_tokens):
                    continue
                if projection.search_item_id in seen:
                    continue
                seen.add(projection.search_item_id)
                ids.append(projection.search_item_id)
                if len(ids) >= limit:
                    break
        return ids

    def list_projection_ids_for_user(self, user_id: str, limit: int) -> list[str]:
        with self._lock:
            return [
                projection.search_item_id
                for projection in self._read_all_unlocked()
                if projection.user_id == user_id
            ][:limit]

    def delete_projection(self, user_id: str, search_item_id: str) -> bool:
        with self._lock:
            projections = self._read_all_unlocked()
            next_projections = [
                projection
                for projection in projections
                if not (projection.user_id == user_id and projection.search_item_id == search_item_id)
            ]
            if len(next_projections) == len(projections):
                return False
            self._write_all_unlocked(next_projections)
            return True

    def _read_all_unlocked(self) -> list[SearchProjection]:
        if not self.file_path.exists():
            return []

        raw_data = json.loads(self.file_path.read_text(encoding="utf-8") or "[]")
        return [SearchProjection.model_validate(item) for item in raw_data]

    def _write_all_unlocked(self, projections: list[SearchProjection]) -> None:
        serialized = [projection.model_dump(mode="json") for projection in projections]
        temp_path = self.file_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
        os.replace(temp_path, self.file_path)


class DynamoSearchIndexRepository:
    def __init__(self, table_name: str, region_name: str, table: Any | None = None):
        self.table_name = table_name
        self.region_name = region_name
        self.table = table or self._build_table(table_name, region_name)

    def upsert_projection(self, projection: SearchProjection) -> SearchProjection:
        existing = self.get_projection(projection.user_id, projection.search_item_id)
        if existing is not None:
            self._delete_token_rows(existing)

        self.table.put_item(Item=self._projection_to_item(projection))
        for token in projection.normalized_search_tokens:
            self.table.put_item(Item=self._token_to_item(projection, token))
        return projection

    def get_projection(self, user_id: str, search_item_id: str) -> SearchProjection | None:
        response = self.table.get_item(Key={"user_id": user_id, "search_key": search_projection_key(search_item_id)})
        item = response.get("Item")
        if item is None or item.get("entity_kind") != SEARCH_PROJECTION_KIND:
            return None
        return self._projection_from_item(item)

    def batch_get_projections(self, user_id: str, search_item_ids: list[str]) -> list[SearchProjection]:
        keys = [
            {"user_id": user_id, "search_key": search_projection_key(search_item_id)}
            for search_item_id in dict.fromkeys(search_item_ids)
        ]
        if not keys:
            return []

        if not hasattr(self.table, "meta"):
            return [
                projection
                for search_item_id in search_item_ids
                if (projection := self.get_projection(user_id, search_item_id)) is not None
            ]

        items: list[dict[str, Any]] = []
        for batch_start in range(0, len(keys), 100):
            request_items = {self.table_name: {"Keys": keys[batch_start : batch_start + 100]}}
            while request_items:
                response = self.table.meta.client.batch_get_item(RequestItems=request_items)
                items.extend(response.get("Responses", {}).get(self.table_name, []))
                request_items = response.get("UnprocessedKeys", {})

        projections = [
            self._projection_from_item(item)
            for item in items
            if item.get("entity_kind") == SEARCH_PROJECTION_KIND
        ]
        by_id = {projection.search_item_id: projection for projection in projections}
        return [by_id[search_item_id] for search_item_id in search_item_ids if search_item_id in by_id]

    def list_projection_ids_for_token_prefix(self, user_id: str, token_prefix: str, limit: int) -> list[str]:
        items = self._query_prefix(user_id, f"{SEARCH_TOKEN_PREFIX}{token_prefix}", limit)
        ids: list[str] = []
        seen: set[str] = set()
        for item in items:
            if item.get("entity_kind") != SEARCH_TOKEN_KIND:
                continue
            search_item_id = item.get("search_item_id")
            if not isinstance(search_item_id, str) or search_item_id in seen:
                continue
            seen.add(search_item_id)
            ids.append(search_item_id)
        return ids

    def list_projection_ids_for_user(self, user_id: str, limit: int) -> list[str]:
        items = self._query_prefix(user_id, SEARCH_PROJECTION_PREFIX, limit)
        ids: list[str] = []
        for item in items:
            if item.get("entity_kind") == SEARCH_PROJECTION_KIND and isinstance(item.get("search_item_id"), str):
                ids.append(item["search_item_id"])
        return ids

    def delete_projection(self, user_id: str, search_item_id: str) -> bool:
        existing = self.get_projection(user_id, search_item_id)
        if existing is not None:
            self._delete_token_rows(existing)

        response = self.table.delete_item(
            Key={"user_id": user_id, "search_key": search_projection_key(search_item_id)},
            ReturnValues="ALL_OLD",
        )
        return "Attributes" in response

    def _query_prefix(self, user_id: str, prefix: str, limit: int) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        query_kwargs: dict[str, Any] = {
            "KeyConditionExpression": "user_id = :user_id AND begins_with(search_key, :prefix)",
            "ExpressionAttributeValues": {":user_id": user_id, ":prefix": prefix},
            "Limit": limit,
        }

        while len(items) < limit:
            response = self.table.query(**query_kwargs)
            items.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            query_kwargs["ExclusiveStartKey"] = last_key
            query_kwargs["Limit"] = max(1, limit - len(items))

        return items[:limit]

    def _delete_token_rows(self, projection: SearchProjection) -> None:
        for token in projection.normalized_search_tokens:
            self.table.delete_item(
                Key={
                    "user_id": projection.user_id,
                    "search_key": search_token_key(token, projection.search_item_id),
                }
            )

    def _projection_to_item(self, projection: SearchProjection) -> dict[str, Any]:
        return {
            **projection.model_dump(mode="json"),
            "entity_kind": SEARCH_PROJECTION_KIND,
            "search_key": search_projection_key(projection.search_item_id),
        }

    def _projection_from_item(self, item: dict[str, Any]) -> SearchProjection:
        projection_data = {key: value for key, value in item.items() if key not in {"entity_kind", "search_key"}}
        return SearchProjection.model_validate(projection_data)

    def _token_to_item(self, projection: SearchProjection, token: str) -> dict[str, Any]:
        return {
            "user_id": projection.user_id,
            "search_key": search_token_key(token, projection.search_item_id),
            "entity_kind": SEARCH_TOKEN_KIND,
            "token": token,
            "search_item_id": projection.search_item_id,
            "source_item_type": projection.source_item_type.value,
            "updated_at": projection.updated_at.isoformat(),
            "projection_version": projection.projection_version,
        }

    def _build_table(self, table_name: str, region_name: str) -> Any:
        import boto3

        return boto3.resource("dynamodb", region_name=region_name).Table(table_name)


class LocalSavedSearchViewRepository:
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

        if not self.file_path.exists():
            self._write_all_unlocked([])

    def create_view(self, view: SavedSearchView) -> SavedSearchView:
        with self._lock:
            views = self._read_all_unlocked()
            views.append(view)
            self._write_all_unlocked(views)
            return view

    def list_views(self, user_id: str) -> list[SavedSearchView]:
        with self._lock:
            return [view for view in self._read_all_unlocked() if view.user_id == user_id]

    def get_view(self, user_id: str, saved_view_id: str) -> SavedSearchView | None:
        with self._lock:
            return next(
                (
                    view
                    for view in self._read_all_unlocked()
                    if view.user_id == user_id and view.saved_view_id == saved_view_id
                ),
                None,
            )

    def update_view(self, view: SavedSearchView) -> SavedSearchView | None:
        with self._lock:
            views = self._read_all_unlocked()
            for index, existing in enumerate(views):
                if existing.user_id == view.user_id and existing.saved_view_id == view.saved_view_id:
                    views[index] = view
                    self._write_all_unlocked(views)
                    return view
            return None

    def delete_view(self, user_id: str, saved_view_id: str) -> bool:
        with self._lock:
            views = self._read_all_unlocked()
            next_views = [
                view
                for view in views
                if not (view.user_id == user_id and view.saved_view_id == saved_view_id)
            ]
            if len(next_views) == len(views):
                return False
            self._write_all_unlocked(next_views)
            return True

    def _read_all_unlocked(self) -> list[SavedSearchView]:
        if not self.file_path.exists():
            return []

        raw_data = json.loads(self.file_path.read_text(encoding="utf-8") or "[]")
        return [SavedSearchView.model_validate(item) for item in raw_data]

    def _write_all_unlocked(self, views: list[SavedSearchView]) -> None:
        serialized = [view.model_dump(mode="json") for view in views]
        temp_path = self.file_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
        os.replace(temp_path, self.file_path)


class DynamoSavedSearchViewRepository:
    def __init__(self, table_name: str, region_name: str, table: Any | None = None):
        self.table_name = table_name
        self.region_name = region_name
        self.table = table or self._build_table(table_name, region_name)

    def create_view(self, view: SavedSearchView) -> SavedSearchView:
        self.table.put_item(Item=view.model_dump(mode="json"))
        return view

    def list_views(self, user_id: str) -> list[SavedSearchView]:
        items: list[dict[str, Any]] = []
        query_kwargs: dict[str, Any] = {
            "KeyConditionExpression": "user_id = :user_id",
            "ExpressionAttributeValues": {":user_id": user_id},
        }

        while True:
            response = self.table.query(**query_kwargs)
            items.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            query_kwargs["ExclusiveStartKey"] = last_key

        return [SavedSearchView.model_validate(item) for item in items]

    def get_view(self, user_id: str, saved_view_id: str) -> SavedSearchView | None:
        response = self.table.get_item(Key={"user_id": user_id, "saved_view_id": saved_view_id})
        item = response.get("Item")
        return SavedSearchView.model_validate(item) if item is not None else None

    def update_view(self, view: SavedSearchView) -> SavedSearchView | None:
        try:
            self.table.put_item(
                Item=view.model_dump(mode="json"),
                ConditionExpression="attribute_exists(user_id) AND attribute_exists(saved_view_id)",
            )
        except Exception as exc:
            if self._is_conditional_check_failed(exc):
                return None
            raise
        return view

    def delete_view(self, user_id: str, saved_view_id: str) -> bool:
        response = self.table.delete_item(
            Key={"user_id": user_id, "saved_view_id": saved_view_id},
            ReturnValues="ALL_OLD",
        )
        return "Attributes" in response

    def _build_table(self, table_name: str, region_name: str) -> Any:
        import boto3

        return boto3.resource("dynamodb", region_name=region_name).Table(table_name)

    def _is_conditional_check_failed(self, exc: Exception) -> bool:
        response = getattr(exc, "response", {})
        error = response.get("Error", {}) if isinstance(response, dict) else {}
        return error.get("Code") == "ConditionalCheckFailedException"
