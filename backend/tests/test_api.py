from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.auth import UserContext, get_current_user
from app.config import get_settings
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


def set_auth_user(user_id: str):
    app.dependency_overrides[get_current_user] = lambda: UserContext(user_id=user_id)


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_stays_public_in_cognito_mode(client, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "cognito")
    get_settings.cache_clear()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("get", "/reminders", None),
        ("post", "/reminders", make_payload()),
        ("get", "/reminders/example-id", None),
        ("put", "/reminders/example-id", {"title": "Updated"}),
        ("delete", "/reminders/example-id", None),
        ("post", "/reminders/example-id/complete", None),
    ],
)
def test_cognito_mode_rejects_unauthenticated_reminder_routes(client, monkeypatch, method, path, json_body):
    monkeypatch.setenv("AUTH_MODE", "cognito")
    get_settings.cache_clear()

    request = getattr(client, method)
    kwargs = {"json": json_body} if json_body is not None else {}
    response = request(path, **kwargs)

    assert response.status_code == 401

    get_settings.cache_clear()


@pytest.mark.parametrize(
    "origin",
    [
        "https://lifeledger.jpreinold.com",
        "https://www.lifeledger.jpreinold.com",
    ],
)
def test_cors_allows_cloudflare_frontend(client, origin):
    response = client.get("/reminders", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


@pytest.mark.parametrize(
    "origin",
    [
        "https://lifeledger.jpreinold.com",
        "https://www.lifeledger.jpreinold.com",
    ],
)
def test_cors_preflight_allows_cloudflare_frontend(client, origin):
    response = client.options(
        "/reminders",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "GET" in response.headers["access-control-allow-methods"]
    assert "Authorization" in response.headers["access-control-allow-headers"]


def test_create_and_fetch_reminder(client):
    created = create_reminder(client)

    assert "user_id" not in created

    list_response = client.get("/reminders")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = client.get(f"/reminders/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Renew car tag"


def test_authenticated_user_can_crud_own_reminders(client):
    set_auth_user("user-a")

    created = create_reminder(client)
    response = client.put(
        f"/reminders/{created['id']}",
        json={"title": "User scoped update"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "User scoped update"

    complete_response = client.post(f"/reminders/{created['id']}/complete")
    assert complete_response.status_code == 200
    assert complete_response.json()["completed"] is True

    delete_response = client.delete(f"/reminders/{created['id']}")
    assert delete_response.status_code == 204


def test_user_cannot_access_another_users_reminder(client):
    set_auth_user("user-a")
    created = create_reminder(client)

    set_auth_user("user-b")

    list_response = client.get("/reminders")
    assert list_response.status_code == 200
    assert list_response.json() == []

    get_response = client.get(f"/reminders/{created['id']}")
    assert get_response.status_code == 404

    update_response = client.put(f"/reminders/{created['id']}", json={"title": "Blocked update"})
    assert update_response.status_code == 404

    complete_response = client.post(f"/reminders/{created['id']}/complete")
    assert complete_response.status_code == 404

    delete_response = client.delete(f"/reminders/{created['id']}")
    assert delete_response.status_code == 404


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
    loaded = second_repo.get_reminder("local-dev-user", created.id)

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
