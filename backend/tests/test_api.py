import json
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.alerts import get_alert_eligibility
from app.auth import UserContext, get_current_user
from app.config import get_settings
from app.main import app, get_preferences_repository, get_repository
from app.preferences_repository import LocalPreferencesRepository
from app.repository import LocalReminderRepository
from app.schemas import BirthdayDetails, MaintenanceDetails, ReminderCategory, ReminderType, RenewalDetails, RepeatOption


@pytest.fixture()
def client(tmp_path):
    repo = LocalReminderRepository(tmp_path / "reminders.json")
    preferences_repo = LocalPreferencesRepository(tmp_path / "preferences.json")
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_preferences_repository] = lambda: preferences_repo

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
        ("get", "/alerts", None),
        ("get", "/preferences/digest", None),
        ("get", "/push/config", None),
        ("get", "/push/subscriptions", None),
        ("post", "/push/subscriptions", {"endpoint": "https://push.example/test", "keys": {"p256dh": "key", "auth": "secret"}}),
        ("delete", "/push/subscriptions/example-id", None),
        ("get", "/reminders", None),
        ("put", "/preferences/digest", {"digest_enabled": False}),
        ("post", "/reminders", make_payload()),
        ("get", "/reminders/example-id", None),
        ("put", "/reminders/example-id", {"title": "Updated"}),
        ("delete", "/reminders/example-id", None),
        ("post", "/reminders/example-id/alert/dismiss", None),
        ("post", "/reminders/example-id/alert/snooze", None),
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


def test_get_digest_preferences_returns_defaults_for_new_user(client):
    response = client.get("/preferences/digest")

    assert response.status_code == 200
    body = response.json()
    assert body["digest_enabled"] is True
    assert body["digest_time"] == "09:00"
    assert body["digest_lookahead_days"] == 30
    assert body["timezone"] is None
    assert body["digest_last_seen_at"] is None
    assert "updated_at" in body
    assert "user_id" not in body


def test_update_digest_preferences_merges_with_defaults(client):
    response = client.put(
        "/preferences/digest",
        json={
            "digest_enabled": False,
            "digest_time": "08:30",
            "digest_lookahead_days": 14,
            "timezone": "America/New_York",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["digest_enabled"] is False
    assert body["digest_time"] == "08:30"
    assert body["digest_lookahead_days"] == 14
    assert body["timezone"] == "America/New_York"
    assert "user_id" not in body

    follow_up = client.put("/preferences/digest", json={"digest_enabled": True})
    assert follow_up.status_code == 200
    assert follow_up.json()["digest_enabled"] is True
    assert follow_up.json()["digest_time"] == "08:30"
    assert follow_up.json()["digest_lookahead_days"] == 14


def test_digest_preferences_are_user_scoped(client):
    set_auth_user("user-a")
    response = client.put("/preferences/digest", json={"digest_enabled": False, "digest_time": "07:15"})
    assert response.status_code == 200

    set_auth_user("user-b")
    other_user_response = client.get("/preferences/digest")
    assert other_user_response.status_code == 200
    assert other_user_response.json()["digest_enabled"] is True
    assert other_user_response.json()["digest_time"] == "09:00"

    set_auth_user("user-a")
    original_user_response = client.get("/preferences/digest")
    assert original_user_response.status_code == 200
    assert original_user_response.json()["digest_enabled"] is False
    assert original_user_response.json()["digest_time"] == "07:15"


def test_update_digest_preferences_records_last_seen(client):
    seen_at = datetime.now(timezone.utc).isoformat()

    response = client.put("/preferences/digest", json={"digest_last_seen_at": seen_at})

    assert response.status_code == 200
    assert response.json()["digest_last_seen_at"].startswith(seen_at[:19])


@pytest.mark.parametrize(
    "payload",
    [
        {"digest_time": "25:00"},
        {"digest_time": "9am"},
        {"digest_lookahead_days": 10},
    ],
)
def test_update_digest_preferences_validates_schedule_fields(client, payload):
    response = client.put("/preferences/digest", json=payload)

    assert response.status_code == 422


def test_create_and_fetch_reminder(client):
    created = create_reminder(client)

    assert "user_id" not in created
    assert created["reminder_type"] == "generic"
    assert created["birthday_details"] is None
    assert created["renewal_details"] is None
    assert created["maintenance_details"] is None
    assert created["computed_label"] is None
    assert created["renewal_status_label"] is None

    list_response = client.get("/reminders")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = client.get(f"/reminders/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Renew car tag"


def test_create_reminder_stores_reminder_timing_fields(client):
    created = create_reminder(
        client,
        reminder_lead_value=1,
        reminder_lead_unit="weeks",
        reminder_time="09:00",
    )

    assert created["reminder_lead_value"] == 1
    assert created["reminder_lead_unit"] == "weeks"
    assert created["reminder_time"] == "09:00"

    get_response = client.get(f"/reminders/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["reminder_lead_value"] == 1


def test_create_birthday_reminder_with_birth_year_calculates_age(client):
    birthday = date.today() + timedelta(days=30)
    birth_year = birthday.year - 27

    created = create_reminder(
        client,
        title="Max's birthday",
        category="Family",
        due_date=date.today().isoformat(),
        repeat="None",
        priority="Medium",
        reminder_type="birthday",
        birthday_details={
            "person_name": "Max",
            "birth_month": birthday.month,
            "birth_day": birthday.day,
            "birth_year": birth_year,
        },
    )

    assert created["reminder_type"] == "birthday"
    assert created["due_date"] == birthday.isoformat()
    assert created["repeat"] == "Yearly"
    assert created["reminder_lead_value"] == 1
    assert created["reminder_lead_unit"] == "weeks"
    assert created["reminder_time"] == "09:00"
    assert created["birthday_details"]["birth_year"] == birth_year
    assert created["birthday_details"]["age_turning_next_birthday"] == 27
    assert created["birthday_details"]["inferred_birth_year"] is False
    assert created["birthday_age_label"] == "Turning 27"
    assert created["computed_label"].startswith("Turns 27")


def test_create_birthday_reminder_with_age_turning_infers_birth_year(client):
    birthday = date.today() + timedelta(days=45)

    created = create_reminder(
        client,
        title="Jasmine's birthday",
        category="Family",
        due_date=date.today().isoformat(),
        reminder_type="birthday",
        birthday_details={
            "person_name": "Jasmine",
            "birth_month": birthday.month,
            "birth_day": birthday.day,
            "age_turning_next_birthday": 31,
        },
    )

    assert created["due_date"] == birthday.isoformat()
    assert created["birthday_details"]["birth_year"] == birthday.year - 31
    assert created["birthday_details"]["age_turning_next_birthday"] == 31
    assert created["birthday_details"]["inferred_birth_year"] is True
    assert created["birthday_age_label"] == "Turning 31"


def test_create_birthday_reminder_with_unknown_age_still_works(client):
    birthday = date.today() + timedelta(days=60)

    created = create_reminder(
        client,
        title="Friend's birthday",
        category="Family",
        due_date=date.today().isoformat(),
        reminder_type="birthday",
        birthday_details={
            "person_name": "Friend",
            "birth_month": birthday.month,
            "birth_day": birthday.day,
        },
    )

    assert created["due_date"] == birthday.isoformat()
    assert created["birthday_details"]["birth_year"] is None
    assert created["birthday_details"]["age_turning_next_birthday"] is None
    assert created["birthday_details"]["inferred_birth_year"] is False
    assert created["birthday_age_label"] == "Age unknown"
    assert created["computed_label"] == "Age unknown"


def test_birthday_reminders_remain_user_scoped(client):
    set_auth_user("user-a")
    birthday = date.today() + timedelta(days=20)
    created = create_reminder(
        client,
        title="Mom's birthday",
        category="Family",
        due_date=date.today().isoformat(),
        reminder_type="birthday",
        birthday_details={
            "person_name": "Mom",
            "birth_month": birthday.month,
            "birth_day": birthday.day,
            "birth_year": birthday.year - 58,
        },
    )

    set_auth_user("user-b")

    list_response = client.get("/reminders")
    get_response = client.get(f"/reminders/{created['id']}")

    assert list_response.status_code == 200
    assert list_response.json() == []
    assert get_response.status_code == 404



def test_create_renewal_reminder_with_renewal_date_works(client):
    renewal_date = date.today() + timedelta(days=42)

    created = create_reminder(
        client,
        title="Renew Alina's car tag",
        category="Car",
        due_date=date.today().isoformat(),
        repeat="Yearly",
        priority="High",
        reminder_type="renewal",
        renewal_details={
            "item_name": "Alina's car tag",
            "renewal_kind": "renewal",
            "renewal_date": renewal_date.isoformat(),
            "renewal_window_days": 31,
            "frequency": "Yearly",
        },
    )

    assert created["reminder_type"] == "renewal"
    assert created["due_date"] == renewal_date.isoformat()
    assert created["birthday_details"] is None
    assert created["renewal_details"]["item_name"] == "Alina's car tag"
    assert created["renewal_details"]["renewal_kind"] == "renewal"
    assert created["reminder_lead_value"] == 1
    assert created["reminder_lead_unit"] == "months"
    assert created["reminder_time"] == "09:00"
    assert created["renewal_status_label"] == "Renews in 42 days"
    assert created["computed_label"] == "Renews in 42 days"
    assert created["renewal_window_label"] is not None


def test_create_expiration_reminder_with_expiration_date_works(client):
    expiration_date = date.today() + timedelta(days=86)

    created = create_reminder(
        client,
        title="Passport expiration",
        category="Other",
        due_date=date.today().isoformat(),
        reminder_type="renewal",
        renewal_details={
            "item_name": "Passport",
            "renewal_kind": "expiration",
            "expiration_date": expiration_date.isoformat(),
        },
    )

    assert created["due_date"] == expiration_date.isoformat()
    assert created["renewal_details"]["expiration_date"] == expiration_date.isoformat()
    assert created["renewal_status_label"] == "Expires in 86 days"
    assert created["computed_label"] == "Expires in 86 days"


def test_past_expiration_reminder_shows_expired_label(client):
    expiration_date = date.today() - timedelta(days=12)

    created = create_reminder(
        client,
        title="Warranty expiration",
        category="Home",
        due_date=date.today().isoformat(),
        reminder_type="renewal",
        renewal_details={
            "item_name": "Warranty",
            "renewal_kind": "expiration",
            "expiration_date": expiration_date.isoformat(),
        },
    )

    assert created["status"] == "Overdue"
    assert created["renewal_status_label"] == "Expired 12 days ago"
    assert created["computed_label"] == "Expired 12 days ago"


def test_renewal_reminder_with_unknown_structured_date_still_works(client):
    generic_due_date = date.today() + timedelta(days=10)

    created = create_reminder(
        client,
        title="Mystery renewal",
        category="Other",
        due_date=generic_due_date.isoformat(),
        reminder_type="renewal",
        renewal_details={
            "item_name": "Mystery renewal",
            "renewal_kind": "renewal",
        },
    )

    assert created["due_date"] == generic_due_date.isoformat()
    assert created["renewal_status_label"] == "Renewal date unknown"
    assert created["computed_label"] == "Renewal date unknown"


def test_review_renewal_reminder_shows_review_label(client):
    renewal_date = date.today() + timedelta(days=180)

    created = create_reminder(
        client,
        title="Review home insurance",
        category="Home",
        due_date=date.today().isoformat(),
        reminder_type="renewal",
        renewal_details={
            "item_name": "Home insurance",
            "renewal_kind": "review",
            "renewal_date": renewal_date.isoformat(),
            "review_lead_days": 30,
        },
    )

    assert created["due_date"] == renewal_date.isoformat()
    assert created["computed_label"] == "Review 30 days before renewal"
    assert created["renewal_status_label"] == "Renews in 180 days"


def test_renewal_reminders_remain_user_scoped(client):
    set_auth_user("user-a")
    renewal_date = date.today() + timedelta(days=20)
    created = create_reminder(
        client,
        title="Renew car tag",
        category="Car",
        due_date=date.today().isoformat(),
        reminder_type="renewal",
        renewal_details={
            "item_name": "Car tag",
            "renewal_kind": "renewal",
            "renewal_date": renewal_date.isoformat(),
        },
    )

    set_auth_user("user-b")

    list_response = client.get("/reminders")
    get_response = client.get(f"/reminders/{created['id']}")

    assert list_response.status_code == 200
    assert list_response.json() == []
    assert get_response.status_code == 404

def test_create_maintenance_reminder_with_last_completed_calculates_next_due(client):
    last_completed = date.today()
    expected_due_date = last_completed + timedelta(weeks=12)

    created = create_reminder(
        client,
        title="Change HVAC filter",
        category="Home",
        due_date=date.today().isoformat(),
        repeat="None",
        priority="Medium",
        reminder_type="maintenance",
        maintenance_details={
            "item_name": "Change HVAC filter",
            "maintenance_area": "home",
            "last_completed_date": last_completed.isoformat(),
            "interval_value": 12,
            "interval_unit": "weeks",
            "instructions": "Replace the filter and reset the reminder.",
        },
    )

    assert created["reminder_type"] == "maintenance"
    assert created["due_date"] == expected_due_date.isoformat()
    assert created["next_due_date"] == expected_due_date.isoformat()
    assert created["birthday_details"] is None
    assert created["renewal_details"] is None
    assert created["maintenance_details"]["item_name"] == "Change HVAC filter"
    assert created["maintenance_details"]["next_due_date"] == expected_due_date.isoformat()
    assert created["reminder_lead_value"] == 1
    assert created["reminder_lead_unit"] == "weeks"
    assert created["reminder_time"] == "09:00"
    assert created["maintenance_status_label"] is not None
    assert created["computed_label"] is not None


def test_create_maintenance_reminder_with_explicit_next_due_date_works(client):
    next_due_date = date.today() + timedelta(days=58)

    created = create_reminder(
        client,
        title="Clean dryer vent",
        category="Home",
        due_date=date.today().isoformat(),
        reminder_type="maintenance",
        maintenance_details={
            "item_name": "Clean dryer vent",
            "maintenance_area": "home",
            "interval_value": 1,
            "interval_unit": "years",
            "next_due_date": next_due_date.isoformat(),
        },
    )

    assert created["due_date"] == next_due_date.isoformat()
    assert created["maintenance_details"]["next_due_date"] == next_due_date.isoformat()
    assert created["repeat"] == "Yearly"


def test_complete_maintenance_reminder_advances_next_due_date(client):
    next_due_date = date.today() - timedelta(days=1)
    created = create_reminder(
        client,
        title="Test smoke detectors",
        category="Home",
        due_date=next_due_date.isoformat(),
        repeat="None",
        priority="Medium",
        reminder_type="maintenance",
        maintenance_details={
            "item_name": "Test smoke detectors",
            "maintenance_area": "home",
            "last_completed_date": (date.today() - timedelta(days=190)).isoformat(),
            "interval_value": 6,
            "interval_unit": "months",
            "next_due_date": next_due_date.isoformat(),
        },
    )

    complete_response = client.post(f"/reminders/{created['id']}/complete")
    body = complete_response.json()
    completed_on = date.fromisoformat(body["maintenance_details"]["last_completed_date"])

    assert complete_response.status_code == 200
    assert body["completed"] is False
    assert body["completed_at"] is not None
    assert date.fromisoformat(body["due_date"]) > completed_on
    assert body["due_date"] == body["maintenance_details"]["next_due_date"]
    assert body["maintenance_details"]["last_completed_date"] == completed_on.isoformat()


def test_maintenance_reminders_remain_user_scoped(client):
    set_auth_user("user-a")
    created = create_reminder(
        client,
        title="Pet heartworm medicine",
        category="Family",
        due_date=date.today().isoformat(),
        reminder_type="maintenance",
        maintenance_details={
            "item_name": "Pet heartworm medicine",
            "maintenance_area": "pet",
            "last_completed_date": date.today().isoformat(),
            "interval_value": 1,
            "interval_unit": "months",
        },
    )

    set_auth_user("user-b")

    list_response = client.get("/reminders")
    get_response = client.get(f"/reminders/{created['id']}")

    assert list_response.status_code == 200
    assert list_response.json() == []
    assert get_response.status_code == 404

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
            "reminder_lead_value": 1,
            "reminder_lead_unit": "months",
            "reminder_time": "09:00",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["title"] == "Renew vehicle registration"
    assert body["repeat"] == "Yearly"
    assert body["notes"] is None
    assert body["reminder_lead_value"] == 1
    assert body["reminder_lead_unit"] == "months"
    assert body["reminder_time"] == "09:00"
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


def test_local_json_repository_persists_birthday_reminders(tmp_path):
    data_file = tmp_path / "reminders.json"
    first_repo = LocalReminderRepository(data_file)
    due_date = date.today() + timedelta(days=10)
    created = create_reminder_model(due_date).model_copy(
        update={
            "title": "Max's birthday",
            "category": ReminderCategory.FAMILY,
            "due_date": due_date,
            "repeat": RepeatOption.YEARLY,
            "reminder_type": ReminderType.BIRTHDAY,
            "birthday_details": BirthdayDetails(
                person_name="Max",
                birth_month=due_date.month,
                birth_day=due_date.day,
                birth_year=due_date.year - 27,
                age_turning_next_birthday=27,
            ),
        }
    )

    first_repo.create_reminder(created)
    second_repo = LocalReminderRepository(data_file)
    loaded = second_repo.get_reminder("local-dev-user", created.id)

    assert loaded is not None
    assert loaded.reminder_type == ReminderType.BIRTHDAY
    assert loaded.birthday_details is not None
    assert loaded.birthday_details.person_name == "Max"
    assert loaded.birthday_details.age_turning_next_birthday == 27



def test_local_json_repository_persists_renewal_reminders(tmp_path):
    data_file = tmp_path / "reminders.json"
    first_repo = LocalReminderRepository(data_file)
    due_date = date.today() + timedelta(days=10)
    created = create_reminder_model(due_date).model_copy(
        update={
            "title": "Passport expiration",
            "category": ReminderCategory.OTHER,
            "due_date": due_date,
            "repeat": RepeatOption.YEARLY,
            "reminder_type": ReminderType.RENEWAL,
            "renewal_details": RenewalDetails(
                item_name="Passport",
                renewal_kind="expiration",
                expiration_date=due_date,
                review_lead_days=90,
            ),
        }
    )

    first_repo.create_reminder(created)
    second_repo = LocalReminderRepository(data_file)
    loaded = second_repo.get_reminder("local-dev-user", created.id)

    assert loaded is not None
    assert loaded.reminder_type == ReminderType.RENEWAL
    assert loaded.renewal_details is not None
    assert loaded.renewal_details.item_name == "Passport"
    assert loaded.renewal_details.expiration_date == due_date

def test_local_json_repository_persists_maintenance_reminders(tmp_path):
    data_file = tmp_path / "reminders.json"
    first_repo = LocalReminderRepository(data_file)
    due_date = date.today() + timedelta(days=10)
    created = create_reminder_model(due_date).model_copy(
        update={
            "title": "Change HVAC filter",
            "category": ReminderCategory.HOME,
            "due_date": due_date,
            "repeat": RepeatOption.QUARTERLY,
            "reminder_type": ReminderType.MAINTENANCE,
            "maintenance_details": MaintenanceDetails(
                item_name="Change HVAC filter",
                maintenance_area="home",
                last_completed_date=date.today(),
                interval_value=3,
                interval_unit="months",
                next_due_date=due_date,
            ),
        }
    )

    first_repo.create_reminder(created)
    second_repo = LocalReminderRepository(data_file)
    loaded = second_repo.get_reminder("local-dev-user", created.id)

    assert loaded is not None
    assert loaded.reminder_type == ReminderType.MAINTENANCE
    assert loaded.maintenance_details is not None
    assert loaded.maintenance_details.item_name == "Change HVAC filter"
    assert loaded.maintenance_details.next_due_date == due_date

def test_local_json_repository_loads_legacy_reminders_without_timing_fields(tmp_path):
    data_file = tmp_path / "reminders.json"
    reminder_id = "legacy-reminder"
    now = "2026-01-01T00:00:00+00:00"
    data_file.write_text(
        json.dumps(
            [
                {
                    "id": reminder_id,
                    "user_id": "local-dev-user",
                    "title": "Legacy reminder",
                    "category": "Other",
                    "due_date": date.today().isoformat(),
                    "repeat": "None",
                    "priority": "Medium",
                    "notes": None,
                    "completed": False,
                    "created_at": now,
                    "updated_at": now,
                    "completed_at": None,
                }
            ]
        ),
        encoding="utf-8",
    )

    repo = LocalReminderRepository(data_file)
    loaded = repo.get_reminder("local-dev-user", reminder_id)

    assert loaded is not None
    assert loaded.reminder_lead_value is None
    assert loaded.reminder_lead_unit is None
    assert loaded.reminder_time is None
    assert loaded.reminder_type == ReminderType.GENERIC
    assert loaded.birthday_details is None
    assert loaded.renewal_details is None
    assert loaded.maintenance_details is None


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



def test_alerts_include_due_today_reminders(client):
    created = create_reminder(client, title="Due today alert", due_date=date.today().isoformat())

    response = client.get("/alerts")
    body = response.json()

    assert response.status_code == 200
    assert [item["id"] for item in body] == [created["id"]]
    assert body[0]["alert_reason"] == "Due today"
    assert body[0]["alert_reminder_start_date"] == date.today().isoformat()


def test_alerts_include_overdue_reminders(client):
    created = create_reminder(client, title="Overdue alert", due_date=(date.today() - timedelta(days=2)).isoformat())

    response = client.get("/alerts")
    body = response.json()

    assert response.status_code == 200
    assert [item["id"] for item in body] == [created["id"]]
    assert body[0]["alert_reason"] == "Overdue"


def test_alerts_include_reminders_inside_timing_window(client):
    due_date = date.today() + timedelta(days=7)
    created = create_reminder(
        client,
        title="Timing window alert",
        due_date=due_date.isoformat(),
        reminder_lead_value=1,
        reminder_lead_unit="weeks",
        reminder_time="09:00",
    )

    response = client.get("/alerts")
    body = response.json()

    assert response.status_code == 200
    assert [item["id"] for item in body] == [created["id"]]
    assert body[0]["alert_reason"] == "Reminder window"
    assert body[0]["alert_reminder_start_date"] == date.today().isoformat()


def test_dismissed_alerts_do_not_appear(client):
    created = create_reminder(client, title="Dismiss me", due_date=date.today().isoformat())

    dismiss_response = client.post(f"/reminders/{created['id']}/alert/dismiss")
    alerts_response = client.get("/alerts")

    assert dismiss_response.status_code == 200
    assert dismiss_response.json()["alert_dismissed_until"] is not None
    assert dismiss_response.json()["alert_last_action_at"] is not None
    assert alerts_response.status_code == 200
    assert alerts_response.json() == []


def test_snoozed_alerts_do_not_appear_before_snooze_time(client):
    created = create_reminder(client, title="Snooze me", due_date=date.today().isoformat())
    snoozed_until = datetime.now(timezone.utc) + timedelta(days=1)

    snooze_response = client.post(
        f"/reminders/{created['id']}/alert/snooze",
        json={"snoozed_until": snoozed_until.isoformat()},
    )
    alerts_response = client.get("/alerts")

    assert snooze_response.status_code == 200
    assert snooze_response.json()["alert_snoozed_until"] is not None
    assert snooze_response.json()["alert_last_action_at"] is not None
    assert alerts_response.status_code == 200
    assert alerts_response.json() == []


def test_alerts_remain_user_scoped(client):
    set_auth_user("user-a")
    create_reminder(client, title="User A alert", due_date=date.today().isoformat())

    set_auth_user("user-b")
    response = client.get("/alerts")

    assert response.status_code == 200
    assert response.json() == []


def test_alert_eligibility_handles_legacy_reminders_without_alert_fields(tmp_path):
    data_file = tmp_path / "reminders.json"
    reminder_id = "legacy-alert-reminder"
    now = "2026-01-01T00:00:00+00:00"
    data_file.write_text(
        json.dumps(
            [
                {
                    "id": reminder_id,
                    "user_id": "local-dev-user",
                    "title": "Legacy alert reminder",
                    "category": "Other",
                    "due_date": date.today().isoformat(),
                    "repeat": "None",
                    "priority": "Medium",
                    "notes": None,
                    "completed": False,
                    "created_at": now,
                    "updated_at": now,
                    "completed_at": None,
                }
            ]
        ),
        encoding="utf-8",
    )

    repo = LocalReminderRepository(data_file)
    loaded = repo.get_reminder("local-dev-user", reminder_id)
    eligibility = get_alert_eligibility(loaded) if loaded else None

    assert loaded is not None
    assert loaded.alert_dismissed_until is None
    assert loaded.alert_snoozed_until is None
    assert eligibility is not None
    assert eligibility.reason == "Due today"


def test_complete_generic_reminder_from_alert_flow(client):
    created = create_reminder(client, title="Complete from alerts", due_date=date.today().isoformat(), repeat="None")
    assert [item["id"] for item in client.get("/alerts").json()] == [created["id"]]

    complete_response = client.post(f"/reminders/{created['id']}/complete")

    assert complete_response.status_code == 200
    assert complete_response.json()["completed"] is True
    assert client.get("/alerts").json() == []


def test_complete_recurring_reminder_from_alert_flow_advances(client):
    created = create_reminder(
        client,
        title="Recurring alert completion",
        due_date=(date.today() - timedelta(days=1)).isoformat(),
        repeat="Weekly",
    )
    assert [item["id"] for item in client.get("/alerts").json()] == [created["id"]]

    complete_response = client.post(f"/reminders/{created['id']}/complete")
    body = complete_response.json()

    assert complete_response.status_code == 200
    assert body["completed"] is False
    assert date.fromisoformat(body["due_date"]) > date.today()
    assert body["alert_dismissed_until"] is None
    assert body["alert_snoozed_until"] is None
    assert client.get("/alerts").json() == []


def test_complete_maintenance_reminder_from_alert_flow_advances_next_due(client):
    next_due_date = date.today() - timedelta(days=1)
    created = create_reminder(
        client,
        title="Maintenance alert completion",
        category="Home",
        due_date=next_due_date.isoformat(),
        repeat="None",
        priority="Medium",
        reminder_type="maintenance",
        maintenance_details={
            "item_name": "Maintenance alert completion",
            "maintenance_area": "home",
            "last_completed_date": (date.today() - timedelta(days=190)).isoformat(),
            "interval_value": 6,
            "interval_unit": "months",
            "next_due_date": next_due_date.isoformat(),
        },
    )
    assert [item["id"] for item in client.get("/alerts").json()] == [created["id"]]

    complete_response = client.post(f"/reminders/{created['id']}/complete")
    body = complete_response.json()

    assert complete_response.status_code == 200
    assert body["completed"] is False
    assert date.fromisoformat(body["due_date"]) > date.today()
    assert body["due_date"] == body["maintenance_details"]["next_due_date"]
    assert body["alert_dismissed_until"] is None
    assert body["alert_snoozed_until"] is None
    assert client.get("/alerts").json() == []


def test_local_json_repository_preserves_alert_state(tmp_path):
    data_file = tmp_path / "reminders.json"
    first_repo = LocalReminderRepository(data_file)
    alert_time = datetime.now(timezone.utc) + timedelta(days=1)
    created = create_reminder_model(date.today()).model_copy(
        update={
            "alert_dismissed_until": alert_time,
            "alert_last_action_at": alert_time,
            "alert_snoozed_until": alert_time,
        }
    )

    first_repo.create_reminder(created)
    second_repo = LocalReminderRepository(data_file)
    loaded = second_repo.get_reminder("local-dev-user", created.id)

    assert loaded is not None
    assert loaded.alert_dismissed_until == alert_time
    assert loaded.alert_last_action_at == alert_time
    assert loaded.alert_snoozed_until == alert_time
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
