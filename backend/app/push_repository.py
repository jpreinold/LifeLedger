import hashlib
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from app.models import PushSubscription


class PushSubscriptionRepository(Protocol):
    def list_subscriptions(self, user_id: str, include_disabled: bool = False) -> list[PushSubscription]:
        ...

    def list_user_ids_with_active_subscriptions(self) -> list[str]:
        ...

    def get_subscription(self, user_id: str, subscription_id: str) -> PushSubscription | None:
        ...

    def get_subscription_by_endpoint(self, user_id: str, endpoint: str) -> PushSubscription | None:
        ...

    def save_subscription(self, subscription: PushSubscription) -> PushSubscription:
        ...

    def disable_subscription(self, user_id: str, subscription_id: str, disabled_at: datetime) -> bool:
        ...

    def delete_subscription(self, user_id: str, subscription_id: str) -> bool:
        ...

    def delete_for_user(self, user_id: str, limit: int = 100) -> int:
        ...


class LocalPushSubscriptionRepository:
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

        if not self.file_path.exists():
            self._write_all_unlocked([])

    def list_subscriptions(self, user_id: str, include_disabled: bool = False) -> list[PushSubscription]:
        with self._lock:
            return [
                subscription
                for subscription in self._read_all_unlocked()
                if subscription.user_id == user_id and (include_disabled or subscription.disabled_at is None)
            ]

    def list_user_ids_with_active_subscriptions(self) -> list[str]:
        with self._lock:
            return sorted(
                {
                    subscription.user_id
                    for subscription in self._read_all_unlocked()
                    if subscription.disabled_at is None
                }
            )

    def get_subscription(self, user_id: str, subscription_id: str) -> PushSubscription | None:
        with self._lock:
            return next(
                (
                    subscription
                    for subscription in self._read_all_unlocked()
                    if subscription.user_id == user_id and subscription.subscription_id == subscription_id
                ),
                None,
            )

    def get_subscription_by_endpoint(self, user_id: str, endpoint: str) -> PushSubscription | None:
        with self._lock:
            return next(
                (
                    subscription
                    for subscription in self._read_all_unlocked()
                    if subscription.user_id == user_id and subscription.endpoint == endpoint
                ),
                None,
            )

    def save_subscription(self, subscription: PushSubscription) -> PushSubscription:
        with self._lock:
            subscriptions = self._read_all_unlocked()
            for index, existing in enumerate(subscriptions):
                if existing.user_id == subscription.user_id and existing.subscription_id == subscription.subscription_id:
                    subscriptions[index] = subscription
                    self._write_all_unlocked(subscriptions)
                    return subscription

            subscriptions.append(subscription)
            self._write_all_unlocked(subscriptions)
            return subscription

    def disable_subscription(self, user_id: str, subscription_id: str, disabled_at: datetime) -> bool:
        with self._lock:
            subscription = self.get_subscription(user_id, subscription_id)
            if subscription is None:
                return False

            self.save_subscription(subscription.model_copy(update={"disabled_at": disabled_at, "updated_at": disabled_at}))
            return True

    def delete_subscription(self, user_id: str, subscription_id: str) -> bool:
        with self._lock:
            subscriptions = self._read_all_unlocked()
            remaining = [
                item
                for item in subscriptions
                if not (item.user_id == user_id and item.subscription_id == subscription_id)
            ]
            if len(remaining) == len(subscriptions):
                return False
            self._write_all_unlocked(remaining)
            return True

    def delete_for_user(self, user_id: str, limit: int = 100) -> int:
        subscriptions = self.list_subscriptions(user_id, include_disabled=True)[:limit]
        for subscription in subscriptions:
            self.delete_subscription(user_id, subscription.subscription_id)
        return len(subscriptions)

    def _read_all_unlocked(self) -> list[PushSubscription]:
        if not self.file_path.exists():
            return []

        raw_data = json.loads(self.file_path.read_text(encoding="utf-8") or "[]")
        return [PushSubscription.model_validate(item) for item in raw_data]

    def _write_all_unlocked(self, subscriptions: list[PushSubscription]) -> None:
        serialized = [subscription.model_dump(mode="json") for subscription in subscriptions]
        temp_path = self.file_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
        os.replace(temp_path, self.file_path)


class DynamoPushSubscriptionRepository:
    def __init__(self, table_name: str, region_name: str, table: Any | None = None):
        self.table_name = table_name
        self.region_name = region_name
        self.table = table or self._build_table(table_name, region_name)

    def list_subscriptions(self, user_id: str, include_disabled: bool = False) -> list[PushSubscription]:
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

        subscriptions = [self._from_item(item) for item in items]
        if include_disabled:
            return subscriptions

        return [subscription for subscription in subscriptions if subscription.disabled_at is None]

    def list_user_ids_with_active_subscriptions(self) -> list[str]:
        items: list[dict[str, Any]] = []
        scan_kwargs: dict[str, Any] = {}

        while True:
            response = self.table.scan(**scan_kwargs)
            items.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_kwargs["ExclusiveStartKey"] = last_key

        return sorted(
            {
                item["user_id"]
                for item in items
                if item.get("user_id") and not item.get("disabled_at")
            }
        )

    def get_subscription(self, user_id: str, subscription_id: str) -> PushSubscription | None:
        response = self.table.get_item(Key={"user_id": user_id, "subscription_id": subscription_id})
        item = response.get("Item")
        if item is None:
            return None

        return self._from_item(item)

    def get_subscription_by_endpoint(self, user_id: str, endpoint: str) -> PushSubscription | None:
        return next(
            (subscription for subscription in self.list_subscriptions(user_id, include_disabled=True) if subscription.endpoint == endpoint),
            None,
        )

    def save_subscription(self, subscription: PushSubscription) -> PushSubscription:
        self.table.put_item(Item=self._to_item(subscription))
        return subscription

    def disable_subscription(self, user_id: str, subscription_id: str, disabled_at: datetime) -> bool:
        subscription = self.get_subscription(user_id, subscription_id)
        if subscription is None:
            return False

        self.save_subscription(subscription.model_copy(update={"disabled_at": disabled_at, "updated_at": disabled_at}))
        return True

    def delete_subscription(self, user_id: str, subscription_id: str) -> bool:
        self.table.delete_item(Key={"user_id": user_id, "subscription_id": subscription_id})
        return True

    def delete_for_user(self, user_id: str, limit: int = 100) -> int:
        subscriptions = self.list_subscriptions(user_id, include_disabled=True)[:limit]
        for subscription in subscriptions:
            self.delete_subscription(user_id, subscription.subscription_id)
        return len(subscriptions)

    def _build_table(self, table_name: str, region_name: str) -> Any:
        import boto3

        return boto3.resource("dynamodb", region_name=region_name).Table(table_name)

    def _to_item(self, subscription: PushSubscription) -> dict[str, Any]:
        return subscription.model_dump(mode="json")

    def _from_item(self, item: dict[str, Any]) -> PushSubscription:
        return PushSubscription.model_validate(item)


def push_subscription_id_for_endpoint(endpoint: str) -> str:
    return f"ps_{hashlib.sha256(endpoint.encode('utf-8')).hexdigest()[:32]}"
