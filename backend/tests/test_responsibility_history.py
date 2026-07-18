from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.auth import UserContext, get_current_user
from app.linked_items_repository import LocalLinkedItemRepository
from app.main import app, get_linked_item_repository, get_preferences_repository, get_record_repository, get_repository
from app.models import Reminder, ResponsibilityEvent
from app.preferences_repository import LocalPreferencesRepository
from app.records_repository import LocalRecordRepository
from app.repository import LocalReminderRepository
from app.recurrence import advance_due_date
from app.responsibility_history_repository import (
    DynamoResponsibilityHistoryRepository,
    LifecycleWriteConflict,
    LocalResponsibilityHistoryRepository,
)
from app.schemas import ReminderCategory, RepeatOption, ResponsibilityEventSource, ResponsibilityEventType


@pytest.fixture()
def client(tmp_path):
    reminder_repo = LocalReminderRepository(tmp_path / "reminders.json")
    app.dependency_overrides[get_repository] = lambda: reminder_repo
    app.dependency_overrides[get_preferences_repository] = lambda: LocalPreferencesRepository(tmp_path / "preferences.json")
    app.dependency_overrides[get_record_repository] = lambda: LocalRecordRepository(tmp_path / "records.json")
    app.dependency_overrides[get_linked_item_repository] = lambda: LocalLinkedItemRepository(tmp_path / "links.json")
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_reminder(client: TestClient, **overrides):
    payload = {
        "title": "Annual responsibility",
        "category": "Other",
        "due_date": (date.today() + timedelta(days=60)).isoformat(),
        "repeat": "None",
        "priority": "High",
        "notes": None,
    }
    payload.update(overrides)
    response = client.post("/reminders", json=payload)
    assert response.status_code == 201
    return response.json()


def history(client: TestClient, reminder_id: str, **params):
    response = client.get(f"/reminders/{reminder_id}/history", params=params)
    assert response.status_code == 200
    return response.json()


def test_completion_is_durable_private_and_idempotent(client, caplog):
    created = create_reminder(client)
    operation = {"Idempotency-Key": "complete-cycle-2026"}
    payload = {
        "completed_on": date.today().isoformat(),
        "occurrence_id": created["current_occurrence_id"],
        "note": "private completion context",
    }

    with caplog.at_level("INFO"):
        first = client.post(f"/reminders/{created['id']}/complete", json=payload, headers=operation)
        second = client.post(f"/reminders/{created['id']}/complete", json=payload, headers=operation)

    assert first.status_code == second.status_code == 200
    entries = history(client, created["id"])["items"]
    completed = [event for event in entries if event["event_type"] == "completed"]
    assert len(completed) == 1
    assert completed[0]["effective_date"] == date.today().isoformat()
    assert completed[0]["note"] == "private completion context"
    assert "private completion context" not in caplog.text
    assert "document_number" not in completed[0]


def test_recurring_completion_advances_to_distinct_occurrence(client):
    previous_due = date.today() + timedelta(days=10)
    expected_due = advance_due_date(previous_due, RepeatOption.MONTHLY, today=date.today())
    created = create_reminder(client, due_date=previous_due.isoformat(), repeat="Monthly")
    response = client.post(
        f"/reminders/{created['id']}/complete",
        json={"completed_on": date.today().isoformat(), "occurrence_id": created["current_occurrence_id"]},
        headers={"Idempotency-Key": "july-completion"},
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["completed"] is False
    assert updated["due_date"] == expected_due.isoformat()
    assert updated["current_occurrence_id"] != created["current_occurrence_id"]
    event = history(client, created["id"])["items"][0]
    assert event["occurrence_id"] == created["current_occurrence_id"]
    assert event["next_due_date"] == expected_due.isoformat()


def test_lifecycle_effective_dates_reject_future_actions(client):
    created = create_reminder(client, repeat="Yearly")
    future = (date.today() + timedelta(days=1)).isoformat()
    assert client.post(
        f"/reminders/{created['id']}/complete",
        json={"completed_on": future, "occurrence_id": created["current_occurrence_id"]},
    ).status_code == 422
    assert client.post(
        f"/reminders/{created['id']}/renew",
        json={"renewed_on": future, "new_due_date": (date.today() + timedelta(days=365)).isoformat()},
    ).status_code == 422
    assert [event["event_type"] for event in history(client, created["id"])["items"]] == ["responsibility_created"]


def test_due_date_change_and_reopen_preserve_distinct_events(client):
    created = create_reminder(client)
    previous_due_date = created["due_date"]
    changed_due_date = (date.today() + timedelta(days=75)).isoformat()
    changed_payload = {
        "title": created["title"],
        "category": created["category"],
        "due_date": changed_due_date,
        "repeat": created["repeat"],
        "priority": created["priority"],
        "notes": created["notes"],
    }
    changed = client.put(f"/reminders/{created['id']}", json=changed_payload)
    assert changed.status_code == 200
    changed_body = changed.json()
    completed = client.post(
        f"/reminders/{created['id']}/complete",
        json={"completed_on": date.today().isoformat(), "occurrence_id": changed_body["current_occurrence_id"]},
    )
    assert completed.status_code == 200
    reopened = client.post(
        f"/reminders/{created['id']}/reopen",
        params={"occurrence_id": completed.json()["current_occurrence_id"]},
    )
    assert reopened.status_code == 200
    recompleted = client.post(
        f"/reminders/{created['id']}/complete",
        json={"completed_on": date.today().isoformat(), "occurrence_id": reopened.json()["current_occurrence_id"]},
    )
    assert recompleted.status_code == 200

    entries = history(client, created["id"])["items"]
    assert [event["event_type"] for event in entries[:4]] == ["completed", "reopened", "completed", "due_date_changed"]
    assert entries[0]["occurrence_id"] != entries[2]["occurrence_id"]
    changed_event = entries[3]
    assert changed_event["previous_due_date"] == previous_due_date
    assert changed_event["next_due_date"] == changed_due_date


def test_history_pagination_is_stable_and_newest_first(client):
    created = create_reminder(client)
    for index in range(3):
        snoozed_until = datetime(2026, 9, 20 + index, 12, tzinfo=timezone.utc).isoformat()
        assert client.post(
            f"/reminders/{created['id']}/snooze",
            json={"snoozed_until": snoozed_until},
            headers={"Idempotency-Key": f"snooze-{index}"},
        ).status_code == 200
        assert client.post(
            f"/reminders/{created['id']}/snooze/clear",
            headers={"Idempotency-Key": f"clear-{index}"},
        ).status_code == 200

    first = history(client, created["id"], limit=3)
    second = history(client, created["id"], limit=3, cursor=first["next_cursor"])
    third = history(client, created["id"], limit=3, cursor=second["next_cursor"])
    event_ids = [event["event_id"] for page in (first, second, third) for event in page["items"]]
    assert len(event_ids) == len(set(event_ids)) == 7
    occurred = [event["occurred_at"] for page in (first, second, third) for event in page["items"]]
    assert occurred == sorted(occurred, reverse=True)


def test_history_and_event_reads_are_user_scoped(client):
    created = create_reminder(client)
    event_id = history(client, created["id"])["items"][0]["event_id"]
    app.dependency_overrides[get_current_user] = lambda: UserContext(user_id="another-user")

    assert client.get(f"/reminders/{created['id']}/history").status_code == 404
    assert client.get(f"/responsibility-events/{event_id}").status_code == 404


def test_item_activity_aggregates_connected_workflow_and_syncs_registry_date(client):
    previous_due_date = date.today() + timedelta(days=100)
    next_due_date = date.today() + timedelta(days=465)
    item = client.post(
        "/records",
        json={"record_type": "vehicle", "title": "Test vehicle", "category": "Vehicles"},
    ).json()
    created = client.post(
        "/reminders",
        params={"item_id": item["id"]},
        json={
            "title": "Renew registration",
            "category": "Car",
            "due_date": previous_due_date.isoformat(),
            "repeat": "Yearly",
            "priority": "High",
            "workflow_id": "vehicle_registration",
            "reminder_type": "renewal",
            "renewal_details": {
                "item_name": "Test vehicle",
                "renewal_kind": "expiration",
                "expiration_date": previous_due_date.isoformat(),
                "frequency": "Yearly",
            },
        },
    ).json()
    assert client.post(
        f"/records/{item['id']}/links",
        json={"target_type": "reminder", "target_id": created["id"], "relationship_type": "renews"},
    ).status_code == 201
    renewed = client.post(
        f"/reminders/{created['id']}/renew",
        json={
            "new_due_date": next_due_date.isoformat(),
            "renewed_on": date.today().isoformat(),
            "occurrence_id": created["current_occurrence_id"],
        },
    )
    assert renewed.status_code == 200

    activity = client.get(f"/records/{item['id']}/activity").json()["items"]
    assert [event["event_type"] for event in activity] == ["renewed", "responsibility_created"]
    updated_item = client.get(f"/records/{item['id']}").json()
    registration_fields = [field for field in updated_item["dynamic_fields"] if field["key"] == "registration_expiration"]
    assert len(registration_fields) == 1
    assert registration_fields[0]["value"] == next_due_date.isoformat()


def test_reconciliation_does_not_infer_missing_history(client):
    created = create_reminder(client)
    first = client.post(f"/reminders/{created['id']}/history/reconcile", params={"dry_run": True})
    second = client.post(f"/reminders/{created['id']}/history/reconcile")
    assert first.status_code == second.status_code == 200
    assert first.json()["inspected"] == 0
    assert second.json()["repaired"] == 0
    assert [event["event_type"] for event in history(client, created["id"])["items"]] == ["responsibility_created"]


def test_user_reconciliation_is_paginated_and_idempotent(client):
    reminder_ids = sorted(create_reminder(client, title=f"Responsibility {index}")["id"] for index in range(3))
    first = client.post("/responsibility-history/reconcile", params={"dry_run": True, "limit": 2})
    assert first.status_code == 200
    assert [item["reminder_id"] for item in first.json()["items"]] == reminder_ids[:2]
    second = client.post(
        "/responsibility-history/reconcile",
        params={"limit": 2, "cursor": first.json()["next_cursor"]},
    )
    assert second.status_code == 200
    assert [item["reminder_id"] for item in second.json()["items"]] == reminder_ids[2:]
    assert all(item["repaired"] == 0 for item in first.json()["items"] + second.json()["items"])


def test_reminder_deletion_removes_history(client):
    created = create_reminder(client)
    event_id = history(client, created["id"])["items"][0]["event_id"]
    assert client.delete(f"/reminders/{created['id']}").status_code == 204
    assert client.get(f"/responsibility-events/{event_id}").status_code == 404


def test_local_atomic_write_rolls_back_reminder_when_event_append_fails(tmp_path):
    reminder_repo = LocalReminderRepository(tmp_path / "reminders.json")
    history_repo = LocalResponsibilityHistoryRepository(tmp_path / "history.json")
    now = datetime.now(timezone.utc)
    previous = Reminder(
        id="reminder-1",
        user_id="user-1",
        title="Atomic test",
        category=ReminderCategory.OTHER,
        due_date=date(2026, 9, 18),
        repeat=RepeatOption.NONE,
        priority="High",
        created_at=now,
        updated_at=now,
    )
    reminder_repo.create_reminder(previous)
    updated = previous.model_copy(update={"completed": True, "version": 1})
    event = ResponsibilityEvent(
        event_id="event-1",
        user_id="user-1",
        reminder_id="reminder-1",
        event_type=ResponsibilityEventType.COMPLETED,
        occurred_at=now,
        source=ResponsibilityEventSource.USER,
        idempotency_key="complete:atomic",
        correlation_id="atomic",
        created_at=now,
    )

    original_append = history_repo.append_event
    history_repo.append_event = lambda _event: (_ for _ in ()).throw(RuntimeError("simulated history failure"))  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="simulated history failure"):
        history_repo.commit_reminder_event(reminder_repo, previous, updated, event)
    history_repo.append_event = original_append  # type: ignore[method-assign]

    assert reminder_repo.get_reminder("user-1", "reminder-1") == previous
    assert history_repo.list_for_reminder("user-1", "reminder-1")[0] == []


def test_dynamo_lifecycle_write_uses_one_versioned_transaction(tmp_path):
    class FakeTable:
        def get_item(self, **_kwargs):
            return {}

    class FakeClient:
        def __init__(self):
            self.transaction = None

        def transact_write_items(self, **kwargs):
            self.transaction = kwargs

    reminder_repo = LocalReminderRepository(tmp_path / "reminders.json")
    now = datetime.now(timezone.utc)
    previous = Reminder(
        id="reminder-dynamo",
        user_id="user-dynamo",
        title="Transaction test",
        category=ReminderCategory.OTHER,
        due_date=date(2026, 9, 18),
        repeat=RepeatOption.NONE,
        priority="High",
        created_at=now,
        updated_at=now,
        version=4,
    )
    updated = previous.model_copy(update={"completed": True, "version": 5})
    event = ResponsibilityEvent(
        event_id="event-dynamo",
        user_id=previous.user_id,
        reminder_id=previous.id,
        event_type=ResponsibilityEventType.COMPLETED,
        occurred_at=now,
        source=ResponsibilityEventSource.USER,
        idempotency_key="complete:dynamo",
        correlation_id="dynamo",
        created_at=now,
    )
    client = FakeClient()
    history_repo = DynamoResponsibilityHistoryRepository(
        "history-table",
        "reminder-table",
        "us-east-1",
        table=FakeTable(),
        client=client,
    )

    assert history_repo.commit_reminder_event(reminder_repo, previous, updated, event) == updated
    writes = client.transaction["TransactItems"]
    assert len(writes) == 2
    assert writes[0]["Put"]["ConditionExpression"] == "attribute_exists(user_id) AND (attribute_not_exists(#version) OR #version = :expected)"
    assert writes[1]["Put"]["ConditionExpression"] == "attribute_not_exists(user_id) AND attribute_not_exists(event_id)"


def test_failed_dynamo_transaction_reports_conflict_without_local_mutation(tmp_path):
    class EmptyTable:
        def get_item(self, **_kwargs):
            return {}

    class FailingClient:
        def transact_write_items(self, **_kwargs):
            raise RuntimeError("transaction cancelled")

    reminder_repo = LocalReminderRepository(tmp_path / "reminders.json")
    now = datetime.now(timezone.utc)
    previous = Reminder(
        id="reminder-conflict",
        user_id="user-conflict",
        title="Conflict test",
        category=ReminderCategory.OTHER,
        due_date=date(2026, 9, 18),
        repeat=RepeatOption.NONE,
        priority="High",
        created_at=now,
        updated_at=now,
    )
    reminder_repo.create_reminder(previous)
    event = ResponsibilityEvent(
        event_id="event-conflict",
        user_id=previous.user_id,
        reminder_id=previous.id,
        event_type=ResponsibilityEventType.COMPLETED,
        occurred_at=now,
        source=ResponsibilityEventSource.USER,
        idempotency_key="complete:conflict",
        correlation_id="conflict",
        created_at=now,
    )
    history_repo = DynamoResponsibilityHistoryRepository(
        "history-table", "reminder-table", "us-east-1", table=EmptyTable(), client=FailingClient()
    )

    with pytest.raises(LifecycleWriteConflict):
        history_repo.commit_reminder_event(
            reminder_repo,
            previous,
            previous.model_copy(update={"completed": True, "version": 1}),
            event,
        )
    assert reminder_repo.get_reminder(previous.user_id, previous.id) == previous
