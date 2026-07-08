from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.auth import UserContext, get_current_user
from app.config import load_settings
from app.digest_push import is_digest_due, run_daily_digest_push, was_pushed_today
from app.main import app, get_preferences_repository, get_push_subscription_repository, get_repository
from app.models import PushSubscription, Reminder
from app.preferences import default_digest_preferences
from app.preferences_repository import LocalPreferencesRepository
from app.push_repository import DynamoPushSubscriptionRepository, LocalPushSubscriptionRepository
from app.push_sender import InvalidPushSubscriptionError, PushPayload, PushSendError
from app.repository import LocalReminderRepository


class FakeDynamoTable:
    def __init__(self):
        self.items = {}

    def query(self, **kwargs):
        user_id = kwargs["ExpressionAttributeValues"][":user_id"]
        return {"Items": [item for (item_user_id, _), item in self.items.items() if item_user_id == user_id]}

    def scan(self, **kwargs):
        return {"Items": list(self.items.values())}

    def get_item(self, Key):
        item = self.items.get((Key["user_id"], Key["subscription_id"]))
        return {"Item": item} if item else {}

    def put_item(self, Item):
        self.items[(Item["user_id"], Item["subscription_id"])] = Item
        return {}


class RecordingPushSender:
    def __init__(self, failures=None):
        self.failures = failures or {}
        self.sent: list[tuple[str, PushPayload]] = []

    def send(self, subscription: PushSubscription, payload: PushPayload) -> None:
        failure = self.failures.get(subscription.endpoint)
        if failure:
            raise failure
        self.sent.append((subscription.endpoint, payload))


@pytest.fixture()
def client(tmp_path):
    repo = LocalReminderRepository(tmp_path / "reminders.json")
    preferences_repo = LocalPreferencesRepository(tmp_path / "preferences.json")
    push_repo = LocalPushSubscriptionRepository(tmp_path / "push-subscriptions.json")
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_preferences_repository] = lambda: preferences_repo
    app.dependency_overrides[get_push_subscription_repository] = lambda: push_repo

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def local_repositories(tmp_path):
    return (
        LocalReminderRepository(tmp_path / "reminders.json"),
        LocalPreferencesRepository(tmp_path / "preferences.json"),
        LocalPushSubscriptionRepository(tmp_path / "push-subscriptions.json"),
    )


def set_auth_user(user_id: str):
    app.dependency_overrides[get_current_user] = lambda: UserContext(user_id=user_id)


def push_payload(endpoint="https://push.example/subscription-a"):
    return {
        "endpoint": endpoint,
        "keys": {
            "p256dh": "public-key",
            "auth": "auth-secret",
        },
        "user_agent": "pytest-browser",
    }


def create_subscription(user_id: str, endpoint: str, now: datetime | None = None) -> PushSubscription:
    from app.push_repository import push_subscription_id_for_endpoint

    resolved_now = now or datetime(2026, 7, 8, 13, tzinfo=timezone.utc)
    return PushSubscription(
        user_id=user_id,
        subscription_id=push_subscription_id_for_endpoint(endpoint),
        endpoint=endpoint,
        p256dh="public-key",
        auth="auth-secret",
        user_agent="pytest-browser",
        created_at=resolved_now,
        updated_at=resolved_now,
    )


def create_reminder(user_id: str, due_date: date, title="Reminder") -> Reminder:
    now = datetime(2026, 7, 8, 13, tzinfo=timezone.utc)
    return Reminder(
        id=f"{user_id}-{title}",
        user_id=user_id,
        title=title,
        category="Other",
        due_date=due_date,
        repeat="None",
        priority="Medium",
        notes="private note not for push",
        completed=False,
        created_at=now,
        updated_at=now,
        completed_at=None,
    )


def push_settings():
    return load_settings(
        {
            "VAPID_PUBLIC_KEY": "public-key",
            "VAPID_PRIVATE_KEY": "private-key",
            "VAPID_SUBJECT": "mailto:test@example.com",
        }
    )


def test_push_config_reports_missing_when_vapid_not_configured(client):
    response = client.get("/push/config")

    assert response.status_code == 200
    assert response.json() == {"configured": False}


def test_push_subscription_routes_are_user_scoped(client):
    set_auth_user("user-a")
    created = client.post("/push/subscriptions", json=push_payload())
    assert created.status_code == 200
    body = created.json()
    assert body["endpoint"] == "https://push.example/subscription-a"
    assert "user_id" not in body
    assert "keys" not in body

    set_auth_user("user-b")
    assert client.get("/push/subscriptions").json() == []
    assert client.delete(f"/push/subscriptions/{body['subscription_id']}").status_code == 404

    set_auth_user("user-a")
    assert [item["subscription_id"] for item in client.get("/push/subscriptions").json()] == [body["subscription_id"]]
    assert client.delete(f"/push/subscriptions/{body['subscription_id']}").status_code == 204
    assert client.get("/push/subscriptions").json() == []


def test_push_subscription_upserts_by_endpoint_for_same_user(client):
    set_auth_user("user-a")
    first = client.post("/push/subscriptions", json=push_payload()).json()
    second = client.post(
        "/push/subscriptions",
        json=push_payload(endpoint="https://push.example/subscription-a") | {"keys": {"p256dh": "rotated", "auth": "rotated-auth"}},
    ).json()

    assert first["subscription_id"] == second["subscription_id"]
    assert len(client.get("/push/subscriptions").json()) == 1


def test_same_endpoint_does_not_cross_users(client):
    endpoint = "https://push.example/shared-endpoint"
    set_auth_user("user-a")
    user_a = client.post("/push/subscriptions", json=push_payload(endpoint=endpoint)).json()

    set_auth_user("user-b")
    user_b = client.post("/push/subscriptions", json=push_payload(endpoint=endpoint)).json()

    assert user_a["subscription_id"] == user_b["subscription_id"]
    assert len(client.get("/push/subscriptions").json()) == 1

    set_auth_user("user-a")
    assert len(client.get("/push/subscriptions").json()) == 1


def test_push_subscription_rejects_frontend_user_id(client):
    response = client.post("/push/subscriptions", json=push_payload() | {"user_id": "attacker"})

    assert response.status_code == 422


def test_old_user_without_push_subscriptions_still_gets_empty_list(client):
    response = client.get("/push/subscriptions")

    assert response.status_code == 200
    assert response.json() == []


def test_local_json_push_repository_persists_subscriptions(tmp_path):
    data_file = tmp_path / "push-subscriptions.json"
    first_repo = LocalPushSubscriptionRepository(data_file)
    subscription = create_subscription("user-a", "https://push.example/a")

    first_repo.save_subscription(subscription)
    second_repo = LocalPushSubscriptionRepository(data_file)

    assert second_repo.get_subscription("user-a", subscription.subscription_id) == subscription
    assert second_repo.get_subscription("user-b", subscription.subscription_id) is None


def test_dynamo_push_repository_persists_subscriptions_by_user():
    table = FakeDynamoTable()
    repo = DynamoPushSubscriptionRepository("push", "us-east-1", table=table)
    subscription = create_subscription("user-a", "https://push.example/a")

    repo.save_subscription(subscription)

    assert repo.get_subscription("user-a", subscription.subscription_id) == subscription
    assert repo.get_subscription("user-b", subscription.subscription_id) is None
    assert repo.list_user_ids_with_active_subscriptions() == ["user-a"]


def test_digest_push_due_window_uses_user_timezone():
    preferences = default_digest_preferences("user-a").model_copy(
        update={"digest_time": "09:00", "timezone": "America/New_York"}
    )
    local_now = datetime(2026, 7, 8, 9, 5, tzinfo=timezone(timedelta(hours=-4)))

    assert is_digest_due(preferences, local_now, 15) is True


def test_digest_push_duplicate_prevention_uses_user_local_day():
    preferences = default_digest_preferences("user-a").model_copy(
        update={
            "digest_time": "09:00",
            "timezone": "America/New_York",
            "digest_last_pushed_at": datetime(2026, 7, 8, 13, 0, tzinfo=timezone.utc),
        }
    )
    local_now = datetime(2026, 7, 8, 9, 5, tzinfo=timezone(timedelta(hours=-4)))

    assert was_pushed_today(preferences, local_now) is True


def test_scheduled_digest_push_sends_user_scoped_summaries(local_repositories):
    reminder_repo, preferences_repo, push_repo = local_repositories
    now = datetime(2026, 7, 8, 13, 5, tzinfo=timezone.utc)
    local_today = date(2026, 7, 8)
    preferences_repo.save_preferences(
        default_digest_preferences("user-a", now).model_copy(update={"digest_time": "13:00", "timezone": "UTC"})
    )
    preferences_repo.save_preferences(
        default_digest_preferences("user-b", now).model_copy(update={"digest_time": "13:00", "timezone": "UTC"})
    )
    reminder_repo.create_reminder(create_reminder("user-a", local_today, "A due today"))
    reminder_repo.create_reminder(create_reminder("user-b", local_today + timedelta(days=3), "B coming up"))
    push_repo.save_subscription(create_subscription("user-a", "https://push.example/a", now))
    push_repo.save_subscription(create_subscription("user-b", "https://push.example/b", now))
    sender = RecordingPushSender()

    result = run_daily_digest_push(
        now=now,
        settings=push_settings(),
        reminder_repository=reminder_repo,
        preferences_repository=preferences_repo,
        push_repository=push_repo,
        sender=sender,
    )

    bodies = {endpoint: payload.body for endpoint, payload in sender.sent}
    assert result.sent == 2
    assert bodies["https://push.example/a"] == "1 needs attention \u2022 0 due today \u2022 0 coming up"
    assert bodies["https://push.example/b"] == "0 needs attention \u2022 0 due today \u2022 1 coming up"


def test_scheduled_digest_push_skips_empty_digest(local_repositories):
    reminder_repo, preferences_repo, push_repo = local_repositories
    now = datetime(2026, 7, 8, 13, 5, tzinfo=timezone.utc)
    preferences_repo.save_preferences(
        default_digest_preferences("user-a", now).model_copy(update={"digest_time": "13:00", "timezone": "UTC"})
    )
    push_repo.save_subscription(create_subscription("user-a", "https://push.example/a", now))
    sender = RecordingPushSender()

    result = run_daily_digest_push(
        now=now,
        settings=push_settings(),
        reminder_repository=reminder_repo,
        preferences_repository=preferences_repo,
        push_repository=push_repo,
        sender=sender,
    )

    assert result.sent == 0
    assert result.skipped_empty_digest == 1
    assert sender.sent == []


def test_scheduled_digest_push_prevents_duplicate_same_local_day(local_repositories):
    reminder_repo, preferences_repo, push_repo = local_repositories
    now = datetime(2026, 7, 8, 13, 5, tzinfo=timezone.utc)
    preferences_repo.save_preferences(
        default_digest_preferences("user-a", now).model_copy(
            update={
                "digest_time": "13:00",
                "timezone": "UTC",
                "digest_last_pushed_at": datetime(2026, 7, 8, 13, 0, tzinfo=timezone.utc),
            }
        )
    )
    reminder_repo.create_reminder(create_reminder("user-a", date(2026, 7, 8)))
    push_repo.save_subscription(create_subscription("user-a", "https://push.example/a", now))
    sender = RecordingPushSender()

    result = run_daily_digest_push(
        now=now,
        settings=push_settings(),
        reminder_repository=reminder_repo,
        preferences_repository=preferences_repo,
        push_repository=push_repo,
        sender=sender,
    )

    assert result.sent == 0
    assert result.skipped_duplicate == 1


def test_scheduled_digest_failure_for_one_user_does_not_stop_other_user(local_repositories):
    reminder_repo, preferences_repo, push_repo = local_repositories
    now = datetime(2026, 7, 8, 13, 5, tzinfo=timezone.utc)
    for user_id in ["user-a", "user-b"]:
        preferences_repo.save_preferences(
            default_digest_preferences(user_id, now).model_copy(update={"digest_time": "13:00", "timezone": "UTC"})
        )
        reminder_repo.create_reminder(create_reminder(user_id, date(2026, 7, 8), user_id))
    push_repo.save_subscription(create_subscription("user-a", "https://push.example/a", now))
    push_repo.save_subscription(create_subscription("user-b", "https://push.example/b", now))
    sender = RecordingPushSender(failures={"https://push.example/a": PushSendError("temporary")})

    result = run_daily_digest_push(
        now=now,
        settings=push_settings(),
        reminder_repository=reminder_repo,
        preferences_repository=preferences_repo,
        push_repository=push_repo,
        sender=sender,
    )

    assert result.failed == 1
    assert result.sent == 1
    assert sender.sent[0][0] == "https://push.example/b"
    assert preferences_repo.get_preferences("user-a").digest_last_pushed_at is None
    assert preferences_repo.get_preferences("user-b").digest_last_pushed_at == now


def test_invalid_subscription_failure_disables_only_that_subscription(local_repositories):
    reminder_repo, preferences_repo, push_repo = local_repositories
    now = datetime(2026, 7, 8, 13, 5, tzinfo=timezone.utc)
    preferences_repo.save_preferences(
        default_digest_preferences("user-a", now).model_copy(update={"digest_time": "13:00", "timezone": "UTC"})
    )
    reminder_repo.create_reminder(create_reminder("user-a", date(2026, 7, 8)))
    invalid = create_subscription("user-a", "https://push.example/invalid", now)
    valid = create_subscription("user-a", "https://push.example/valid", now)
    push_repo.save_subscription(invalid)
    push_repo.save_subscription(valid)
    sender = RecordingPushSender(failures={"https://push.example/invalid": InvalidPushSubscriptionError("gone")})

    result = run_daily_digest_push(
        now=now,
        settings=push_settings(),
        reminder_repository=reminder_repo,
        preferences_repository=preferences_repo,
        push_repository=push_repo,
        sender=sender,
    )

    assert result.disabled_invalid == 1
    assert result.sent == 1
    assert push_repo.get_subscription("user-a", invalid.subscription_id).disabled_at == now
    assert push_repo.get_subscription("user-a", valid.subscription_id).disabled_at is None
