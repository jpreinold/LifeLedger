from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.attachments_repository import LocalRecordAttachmentRepository
from app.auth import UserContext, get_current_user
from app.linked_items_repository import DynamoLinkedItemRepository, LocalLinkedItemRepository
from app.main import (
    app,
    get_linked_item_repository,
    get_record_attachment_repository,
    get_record_repository,
    get_repository,
)
from app.models import LinkedItem
from app.records_repository import LocalRecordRepository
from app.repository import LocalReminderRepository
from app.schemas import LinkedEntityType, RelationshipType


@pytest.fixture()
def link_context(tmp_path):
    record_repo = LocalRecordRepository(tmp_path / "records.json")
    reminder_repo = LocalReminderRepository(tmp_path / "reminders.json")
    linked_repo = LocalLinkedItemRepository(tmp_path / "linked-items.json")
    attachment_repo = LocalRecordAttachmentRepository(tmp_path / "attachments.json")

    app.dependency_overrides[get_record_repository] = lambda: record_repo
    app.dependency_overrides[get_repository] = lambda: reminder_repo
    app.dependency_overrides[get_linked_item_repository] = lambda: linked_repo
    app.dependency_overrides[get_record_attachment_repository] = lambda: attachment_repo

    with TestClient(app) as client:
        yield client, record_repo, reminder_repo, linked_repo

    app.dependency_overrides.clear()


def set_auth_user(user_id: str):
    app.dependency_overrides[get_current_user] = lambda: UserContext(user_id=user_id)


def record_payload(**overrides):
    payload = {
        "record_type": "vehicle",
        "title": "2018 Honda Accord",
        "category": "Auto",
        "owner_name": "Alina",
        "provider_or_brand": "Honda",
        "notes": "Safe notes only.",
    }
    payload.update(overrides)
    return payload


def reminder_payload(**overrides):
    payload = {
        "title": "Renew registration",
        "category": "Car",
        "due_date": date.today().isoformat(),
        "repeat": "Yearly",
        "priority": "High",
        "notes": "Bring paperwork.",
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


def test_record_links_resolve_records_reminders_and_reverse_record_view(link_context):
    client, *_ = link_context
    vehicle = create_record(client)
    insurance = create_record(
        client,
        record_type="insurance",
        title="Progressive Auto Insurance",
        category="Insurance",
        provider_or_brand="Progressive",
    )
    reminder = create_reminder(client)

    record_link = client.post(
        f"/records/{vehicle['id']}/links",
        json={"target_type": "record", "target_id": insurance["id"], "relationship_type": "insures"},
    )
    reminder_link = client.post(
        f"/records/{vehicle['id']}/links",
        json={"target_type": "reminder", "target_id": reminder["id"], "relationship_type": "renews"},
    )

    assert record_link.status_code == 201
    assert reminder_link.status_code == 201
    assert "user_id" not in record_link.json()

    vehicle_links = client.get(f"/records/{vehicle['id']}/links")
    assert vehicle_links.status_code == 200
    body = vehicle_links.json()
    assert [item["linked_entity"]["title"] for item in body["records"]] == ["Progressive Auto Insurance"]
    assert [item["linked_entity"]["title"] for item in body["reminders"]] == ["Renew registration"]
    assert body["records"][0]["direction"] == "outbound"
    assert body["records"][0]["linked_entity"]["record_type"] == "insurance"
    assert body["reminders"][0]["linked_entity"]["due_date"] == reminder["due_date"]
    assert "protected_ciphertext" not in str(body)
    assert "clean_object_key" not in str(body)

    reverse_links = client.get(f"/records/{insurance['id']}/links")
    assert reverse_links.status_code == 200
    assert reverse_links.json()["records"][0]["linked_entity"]["title"] == "2018 Honda Accord"
    assert reverse_links.json()["records"][0]["direction"] == "inbound"

    reminder_links = client.get(f"/reminders/{reminder['id']}/links")
    assert reminder_links.status_code == 200
    assert reminder_links.json()["records"][0]["linked_entity"]["title"] == "2018 Honda Accord"
    assert reminder_links.json()["reminders"] == []


def test_link_create_rejects_frontend_user_id(link_context):
    client, *_ = link_context
    source = create_record(client)
    target = create_record(client, title="Warranty", record_type="warranty")

    response = client.post(
        f"/records/{source['id']}/links",
        json={"target_type": "record", "target_id": target["id"], "user_id": "attacker"},
    )

    assert response.status_code == 422


def test_link_validation_rejects_self_duplicate_reverse_and_unsupported(link_context):
    client, *_ = link_context
    source = create_record(client)
    target = create_record(client, title="Powertrain Warranty", record_type="warranty")

    self_link = client.post(
        f"/records/{source['id']}/links",
        json={"target_type": "record", "target_id": source["id"]},
    )
    assert self_link.status_code == 409

    first = client.post(
        f"/records/{source['id']}/links",
        json={"target_type": "record", "target_id": target["id"], "relationship_type": "warranty_for"},
    )
    assert first.status_code == 201

    duplicate = client.post(f"/records/{source['id']}/links", json={"target_type": "record", "target_id": target["id"]})
    reverse = client.post(f"/records/{target['id']}/links", json={"target_type": "record", "target_id": source["id"]})
    unsupported = client.post(f"/records/{source['id']}/links", json={"target_type": "attachment", "target_id": "x"})

    assert duplicate.status_code == 409
    assert reverse.status_code == 409
    assert unsupported.status_code == 422


def test_link_routes_are_user_scoped(link_context):
    client, *_ = link_context
    set_auth_user("user-a")
    source = create_record(client, title="User A vehicle")
    target = create_record(client, title="User A insurance", record_type="insurance")
    created = client.post(f"/records/{source['id']}/links", json={"target_type": "record", "target_id": target["id"]})
    assert created.status_code == 201

    set_auth_user("user-b")
    other_source = create_record(client, title="User B vehicle")
    cross_user = client.post(f"/records/{other_source['id']}/links", json={"target_type": "record", "target_id": target["id"]})

    assert cross_user.status_code == 404
    assert client.get(f"/records/{source['id']}/links").status_code == 404
    assert client.delete(f"/records/{source['id']}/links/{created.json()['link_id']}").status_code == 404


def test_unlink_and_entity_delete_cleanup_preserve_related_entities(link_context):
    client, *_ = link_context
    source = create_record(client, title="Vehicle")
    target = create_record(client, title="Insurance", record_type="insurance")
    reminder = create_reminder(client, title="Rotate tires")

    record_link = client.post(f"/records/{source['id']}/links", json={"target_type": "record", "target_id": target["id"]}).json()
    reminder_link = client.post(f"/records/{source['id']}/links", json={"target_type": "reminder", "target_id": reminder["id"]}).json()

    unlink = client.delete(f"/records/{source['id']}/links/{record_link['link_id']}")
    assert unlink.status_code == 204
    assert client.get(f"/records/{source['id']}/links").json()["records"] == []
    assert client.get(f"/records/{target['id']}").status_code == 200

    client.post(f"/records/{source['id']}/links", json={"target_type": "record", "target_id": target["id"]})
    delete_target = client.delete(f"/records/{target['id']}")
    assert delete_target.status_code == 204
    assert client.get(f"/records/{source['id']}/links").json()["records"] == []
    assert client.get(f"/records/{source['id']}").status_code == 200

    delete_reminder = client.delete(f"/reminders/{reminder['id']}")
    assert delete_reminder.status_code == 204
    assert client.get(f"/records/{source['id']}/links").json()["reminders"] == []
    assert client.get(f"/records/{source['id']}").status_code == 200
    assert client.delete(f"/records/{source['id']}/links/{reminder_link['link_id']}").status_code == 404


def test_local_linked_item_repository_persists_across_instances(tmp_path):
    data_file = tmp_path / "linked-items.json"
    first_repo = LocalLinkedItemRepository(data_file)
    link = build_link()

    first_repo.create_link(link)
    second_repo = LocalLinkedItemRepository(data_file)
    loaded = second_repo.get_link("user-a", link.link_id)

    assert loaded is not None
    assert loaded.link_id == link.link_id
    assert second_repo.list_links_for_entity("user-a", LinkedEntityType.RECORD, "source-record") == [loaded]


class FakeLinkedItemsTable:
    def __init__(self):
        self.items = {}
        self.query_calls = []
        self.scan_called = False

    def put_item(self, Item):
        self.items[(Item["user_id"], Item["link_id"])] = dict(Item)
        return {}

    def get_item(self, Key):
        item = self.items.get((Key["user_id"], Key["link_id"]))
        return {"Item": item} if item else {}

    def query(self, **kwargs):
        self.query_calls.append(kwargs)
        values = kwargs["ExpressionAttributeValues"]
        user_id = values[":user_id"]
        prefix = values[":lookup_prefix"]
        key = "source_link_key" if kwargs["IndexName"] == "SourceLinksIndex" else "target_link_key"
        return {
            "Items": [
                item
                for item in self.items.values()
                if item["user_id"] == user_id and item[key].startswith(prefix)
            ]
        }

    def scan(self, **_kwargs):
        self.scan_called = True
        raise AssertionError("linked item repository must not scan")

    def delete_item(self, Key, ReturnValues=None):
        item = self.items.pop((Key["user_id"], Key["link_id"]), None)
        return {"Attributes": item} if item else {}


def test_dynamo_linked_item_repository_uses_lookup_indexes_not_scan():
    table = FakeLinkedItemsTable()
    repo = DynamoLinkedItemRepository(table_name="linked", region_name="us-east-1", table=table)
    link = build_link()

    repo.create_link(link)
    links = repo.list_links_for_entity("user-a", LinkedEntityType.RECORD, "source-record")

    assert links == [link]
    assert {call["IndexName"] for call in table.query_calls} == {"SourceLinksIndex", "TargetLinksIndex"}
    assert table.scan_called is False
    assert repo.link_exists("user-a", LinkedEntityType.RECORD, "source-record", LinkedEntityType.RECORD, "target-record") is True
    assert repo.delete_links_for_entity("user-a", LinkedEntityType.RECORD, "source-record") == 1
    assert repo.get_link("user-a", link.link_id) is None


def build_link():
    now = datetime.now(timezone.utc)
    link_id = str(uuid4())
    return LinkedItem(
        user_id="user-a",
        link_id=link_id,
        source_type=LinkedEntityType.RECORD,
        source_id="source-record",
        target_type=LinkedEntityType.RECORD,
        target_id="target-record",
        relationship_type=RelationshipType.RELATED,
        label=None,
        source_link_key=f"record#source-record#{link_id}",
        target_link_key=f"record#target-record#{link_id}",
        created_at=now,
        updated_at=now,
        created_by="user",
    )
