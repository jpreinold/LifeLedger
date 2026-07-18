import base64
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.attachments_repository import LocalRecordAttachmentRepository, record_attachment_key
from app.auth import UserContext, get_current_user
from app.config import load_settings
from app.encryption_service import EncryptionService
from app.linked_items_repository import LocalLinkedItemRepository
from app.main import (
    app,
    get_encryption_service,
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
from app.search_service import SearchProjectionService, document_item_id, record_search_item_id


@pytest.fixture()
def search_context(tmp_path):
    record_repo = LocalRecordRepository(tmp_path / "records.json")
    reminder_repo = LocalReminderRepository(tmp_path / "reminders.json")
    attachment_repo = LocalRecordAttachmentRepository(tmp_path / "attachments.json")
    linked_repo = LocalLinkedItemRepository(tmp_path / "linked-items.json")
    search_repo = LocalSearchIndexRepository(tmp_path / "search-index.json")
    saved_view_repo = LocalSavedSearchViewRepository(tmp_path / "saved-views.json")
    encryption_service = EncryptionService(
        load_settings(
            {
                "RECORD_ENCRYPTION_MODE": "local",
                "LOCAL_RECORDS_ENCRYPTION_KEY": base64.b64encode(b"2" * 32).decode("ascii"),
            }
        )
    )

    app.dependency_overrides[get_record_repository] = lambda: record_repo
    app.dependency_overrides[get_encryption_service] = lambda: encryption_service
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


def test_protected_values_never_enter_search_projection(search_context):
    client, *_repos = search_context
    record = create_record(client, title="Search-safe passport", record_type="passport")
    protected_value = "P-NEVER-INDEX-8842"

    protected = client.put(
        f"/records/{record['id']}/protected", json={"document_number": protected_value}
    )

    assert protected.status_code == 200
    assert search(client, q="never index 8842")["items"] == []
    standard = client.get(f"/records/{record['id']}")
    assert protected_value not in standard.text


def test_renewal_and_completion_refresh_search_dates_and_status(search_context):
    client, *_repos = search_context
    previous_date = date.today() + timedelta(days=2)
    new_date = date.today() + timedelta(days=400)
    record = create_record(
        client,
        title="Car registration projection",
        record_type="vehicle",
        expiration_date=None,
        renewal_date=previous_date.isoformat(),
    )
    renewal = create_reminder(
        client,
        title="Renew projection registration",
        due_date=previous_date.isoformat(),
        repeat="Yearly",
        renewal_details={
            "item_name": "Car registration projection",
            "renewal_kind": "renewal",
            "renewal_date": previous_date.isoformat(),
        },
    )
    assert client.post(
        f"/records/{record['id']}/links",
        json={"target_type": "reminder", "target_id": renewal["id"], "relationship_type": "renews"},
    ).status_code == 201

    assert client.post(
        f"/reminders/{renewal['id']}/renew", json={"new_due_date": new_date.isoformat()}
    ).status_code == 200
    record_result = next(
        item for item in search(client, q="car registration projection")["items"]
        if item["source_item_type"] == "record"
    )
    assert record_result["relevant_date"] == new_date.isoformat()

    one_time = create_reminder(
        client,
        title="Complete projection reminder",
        repeat="None",
        reminder_type="generic",
        renewal_details=None,
    )
    assert client.post(f"/reminders/{one_time['id']}/complete").status_code == 200
    completed_result = search(client, q="complete projection reminder")["items"][0]
    assert completed_result["status"] == "completed"


def test_relationship_and_linked_title_changes_refresh_both_projection_contexts(search_context):
    client, *_repos = search_context
    record = create_record(client, title="Baxter projection", record_type="pet")
    reminder = create_reminder(client, title="Rabies projection reminder")
    created = client.post(
        "/relationships",
        json={
            "source_item_type": "record",
            "source_item_id": record["id"],
            "target_item_type": "reminder",
            "target_item_id": reminder["id"],
            "relationship_type": "reminder_for",
            "custom_label": "Annual vaccine projection",
        },
    )
    assert created.status_code == 201
    relationship_id = created.json()["relationship_id"]
    assert {item["source_item_type"] for item in search(client, q="annual vaccine projection")["items"]} == {"record", "reminder"}

    changed = client.patch(
        f"/relationships/{relationship_id}",
        json={"custom_label": "Clinic paperwork projection"},
    )
    assert changed.status_code == 200
    assert search(client, q="annual vaccine projection")["items"] == []
    assert {item["source_item_type"] for item in search(client, q="clinic paperwork projection")["items"]} == {"record", "reminder"}

    renamed = client.put(f"/records/{record['id']}", json={"title": "Baxter renamed projection"})
    assert renamed.status_code == 200
    linked_reminder = next(
        item for item in search(client, q="baxter renamed projection")["items"]
        if item["source_item_type"] == "reminder"
    )
    assert linked_reminder["source_item_id"] == reminder["id"]

    assert client.delete(f"/relationships/{relationship_id}").status_code == 204
    assert search(client, q="clinic paperwork projection")["items"] == []


def test_document_metadata_sync_uses_document_id_and_delete_removes_projection(search_context):
    client, record_repo, reminder_repo, attachment_repo, linked_repo, search_repo, _saved_repo = search_context
    record = create_record(client, title="Document projection parent")
    attachment = create_attachment_metadata(attachment_repo, "local-dev-user", record["id"], "Original projection.pdf")
    service = build_projection_service(record_repo, reminder_repo, attachment_repo, linked_repo, search_repo)
    entity_id = document_item_id(record["id"], attachment.attachment_id)
    service.sync_entity_and_neighbors_observed("local-dev-user", LinkedEntityType.DOCUMENT, entity_id, operation="test_document_create")

    renamed = attachment_repo.update_attachment(
        attachment.model_copy(update={"display_name": "Renamed projection.pdf"})
    )
    service.sync_entity_and_neighbors_observed("local-dev-user", LinkedEntityType.DOCUMENT, entity_id, operation="test_document_update")
    assert search(client, q="original projection")["items"] == []
    result = search(client, q="renamed projection")["items"][0]
    assert result["source_item_id"] == entity_id
    assert result["navigation_metadata"]["attachment_id"] == renamed.attachment_id

    assert attachment_repo.delete_attachment_metadata("local-dev-user", record["id"], attachment.attachment_id)
    service.sync_entity_and_neighbors_observed("local-dev-user", LinkedEntityType.DOCUMENT, entity_id, operation="test_document_delete")
    assert search(client, q="renamed projection")["items"] == []


def test_projection_failure_is_persisted_and_reconciliation_repairs_stale_and_orphan_rows(search_context, monkeypatch):
    _client, record_repo, reminder_repo, attachment_repo, linked_repo, search_repo, _saved_repo = search_context
    client = _client
    created = create_record(client, title="Recoverable projection")
    service = build_projection_service(record_repo, reminder_repo, attachment_repo, linked_repo, search_repo)
    original_upsert = search_repo.upsert_projection

    def fail_upsert(_projection):
        raise RuntimeError("simulated projection storage outage")

    monkeypatch.setattr(search_repo, "upsert_projection", fail_upsert)
    with pytest.raises(RuntimeError, match="simulated projection storage outage"):
        service.sync_entity_observed(
            "local-dev-user", LinkedEntityType.RECORD, created["id"], operation="record_update"
        )
    failures = search_repo.list_sync_failures("local-dev-user")
    assert [(item.entity_id, item.operation, item.retryable) for item in failures] == [
        (created["id"], "record_update", True)
    ]

    monkeypatch.setattr(search_repo, "upsert_projection", original_upsert)
    projection = search_repo.get_projection("local-dev-user", record_search_item_id(created["id"]))
    assert projection is not None
    original_upsert(projection.model_copy(update={"display_title": "Stale title", "projection_version": 1}))

    orphan_source = create_record(client, title="Orphan projection")
    orphan_id = record_search_item_id(orphan_source["id"])
    assert record_repo.delete_record("local-dev-user", orphan_source["id"])
    assert search_repo.get_projection("local-dev-user", orphan_id) is not None

    repaired = service.rebuild_user("local-dev-user")
    assert repaired.failures_retried == 1
    assert repaired.failures_remaining == 0
    assert repaired.projections_deleted == 1
    current = search_repo.get_projection("local-dev-user", record_search_item_id(created["id"]))
    assert current is not None
    assert current.display_title == "Recoverable projection"
    assert current.projection_version > 1
    assert search_repo.get_projection("local-dev-user", orphan_id) is None

    second = service.rebuild_user("local-dev-user")
    assert second.projections_deleted == 0
    assert second.failures_remaining == 0