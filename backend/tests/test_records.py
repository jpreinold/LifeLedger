from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
import base64

import pytest
from fastapi.testclient import TestClient

from app.auth import UserContext, get_current_user
from app.config import load_settings
from app.dynamo_repository import DynamoRecordRepository
from app.encryption_service import EncryptionService
from app.main import app, get_encryption_service, get_linked_item_repository, get_record_repository
from app.linked_items_repository import LocalLinkedItemRepository
from app.models import Record
from app.records_repository import LocalRecordRepository
from app.schemas import RecordCreate, RecordResponse, RecordStatus, RecordUpdate


@pytest.fixture()
def record_repo(tmp_path):
    return LocalRecordRepository(tmp_path / "records.json")


@pytest.fixture()
def linked_repo(tmp_path):
    return LocalLinkedItemRepository(tmp_path / "linked-items.json")


@pytest.fixture()
def client(record_repo, linked_repo):
    app.dependency_overrides[get_record_repository] = lambda: record_repo
    app.dependency_overrides[get_linked_item_repository] = lambda: linked_repo

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def encrypted_client(record_repo, linked_repo):
    encryption_service = EncryptionService(
        load_settings(
            {
                "RECORD_ENCRYPTION_MODE": "local",
                "LOCAL_RECORDS_ENCRYPTION_KEY": base64.b64encode(b"1" * 32).decode("ascii"),
            }
        )
    )
    app.dependency_overrides[get_record_repository] = lambda: record_repo
    app.dependency_overrides[get_linked_item_repository] = lambda: linked_repo
    app.dependency_overrides[get_encryption_service] = lambda: encryption_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


class FakeDynamoTable:
    def __init__(self):
        self.items = {}

    def query(self, ExpressionAttributeValues, **_kwargs):
        user_id = ExpressionAttributeValues[":user_id"]
        return {
            "Items": [
                item
                for item in self.items.values()
                if item["user_id"] == user_id
            ]
        }

    def put_item(self, Item):
        self.items[(Item["user_id"], Item["id"])] = dict(Item)
        return {}

    def get_item(self, Key):
        item = self.items.get((Key["user_id"], Key["id"]))
        if item is None:
            return {}
        return {"Item": item}

    def delete_item(self, Key, ReturnValues=None):
        item = self.items.pop((Key["user_id"], Key["id"]), None)
        if item is None:
            return {}
        return {"Attributes": item}


def record_payload(**overrides):
    payload = {
        "record_type": "passport",
        "title": "Passport",
        "category": "Documents",
        "owner_name": "Alina",
        "provider_or_brand": "United States",
        "issue_date": date.today().isoformat(),
        "expiration_date": (date.today() + timedelta(days=365)).isoformat(),
        "location_hint": "Home file",
        "notes": "Keep notes general.",
        "tags": [" travel ", "", "Travel", "documents"],
    }
    payload.update(overrides)
    return payload


def set_auth_user(user_id: str):
    app.dependency_overrides[get_current_user] = lambda: UserContext(user_id=user_id)


def test_create_record_derives_user_id_from_auth_context(client, record_repo):
    set_auth_user("user-a")

    response = client.post("/records", json=record_payload())

    assert response.status_code == 201
    body = response.json()
    assert "user_id" not in body
    assert body["title"] == "Passport"
    assert body["status"] == "active"
    assert body["tags"] == ["travel", "documents"]

    saved = record_repo.get_record("user-a", body["id"])
    assert saved is not None
    assert saved.user_id == "user-a"
    assert record_repo.get_record("local-dev-user", body["id"]) is None


def test_create_record_rejects_frontend_user_id(client):
    response = client.post("/records", json={**record_payload(), "user_id": "attacker"})

    assert response.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"record_type": "general", "title": " "},
        {"title": "Missing type"},
        {"record_type": "general"},
    ],
)
def test_create_record_validates_required_title_and_type(client, payload):
    response = client.post("/records", json=payload)

    assert response.status_code == 422


def test_records_are_user_scoped_for_list_get_update_archive_restore_and_delete(client):
    set_auth_user("user-a")
    created = client.post("/records", json=record_payload(title="User A record")).json()

    set_auth_user("user-b")
    assert client.get("/records").json() == []
    assert client.get(f"/records/{created['id']}").status_code == 404
    assert client.put(f"/records/{created['id']}", json={"title": "Blocked"}).status_code == 404
    assert client.post(f"/records/{created['id']}/archive").status_code == 404
    assert client.post(f"/records/{created['id']}/restore").status_code == 404
    assert client.delete(f"/records/{created['id']}").status_code == 404

    set_auth_user("user-a")
    update_response = client.put(f"/records/{created['id']}", json={"title": "Updated record"})
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Updated record"

    delete_response = client.delete(f"/records/{created['id']}")
    assert delete_response.status_code == 204


def test_archived_records_are_hidden_by_default_but_queryable(client):
    created = client.post("/records", json=record_payload(title="Archive me")).json()

    archive_response = client.post(f"/records/{created['id']}/archive")
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "archived"

    default_list = client.get("/records")
    include_archived_list = client.get("/records?include_archived=true")

    assert default_list.status_code == 200
    assert default_list.json() == []
    assert include_archived_list.status_code == 200
    assert [item["id"] for item in include_archived_list.json()] == [created["id"]]

    restore_response = client.post(f"/records/{created['id']}/restore")
    assert restore_response.status_code == 200
    assert restore_response.json()["status"] == "active"
    assert [item["id"] for item in client.get("/records").json()] == [created["id"]]


def test_local_json_record_repository_persists_across_instances(tmp_path):
    data_file = tmp_path / "records.json"
    first_repo = LocalRecordRepository(data_file)
    record = build_record()

    first_repo.create_record(record)
    second_repo = LocalRecordRepository(data_file)
    loaded = second_repo.get_record(record.user_id, record.id)

    assert loaded is not None
    assert loaded.id == record.id
    assert loaded.title == "Repository record"


def test_dynamo_record_repository_uses_user_id_and_id_keys():
    table = FakeDynamoTable()
    repo = DynamoRecordRepository(table_name="records", region_name="us-east-1", table=table)
    record = build_record(user_id="user-a")

    repo.create_record(record)
    assert ("user-a", record.id) in table.items
    assert repo.get_record("other-user", record.id) is None
    assert repo.list_records("other-user") == []

    loaded = repo.get_record("user-a", record.id)
    assert loaded is not None
    assert loaded.id == record.id

    archived = repo.archive_record("user-a", record.id)
    assert archived is not None
    assert archived.status == RecordStatus.ARCHIVED
    assert repo.list_records("user-a") == []
    assert len(repo.list_records("user-a", include_archived=True)) == 1

    assert repo.delete_record("user-a", record.id) is True
    assert repo.delete_record("user-a", record.id) is False


def test_sensitive_identifier_fields_are_not_exposed_in_record_schemas():
    forbidden_fields = {
        "passport_number",
        "driver_license_number",
        "ssn",
        "payment_card_number",
        "bank_account_number",
        "insurance_policy_number",
        "vin",
        "password",
        "credentials",
        "api_key",
        "government_identifier",
        "user_id",
    }

    for schema in (RecordCreate, RecordUpdate, RecordResponse):
        assert forbidden_fields.isdisjoint(schema.model_fields)


def test_protected_payload_is_encrypted_and_omitted_from_standard_responses(encrypted_client, record_repo, caplog):
    caplog.set_level("INFO", logger="app.security")
    created = encrypted_client.post("/records", json=record_payload(record_type="passport", title="Passport")).json()

    protected_response = encrypted_client.put(
        f"/records/{created['id']}/protected",
        json={"document_number": "P1234567"},
    )
    assert protected_response.status_code == 200
    assert protected_response.json()["has_protected_data"] is True
    assert protected_response.json()["protected_field_names"] == ["document_number"]

    saved = record_repo.get_record("local-dev-user", created["id"])
    assert saved is not None
    assert saved.protected_ciphertext
    assert saved.protected_encrypted_data_key
    assert saved.protected_nonce
    assert "P1234567" not in str(saved.model_dump())

    list_body = encrypted_client.get("/records").json()
    detail_body = encrypted_client.get(f"/records/{created['id']}").json()
    assert "P1234567" not in str(list_body)
    assert "P1234567" not in str(detail_body)
    assert list_body[0]["has_protected_data"] is True
    assert detail_body["protected_field_names"] == ["document_number"]
    assert "protected_ciphertext" not in detail_body
    assert "protected_encrypted_data_key" not in detail_body

    assert "P1234567" not in caplog.text


def test_reveal_is_explicit_no_store_and_user_scoped(encrypted_client):
    set_auth_user("user-a")
    created = encrypted_client.post("/records", json=record_payload(record_type="passport", title="Passport")).json()
    assert encrypted_client.put(f"/records/{created['id']}/protected", json={"document_number": "P1234567"}).status_code == 200

    reveal_response = encrypted_client.get(f"/records/{created['id']}/protected")
    assert reveal_response.status_code == 200
    assert reveal_response.json()["document_number"] == "P1234567"
    assert reveal_response.headers["cache-control"] == "no-store, private"
    assert reveal_response.headers["pragma"] == "no-cache"

    set_auth_user("user-b")
    assert encrypted_client.get(f"/records/{created['id']}/protected/status").status_code == 404
    assert encrypted_client.get(f"/records/{created['id']}/protected").status_code == 404
    assert encrypted_client.put(f"/records/{created['id']}/protected", json={"document_number": "blocked"}).status_code == 404
    assert encrypted_client.delete(f"/records/{created['id']}/protected").status_code == 404


def test_copied_protected_ciphertext_does_not_decrypt_under_another_record_context(encrypted_client, record_repo):
    set_auth_user("user-a")
    first = encrypted_client.post("/records", json=record_payload(record_type="passport", title="First")).json()
    second = encrypted_client.post("/records", json=record_payload(record_type="passport", title="Second")).json()
    encrypted_client.put(f"/records/{first['id']}/protected", json={"document_number": "P1234567"})

    first_record = record_repo.get_record("user-a", first["id"])
    second_record = record_repo.get_record("user-a", second["id"])
    copied = second_record.model_copy(
        update={
            "protected_ciphertext": first_record.protected_ciphertext,
            "protected_encrypted_data_key": first_record.protected_encrypted_data_key,
            "protected_nonce": first_record.protected_nonce,
            "protected_encryption_version": first_record.protected_encryption_version,
            "protected_key_arn": first_record.protected_key_arn,
            "protected_updated_at": first_record.protected_updated_at,
            "protected_field_names": first_record.protected_field_names,
        }
    )
    record_repo.update_record(copied)

    response = encrypted_client.get(f"/records/{second['id']}/protected")
    assert response.status_code == 503
    assert "P1234567" not in response.text


def test_clear_protected_data_leaves_metadata_intact(encrypted_client, record_repo):
    created = encrypted_client.post("/records", json=record_payload(record_type="insurance", title="Insurance")).json()
    encrypted_client.put(f"/records/{created['id']}/protected", json={"policy_number": "POL-123"})

    clear_response = encrypted_client.delete(f"/records/{created['id']}/protected")

    assert clear_response.status_code == 200
    assert clear_response.json()["has_protected_data"] is False
    saved = record_repo.get_record("local-dev-user", created["id"])
    assert saved is not None
    assert saved.title == "Insurance"
    assert saved.protected_ciphertext is None


def test_missing_encryption_configuration_fails_closed(client):
    created = client.post("/records", json=record_payload(record_type="passport", title="Passport")).json()

    response = client.put(f"/records/{created['id']}/protected", json={"document_number": "P1234567"})

    assert response.status_code == 409
    assert response.json()["detail"] == "Protected record storage is not configured for this environment."


def build_record(user_id="local-dev-user"):
    now = datetime.now(timezone.utc)
    return Record(
        id=str(uuid4()),
        user_id=user_id,
        record_type="general",
        title="Repository record",
        category="General",
        notes=None,
        tags=["home"],
        status="active",
        created_at=now,
        updated_at=now,
    )


def test_dynamic_record_field_crud_preserves_record_and_validates_types(client, record_repo):
    created = client.post("/records", json=record_payload(record_type="vehicle", title="Vehicle")).json()

    add_response = client.post(
        f"/records/{created['id']}/fields",
        json={"label": "Mileage", "field_type": "number", "value": "42000"},
    )
    assert add_response.status_code == 201
    field = add_response.json()["dynamic_fields"][0]
    assert field["label"] == "Mileage"
    assert field["field_type"] == "number"
    assert field["value"] == 42000.0
    assert field["has_value"] is True

    invalid_response = client.post(
        f"/records/{created['id']}/fields",
        json={"label": "Service date", "field_type": "date", "value": "tomorrow"},
    )
    assert invalid_response.status_code == 422

    update_response = client.put(
        f"/records/{created['id']}/fields/{field['field_id']}",
        json={"value": 43000, "display_order": 5},
    )
    assert update_response.status_code == 200
    updated_field = update_response.json()["dynamic_fields"][0]
    assert updated_field["value"] == 43000.0
    assert updated_field["display_order"] == 5

    type_change_response = client.put(
        f"/records/{created['id']}/fields/{field['field_id']}",
        json={"field_type": "date"},
    )
    assert type_change_response.status_code == 409

    delete_response = client.delete(f"/records/{created['id']}/fields/{field['field_id']}")
    assert delete_response.status_code == 200
    assert delete_response.json()["dynamic_fields"] == []
    assert record_repo.get_record("local-dev-user", created["id"]) is not None


def test_dynamic_record_field_key_rejects_duplicate_retry_without_overwriting(client):
    created = client.post("/records", json=record_payload(record_type="vehicle", title="Vehicle")).json()
    detail = {
        "key": "registration_expiration",
        "label": "Registration expiration date",
        "field_type": "date",
        "value": "2030-04-15",
    }

    first = client.post(f"/records/{created['id']}/fields", json=detail)
    retry = client.post(f"/records/{created['id']}/fields", json={**detail, "value": "2031-04-15"})

    assert first.status_code == 201
    assert retry.status_code == 409
    current = client.get(f"/records/{created['id']}").json()
    assert len(current["dynamic_fields"]) == 1
    assert current["dynamic_fields"][0]["value"] == "2030-04-15"


def test_sensitive_dynamic_field_is_encrypted_masked_revealed_and_user_scoped(encrypted_client, record_repo, caplog):
    caplog.set_level("INFO", logger="app.security")
    set_auth_user("user-a")
    created = encrypted_client.post("/records", json=record_payload(record_type="vehicle", title="Vehicle")).json()

    add_response = encrypted_client.post(
        f"/records/{created['id']}/fields",
        json={"label": "VIN", "field_type": "short_text", "value": "1HGCM82633A004352", "is_sensitive": True},
    )
    assert add_response.status_code == 201
    field = add_response.json()["dynamic_fields"][0]
    assert field["is_sensitive"] is True
    assert field["value"] is None
    assert field["has_value"] is True

    saved = record_repo.get_record("user-a", created["id"])
    assert saved is not None
    assert saved.protected_ciphertext
    assert "1HGCM82633A004352" not in str(saved.model_dump())

    list_body = encrypted_client.get("/records").json()
    detail_body = encrypted_client.get(f"/records/{created['id']}").json()
    assert "1HGCM82633A004352" not in str(list_body)
    assert "1HGCM82633A004352" not in str(detail_body)

    reveal_response = encrypted_client.get(f"/records/{created['id']}/fields/{field['field_id']}/reveal")
    assert reveal_response.status_code == 200
    assert reveal_response.json() == {"field_id": field["field_id"], "value": "1HGCM82633A004352"}
    assert reveal_response.headers["cache-control"] == "no-store, private"
    assert reveal_response.headers["pragma"] == "no-cache"

    set_auth_user("user-b")
    assert encrypted_client.get(f"/records/{created['id']}/fields/{field['field_id']}/reveal").status_code == 404
    assert encrypted_client.put(f"/records/{created['id']}/fields/{field['field_id']}", json={"value": "blocked"}).status_code == 404
    assert encrypted_client.delete(f"/records/{created['id']}/fields/{field['field_id']}").status_code == 404
    assert "1HGCM82633A004352" not in caplog.text


def test_legacy_protected_payload_and_dynamic_sensitive_fields_preserve_each_other(encrypted_client, record_repo):
    created = encrypted_client.post("/records", json=record_payload(record_type="passport", title="Passport")).json()
    protected_response = encrypted_client.put(
        f"/records/{created['id']}/protected",
        json={"document_number": "P1234567"},
    )
    assert protected_response.status_code == 200

    dynamic_response = encrypted_client.post(
        f"/records/{created['id']}/fields",
        json={"label": "Backup document number", "field_type": "short_text", "value": "B7654321", "is_sensitive": True},
    )
    assert dynamic_response.status_code == 201
    field = dynamic_response.json()["dynamic_fields"][0]

    reveal_protected = encrypted_client.get(f"/records/{created['id']}/protected")
    assert reveal_protected.status_code == 200
    assert reveal_protected.json()["document_number"] == "P1234567"

    cleared = encrypted_client.delete(f"/records/{created['id']}/protected")
    assert cleared.status_code == 200
    assert cleared.json()["has_protected_data"] is True
    assert cleared.json()["protected_field_names"] == []

    reveal_dynamic = encrypted_client.get(f"/records/{created['id']}/fields/{field['field_id']}/reveal")
    assert reveal_dynamic.status_code == 200
    assert reveal_dynamic.json()["value"] == "B7654321"

    saved = record_repo.get_record("local-dev-user", created["id"])
    assert saved is not None
    assert "P1234567" not in str(saved.model_dump())
    assert "B7654321" not in str(saved.model_dump())


def test_sensitive_dynamic_field_requires_encryption_configuration(client):
    created = client.post("/records", json=record_payload(record_type="general", title="General")).json()

    response = client.post(
        f"/records/{created['id']}/fields",
        json={"label": "Sensitive note", "field_type": "short_text", "value": "private", "is_sensitive": True},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Protected record storage is not configured for this environment."


def test_record_creation_idempotency_key_prevents_duplicate_records(client, record_repo):
    set_auth_user("user-a")
    headers = {"Idempotency-Key": "record-workflow-123"}

    first = client.post("/records", json=record_payload(title="Idempotent record"), headers=headers)
    second = client.post("/records", json=record_payload(title="Idempotent record"), headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert len(record_repo.list_records("user-a", include_archived=True)) == 1

    set_auth_user("user-b")
    other_user = client.post("/records", json=record_payload(title="Idempotent record"), headers=headers)
    assert other_user.status_code == 201
    assert other_user.json()["id"] != first.json()["id"]


def test_protected_patch_replaces_and_removes_one_detail(encrypted_client):
    created = encrypted_client.post(
        "/records", json=record_payload(record_type="insurance", title="Insurance")
    ).json()
    assert encrypted_client.put(
        f"/records/{created['id']}/protected",
        json={"policy_number": "POL-123", "member_number": "MEM-456"},
    ).status_code == 200

    updated = encrypted_client.patch(
        f"/records/{created['id']}/protected",
        json={"policy_number": "POL-999", "member_number": None},
    )
    assert updated.status_code == 200
    assert updated.json()["protected_field_names"] == ["policy_number"]
    assert encrypted_client.get(f"/records/{created['id']}/protected").json() == {
        "document_number": None,
        "license_number": None,
        "vin": None,
        "policy_number": "POL-999",
        "member_number": None,
        "serial_number": None,
        "account_reference": None,
        "sensitive_notes": None,
    }


def test_protected_validation_error_does_not_echo_plaintext(encrypted_client, caplog):
    caplog.set_level("INFO")
    created = encrypted_client.post(
        "/records", json=record_payload(record_type="vehicle", title="Vehicle")
    ).json()
    rejected_value = "BAD-PROTECTED-VALUE"

    response = encrypted_client.patch(
        f"/records/{created['id']}/protected",
        json={"vin": rejected_value},
    )

    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store, private"
    assert rejected_value not in response.text
    assert rejected_value not in caplog.text
