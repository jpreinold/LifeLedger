from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_repository
from app.repository import LocalReminderRepository


@pytest.fixture()
def client(tmp_path):
    repo = LocalReminderRepository(tmp_path / "reminders.json")
    app.dependency_overrides[get_repository] = lambda: repo

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def make_payload(**overrides):
    payload = {
        "title": "Renew car tag",
        "category": "Car",
        "due_date": date.today().isoformat(),
        "repeat": "None",
        "priority": "High",
        "notes": "Bring registration paperwork.",
    }
    payload.update(overrides)
    return payload


def create_reminder(client: TestClient, **overrides):
    response = client.post("/reminders", json=make_payload(**overrides))
    assert response.status_code == 201
    return response.json()


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_cloudflare_frontend(client):
    response = client.get("/reminders", headers={"Origin": "https://lifeledger.jpreinold.com"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://lifeledger.jpreinold.com"


def test_cors_preflight_allows_cloudflare_frontend(client):
    response = client.options(
        "/reminders",
        headers={
            "Origin": "https://lifeledger.jpreinold.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://lifeledger.jpreinold.com"
    assert "GET" in response.headers["access-control-allow-methods"]


def test_create_and_fetch_reminder(client):
    created = create_reminder(client)

    list_response = client.get("/reminders")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = client.get(f"/reminders/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Renew car tag"


def test_update_reminder(client):
    created = create_reminder(client)

    response = client.put(
        f"/reminders/{created['id']}",
        json={
            "title": "Renew vehicle registration",
            "category": "Car",
            "due_date": (date.today() + timedelta(days=30)).isoformat(),
            "repeat": "Yearly",
            "priority": "Medium",
            "notes": None,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["title"] == "Renew vehicle registration"
    assert body["repeat"] == "Yearly"
    assert body["notes"] is None
    assert body["next_due_date"] is not None


def test_create_validates_required_fields(client):
    response = client.post("/reminders", json=make_payload(title=" "))

    assert response.status_code == 422


def test_delete_reminder(client):
    created = create_reminder(client)

    delete_response = client.delete(f"/reminders/{created['id']}")
    assert delete_response.status_code == 204

    get_response = client.get(f"/reminders/{created['id']}")
    assert get_response.status_code == 404


def test_local_json_repository_persists_across_instances(tmp_path):
    data_file = tmp_path / "reminders.json"
    first_repo = LocalReminderRepository(data_file)
    now = date.today()

    created = create_reminder_model(now)
    first_repo.create_reminder(created)

    second_repo = LocalReminderRepository(data_file)
    loaded = second_repo.get_reminder(created.id)

    assert loaded is not None
    assert loaded.id == created.id
    assert loaded.title == "Repository persistence check"


def test_complete_non_recurring_reminder(client):
    created = create_reminder(client, repeat="None")

    complete_response = client.post(f"/reminders/{created['id']}/complete")
    body = complete_response.json()

    assert complete_response.status_code == 200
    assert body["completed"] is True
    assert body["completed_at"] is not None
    assert body["status"] == "Completed"


def test_complete_recurring_reminder_advances_due_date(client):
    yesterday = date.today() - timedelta(days=1)
    created = create_reminder(client, due_date=yesterday.isoformat(), repeat="Weekly")

    complete_response = client.post(f"/reminders/{created['id']}/complete")
    body = complete_response.json()

    assert complete_response.status_code == 200
    assert body["completed"] is False
    assert body["completed_at"] is not None
    assert date.fromisoformat(body["due_date"]) > date.today()


@pytest.mark.parametrize(
    ("due_date", "expected_status"),
    [
        (date.today() - timedelta(days=1), "Overdue"),
        (date.today(), "Due today"),
        (date.today() + timedelta(days=3), "Due this week"),
        (date.today().replace(day=28), "Due this month"),
        (date.today() + timedelta(days=45), "Upcoming"),
    ],
)
def test_status_logic(client, due_date, expected_status):
    if expected_status == "Due this month" and due_date <= date.today() + timedelta(days=7):
        pytest.skip("Current date leaves no later-in-month day outside the week window.")

    created = create_reminder(client, due_date=due_date.isoformat())

    assert created["status"] == expected_status


def create_reminder_model(due_date):
    from datetime import datetime, timezone
    from uuid import uuid4

    from app.models import Reminder

    return Reminder(
        id=str(uuid4()),
        title="Repository persistence check",
        category="Other",
        due_date=due_date,
        repeat="None",
        priority="Medium",
        notes=None,
        completed=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        completed_at=None,
    )
