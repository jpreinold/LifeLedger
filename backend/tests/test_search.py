from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.attachments_repository import LocalRecordAttachmentRepository, record_attachment_key
from app.auth import UserContext, get_current_user
from app.linked_items_repository import LocalLinkedItemRepository
from app.main import (
    app,
    get_linked_item_repository,
    get_record_attachment_repository,
    get_record_repository,
    get_repository,
    get_saved_search_view_repository,
    get_search_index_repository,
)
from app.models import RecordAttachment
from app.records_repository import LocalRecordRepository
from app.repository import LocalReminderRepository
from app.schemas import AttachmentStatus, LinkedEntityType
from app.search_repository import LocalSavedSearchViewRepository, LocalSearchIndexRepository
from app.search_service import SearchProjectionService


@pytest.fixture()
def search_context(tmp_path):
    record_repo = LocalRecordRepository(tmp_path / "records.json")
    reminder_repo = LocalReminderRepository(tmp_path / "reminders.json")
    attachment_repo = LocalRecordAttachmentRepository(tmp_path / "attachments.json")
    linked_repo = LocalLinkedItemRepository(tmp_path / "linked-items.json")
    search_repo = LocalSearchIndexRepository(tmp_path / "search-index.json")
    saved_view_repo = LocalSavedSearchViewRepository(tmp_path / "saved-views.json")

    app.dependency_overrides[get_record_repository] = lambda: record_repo
    app.dependency_overrides[get_repository] = lambda: reminder_repo
    app.dependency_overrides[get_record_attachment_repository] = lambda: attachment_repo
    app.dependency_overrides[get_linked_item_repository] = lambda: linked_repo
    app.dependency_overrides[get_search_index_repository] = lambda: search_repo
    app.dependency_overrides[get_saved_search_view_repository] = lambda: saved_view_repo

    with TestClient(app) as client:
        yield client, record_repo, reminder_repo, attachment_repo, linked_repo, search_repo, saved_view_repo

    app.dependency_overrides.clear()


def set_auth_user(user_id: str) -> None:
    app.dependency_overrides[get_current_user] = lambda: UserContext(user_id=user_id)


def record_payload(**overrides):
    payload = {
        "record_type": "passport",
        "title": "Passport",
        "category": "Documents",
        "owner_name": "Alina",
        "provider_or_brand": "United States",
        "issue_date": date.today().isoformat(),
        "expiration_date": (date.today() + timedelta(days=365)).isoformat(),
        "notes": "Private note not intended for search.",
        "tags": ["travel"],
    }
    payload.update(overrides)
    return payload


def reminder_payload(**overrides):
    payload = {
        "title": "Passport Renewal",
        "category": "Other",
        "due_date": (date.today() + timedelta(days=45)).isoformat(),
        "repeat": "Yearly",
        "priority": "High",
        "reminder_type": "renewal",
        "renewal_details": {
            "item_name": "Passport",
            "renewal_kind": "expiration",
            "owner_name": "Alina",
            "expiration_date": (date.today() + timedelta(days=45)).isoformat(),
        },
    }
    payload.update(overrides)
    return payload


def create_record(client: TestClient, **overrides):
    response = client.post("/records", json=record_payload(**overrides))
    assert response.status_code == 201
    return response.json()


def create_reminder(client: TestClient, **overrides):
    response = client.post("/reminders", json=reminder_payload(**overrides))
    assert response.status_code == 201
    return response.json()


def search(client: TestClient, **params):
    response = client.get("/search", params=params)
    assert response.status_code == 200
    return response.json()


def create_attachment_metadata(attachment_repo, user_id: str, record_id: str, name: str) -> RecordAttachment:
    now = datetime.now(timezone.utc)
    attachment_id = str(uuid4())
    return attachment_repo.create_attachment(
        RecordAttachment(
            attachment_id=attachment_id,
            user_id=user_id,
            owner_hash="owner-hash",
            record_id=record_id,
            record_attachment_key=record_attachment_key(record_id, attachment_id),
            display_name=name,
            content_type="application/pdf",
            size_bytes=2048,
            status=AttachmentStatus.AVAILABLE,
            scan_result=None,
            quarantine_object_key=None,
            clean_object_key="clean/object",
            upload_expires_at=None,
            created_at=now,
            uploaded_at=now,
            scan_completed_at=now,
            available_at=now,
            deleted_at=None,
            etag=None,
            encryption_key_arn=None,
        )
    )


def build_projection_service(record_repo, reminder_repo, attachment_repo, linked_repo, search_repo):
    return SearchProjectionService(search_repo, record_repo, reminder_repo, attachment_repo, linked_repo)


def test_search_returns_records_reminders_documents_and_relationship_context(search_context):
    client, record_repo, reminder_repo, attachment_repo, linked_repo, search_repo, _saved_repo = search_context
    record = create_record(client, title="Passport", category="Travel Documents")
    reminder = create_reminder(client)
    attachment = create_attachment_metadata(attachment_repo, "local-dev-user", record["id"], "Passport Scan.pdf")
    service = build_projection_service(record_repo, reminder_repo, attachment_repo, linked_repo, search_repo)
    service.sync_entity("local-dev-user", LinkedEntityType.DOCUMENT, record_attachment_key(record["id"], attachment.attachment_id))
    service.sync_entity("local-dev-user", LinkedEntityType.RECORD, record["id"])

    relationship = client.post(
        "/relationships",
        json={
            "source_item_type": "record",
            "source_item_id": record["id"],
            "target_item_type": "reminder",
            "target_item_id": reminder["id"],
            "relationship_type": "renews",
            "custom_label": "Renewal checklist",
        },
    )
    assert relationship.status_code == 201

    body = search(client, q="passport")
    titles = {item["title"] for item in body["items"]}
    assert {"Passport", "Passport Renewal", "Passport Scan.pdf"}.issubset(titles)
    assert body["result_count"] == 3

    relationship_body = search(client, q="checklist")
    assert {item["source_item_type"] for item in relationship_body["items"]} == {"record", "reminder"}
    assert all(item["match_context"] for item in relationship_body["items"])


def test_search_indexes_custom_field_labels_but_not_private_values_or_notes(search_context):
    client, *_repos = search_context
    record = create_record(
        client,
        title="Home Insurance Policy",
        category="Insurance",
        notes="ultrasecret-notes should stay out of search",
    )

    field_response = client.post(
        f"/records/{record['id']}/fields",
        json={"label": "Agent Email", "field_type": "email", "value": "privateagent@example.com"},
    )
    assert field_response.status_code == 201

    label_body = search(client, q="agent email")
    assert [item["title"] for item in label_body["items"]] == ["Home Insurance Policy"]

    assert search(client, q="privateagent")["items"] == []
    assert search(client, q="ultrasecret")["items"] == []


def test_search_filters_paginates_and_rejects_invalid_cursor(search_context):
    client, *_repos = search_context
    create_record(client, title="Auto Insurance Policy", record_type="insurance", category="Insurance")
    create_record(client, title="Home Insurance Policy", record_type="insurance", category="Insurance")
    create_reminder(client, title="Insurance Renewal", category="Finance")

    first_page = search(client, q="insurance", itemTypes="record", sort="title_asc", pageSize=1)
    assert first_page["result_count"] == 2
    assert [item["source_item_type"] for item in first_page["items"]] == ["record"]
    assert first_page["items"][0]["title"] == "Auto Insurance Policy"
    assert first_page["next_cursor"]

    second_page = search(
        client,
        q="insurance",
        itemTypes="record",
        sort="title_asc",
        pageSize=1,
        cursor=first_page["next_cursor"],
    )
    assert second_page["items"][0]["title"] == "Home Insurance Policy"
    assert second_page["next_cursor"] is None

    invalid = client.get("/search", params={"q": "insurance", "cursor": "not-a-valid-cursor"})
    assert invalid.status_code == 422


def test_search_is_user_scoped_and_tracks_archive_restore_delete(search_context):
    client, *_repos = search_context
    set_auth_user("user-a")
    record = create_record(client, title="Archive Passport")

    set_auth_user("user-b")
    assert search(client, q="archive passport")["items"] == []

    set_auth_user("user-a")
    assert [item["title"] for item in search(client, q="archive passport")["items"]] == ["Archive Passport"]

    archive = client.post(f"/records/{record['id']}/archive")
    assert archive.status_code == 200
    assert search(client, q="archive passport")["items"] == []
    archived_body = search(client, q="archive passport", archived=True)
    assert archived_body["items"][0]["archived"] is True

    restore = client.post(f"/records/{record['id']}/restore")
    assert restore.status_code == 200
    assert search(client, q="archive passport")["items"][0]["archived"] is False

    delete = client.delete(f"/records/{record['id']}")
    assert delete.status_code == 204
    assert search(client, q="archive passport", archived=True)["items"] == []


def test_saved_search_views_are_user_scoped_and_crud(search_context):
    client, *_repos = search_context
    payload = {
        "name": "Travel docs",
        "query": "passport",
        "filters": {"itemTypes": ["record"], "statuses": ["active"]},
        "sort": "updated_desc",
        "icon": "plane",
        "is_pinned": True,
    }

    created = client.post("/saved-views", json=payload)
    assert created.status_code == 201
    view_id = created.json()["saved_view_id"]
    assert created.json()["name"] == "Travel docs"

    listed = client.get("/saved-views")
    assert listed.status_code == 200
    assert [item["saved_view_id"] for item in listed.json()] == [view_id]

    updated = client.patch(f"/saved-views/{view_id}", json={"name": "Passport docs", "is_pinned": False})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Passport docs"
    assert updated.json()["is_pinned"] is False

    set_auth_user("other-user")
    assert client.get("/saved-views").json() == []
    assert client.get(f"/saved-views/{view_id}").status_code == 404

    set_auth_user("local-dev-user")
    assert client.delete(f"/saved-views/{view_id}").status_code == 204
    assert client.get("/saved-views").json() == []
